#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import yum
import os
import shutil
import sys
import pypungi
import logging

class PungiYum(yum.YumBase):
    """Subclass of Yum"""

    def __init__(self, config):
        self.pungiconfig = config
        yum.YumBase.__init__(self)

    def doLoggingSetup(self, debuglevel, errorlevel):
        """Setup the logging facility."""


        logdir = os.path.join(self.pungiconfig.get('default', 'destdir'), 'logs')
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        if self.pungiconfig.get('default', 'flavor'):
            logfile = os.path.join(logdir, '%s.%s.log' % (self.pungiconfig.get('default', 'flavor'),
                                                          self.pungiconfig.get('default', 'arch')))
        else:
            logfile = os.path.join(logdir, '%s.log' % (self.pungiconfig.get('default', 'arch')))

        yum.logging.basicConfig(level=yum.logging.DEBUG, filename=logfile)

    def doFileLogSetup(self, uid, logfile):
        # This function overrides a yum function, allowing pungi to control
        # the logging.
        pass

class Gather(pypungi.PungiBase):
    def __init__(self, config, pkglist):
	pypungi.PungiBase.__init__(self, config)

        # Set our own logging name space
        self.logger = logging.getLogger('Pungi.Gather')

        self.pkglist = pkglist
        self.config.cachedir = os.path.join(self.workdir, 'yumcache')
        self.polist = []
        self.srpmlist = []
        self.resolved_deps = {} # list the deps we've already resolved, short circuit.

        # Create a comps object and add our comps file for group definitions
        self.compsobj = yum.comps.Comps()
        self.compsobj.add(self.config.get('default', 'comps'))

        # Create a yum object to use
        self.ayum = PungiYum(config)
        self.ayum.doConfigSetup(fn=config.get('default', 'yumconf'), debuglevel=6, errorlevel=6, root=os.path.join(self.workdir, 'yumroot'))
        self.ayum.cleanMetadata() # clean metadata that might be in the cache from previous runs
        self.ayum.cleanSqlite() # clean metadata that might be in the cache from previous runs
        self.ayum.doRepoSetup()
        self.ayum.doTsSetup()
        self.ayum.doRpmDBSetup()
        if config.get('default', 'arch') == 'i386':
            arches = yum.rpmUtils.arch.getArchList('i686')
            self.ayum.compatarch = 'i686'
        elif config.get('default', 'arch') == 'ppc':
            arches = yum.rpmUtils.arch.getArchList('ppc64')
            self.ayum.compatarch = 'ppc64'
        elif config.get('default', 'arch') == 'sparc':
            arches = yum.rpmUtils.arch.getArchList('sparc64v')
            self.ayum.compatarch = 'sparc64v'
        else:
            arches = yum.rpmUtils.arch.getArchList(config.get('default', 'arch'))
            self.ayum.compatarch = config.get('default', 'arch')
        #self.doSackSetup(arches)
        #self.doSackSetup(archlist=arches) # work around temp break in yum api
        #self.doSackFilelistPopulate()
        self.ayum._getSacks(archlist=arches)

    def verifyCachePkg(self, po, path): # Stolen from yum
        """check the package checksum vs the cache
           return True if pkg is good, False if not"""

        (csum_type, csum) = po.returnIdSum()

        try:
            filesum = yum.misc.checksum(csum_type, path)
        except yum.Errors.MiscError:
            return False

        if filesum != csum:
            return False

        return True

    def getPackageDeps(self, po):
        """Add the dependencies for a given package to the
           transaction info"""


        self.logger.info('Checking deps of %s.%s' % (po.name, po.arch))

        reqs = po.requires
        provs = po.provides

        for req in reqs:
            if self.resolved_deps.has_key(req):
                continue
            (r,f,v) = req
            if r.startswith('rpmlib(') or r.startswith('config('):
                continue
            if req in provs:
                continue

            deps = self.ayum.whatProvides(r, f, v).returnPackages()
            if not deps:
                self.logger.warn("Unresolvable dependency %s in %s.%s" % (r, po.name, po.arch))
                continue

            depsack = yum.packageSack.ListPackageSack(deps)

            for dep in depsack.returnNewestByNameArch():
                self.ayum.tsInfo.addInstall(dep)
                self.logger.info('Added %s.%s for %s.%s' % (dep.name, dep.arch, po.name, po.arch))
           
            self.resolved_deps[req] = None

    def getPackagesFromGroup(self, group):
        """Get a list of package names from a comps object

            Returns a list of package names"""

        packages = []
        optional = None
        nodefaults = None

        # Check for an option regarding default/optional packages
        last = group.split()[-1]
        if last == '--optional':
            optional = True
            group = group.split(' --optional')[0]

        if last == '--nodefaults':
            nodefaults = True
            group = group.split(' --nodefaults')[0]

        # Check if we have the group
        if not self.compsobj.has_group(group):
            self.logger.error("Group %s not found in comps!" % group)
            return packages

        # Get the group object to work with
        groupobj = self.compsobj.return_group(group)

        # Add the mandatory packages
        packages.extend(groupobj.mandatory_packages.keys())

        # Add the default packages unless we don't want them
        if not nodefaults:
            packages.extend(groupobj.default_packages.keys())

        # Add the optional packages if we want them
        if optional:
            packages.extend(groupobj.optional_packages.keys())

        # Deal with conditional packages
        # Populate a dict with the name of the required package and value
        # of the package objects it would bring in.  To be used later if
        # we match the conditional.
        for condreq, cond in groupobj.conditional_packages.iteritems():
            pkgs = self.ayum.pkgSack.searchNevra(name=condreq)
            if pkgs:
                pkgs = self.ayum.bestPackagesFromList(pkgs)
            if self.ayum.tsInfo.conditionals.has_key(cond):
                self.ayum.tsInfo.conditionals[cond].extend(pkgs)
            else:
                self.ayum.tsInfo.conditionals[cond] = pkgs

        return packages

    def getPackageObjects(self):
        """Cycle through the list of packages, get package object
           matches, and resolve deps.

           Returns a list of package objects"""


        final_pkgobjs = {} # The final list of package objects
        searchlist = [] # The list of package names/globs to search for
        matchdict = {} # A dict of objects to names

        grouplist = []
        excludelist = []
        addlist = []

        # Cycle through the package list and pull out the groups
        for line in self.pkglist:
            line = line.strip()
            if line.startswith('#'):
                self.logger.debug('Skipping comment: %s' % line)
                continue
            if line.startswith('@'):
                self.logger.info('Adding group: %s' % line)
                grouplist.append(line.strip('@'))
                continue
            if line.startswith('-'):
                self.logger.info('Adding exclude: %s' % line)
                excludelist.append(line.strip('-'))
                continue
            else:
                self.logger.info('Adding package: %s' % line)
                addlist.append(line)

        # First remove the excludes
        self.ayum.conf.exclude.extend(excludelist)
        self.ayum.excludePackages()

        # Get a list of packages from groups
        for group in grouplist:
            searchlist.extend(self.getPackagesFromGroup(group))

        # Add the adds
        searchlist.extend(addlist)

        # Make the search list unique
        searchlist = yum.misc.unique(searchlist)

        # Search repos for things in our searchlist, supports globs
        (exactmatched, matched, unmatched) = yum.packages.parsePackages(self.ayum.pkgSack.returnPackages(), searchlist, casematch=1)
        matches = exactmatched + matched

        # Populate a dict of package objects to their names
        for match in matches:
            matchdict[match.name] = match
            
        # Get the newest results from the search
        mysack = yum.packageSack.ListPackageSack(matches)
        for match in mysack.returnNewestByNameArch():
            self.ayum.tsInfo.addInstall(match)
            self.logger.debug('Found %s.%s' % (match.name, match.arch))

        for pkg in unmatched:
            if not pkg in matchdict.keys():
                self.logger.warn('Could not find a match for %s' % pkg)

        if len(self.ayum.tsInfo) == 0:
            raise yum.Errors.MiscError, 'No packages found to download.'

        moretoprocess = True
        while moretoprocess: # Our fun loop
            moretoprocess = False
            for txmbr in self.ayum.tsInfo:
                if not final_pkgobjs.has_key(txmbr.po):
                    final_pkgobjs[txmbr.po] = None # Add the pkg to our final list
                    self.getPackageDeps(txmbr.po) # Get the deps of our package
                    moretoprocess = True

        self.polist = final_pkgobjs.keys()
        self.logger.info('Finished gathering package objects.')

    def getSRPMList(self):
        """Cycle through the list of package objects and
           find the sourcerpm for them.  Requires yum still
           configured and a list of package objects"""

 
        for po in self.polist:
            srpm = po.sourcerpm.split('.src.rpm')[0]
            if not srpm in self.srpmlist:
                self.srpmlist.append(srpm)


    def downloadPackages(self):
        """Cycle through the list of package objects and
           download them from their respective repos."""


        downloads = []
        for pkg in self.polist:
            downloads.append('%s.%s' % (pkg.name, pkg.arch))
            downloads.sort()
        self.logger.info("Download list: %s" % downloads)

        # Package location within destdir, name subject to change/config
        pkgdir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 
                                             self.config.get('default', 'flavor'), 
                                             self.config.get('default', 'arch'), 
                                             self.config.get('default', 'osdir'),
                                             self.config.get('default', 'product_path')) 

        if not os.path.exists(pkgdir):
            os.makedirs(pkgdir)

        for pkg in self.polist:
            repo = self.ayum.repos.getRepo(pkg.repoid)
            remote = pkg.relativepath
            local = os.path.basename(remote)
            local = os.path.join(self.config.get('default', 'cachedir'), local)
            if os.path.exists(local) and self.verifyCachePkg(pkg, local):
                self.logger.debug("%s already exists and appears to be complete" % local)
                target = os.path.join(pkgdir, os.path.basename(remote))
                if os.path.exists(target):
                    os.remove(target) # avoid traceback after interrupted download
                os.link(local, target)
                continue

            # Disable cache otherwise things won't download
            repo.cache = 0
            self.logger.info('Downloading %s' % os.path.basename(remote))
            pkg.localpath = local # Hack: to set the localpath to what we want.

            # do a little dance for file:// repos...
            path = repo.getPackage(pkg)
            if not os.path.exists(local) or not os.path.samefile(path, local):
                shutil.copy2(path, local)
 
            os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
            self.logger.info('Finished downloading packages.')


    def downloadSRPMs(self):
        """Cycle through the list of srpms and
           find the package objects for them, Then download them."""


        srpmpolist = []

        ## Work around for yum bug
        #for sack in self.pkgSack.sacks.values():
        #    sack.added = {}
        #    sack.excludes = {}

        #self.pkgSack.excludes = {}

        ## We need to reset the yum object
        #self.pkgSack = None

        ## Setup the sack with just src arch
        #self.doSackSetup(archlist=['src'])

        # Make a new yum object
        syum = yum.YumBase()
        syum.doConfigSetup(fn=self.config.get('default', 'yumconf'), debuglevel=6, errorlevel=6, root=os.path.join(self.workdir, 'yumroot'))
        syum.doRepoSetup()

        syum._getSacks(archlist=['src'])

        for srpm in self.srpmlist:
            (sname, sver, srel) = srpm.rsplit('-', 2)
            try:
                srpmpo = syum.pkgSack.searchNevra(name=sname, ver=sver, rel=srel)[0]
                if not srpmpo in srpmpolist:
                    srpmpolist.append(srpmpo)
            except IndexError:
                print >> sys.stderr, "Error: Cannot find a source rpm for %s" % srpm
                sys.exit(1)

        # do the downloads
        pkgdir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'),
            self.config.get('default', 'flavor'), 'source', 'SRPMS')

        if not os.path.exists(pkgdir):
            os.makedirs(pkgdir)

        for pkg in srpmpolist:
            repo = syum.repos.getRepo(pkg.repoid)
            remote = pkg.relativepath
            local = os.path.basename(remote)
            local = os.path.join(self.config.get('default', 'cachedir'), local)
            if os.path.exists(local) and self.verifyCachePkg(pkg, local):
                self.logger.debug("%s already exists and appears to be complete" % local)
                if os.path.exists(os.path.join(pkgdir, os.path.basename(remote))) and self.verifyCachePkg(pkg, os.path.join(pkgdir, os.path.basename(remote))):
                    self.logger.debug("%s already exists in tree and appears to be complete" % local)
                else:
                    os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
                continue

            # Disable cache otherwise things won't download
            repo.cache = 0
            self.logger.info('Downloading %s' % os.path.basename(remote))
            pkg.localpath = local # Hack: to set the localpath to what we want.

            # do a little dance for file:// repos...
            path = repo.getPackage(pkg)
            if not os.path.exists(local) or not os.path.samefile(path, local):
                shutil.copy2(path, local)

            os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
