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
import gzip
import pypungi
import logging
import urlgrabber.progress

class CallBack(urlgrabber.progress.TextMeter):
    """A call back function used with yum."""

    def progressbar(self, current, total, name=None):
        return

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
        self.logger.error('foobar')

    def doFileLogSetup(self, uid, logfile):
        # This function overrides a yum function, allowing pungi to control
        # the logging.
        pass

class Gather(pypungi.PungiBase):
    def __init__(self, config, ksparser):
        pypungi.PungiBase.__init__(self, config)
 
        # Set our own logging name space
        self.logger = logging.getLogger('Pungi.Gather')

        # Create the stdout/err streams and only send INFO+ stuff there
        formatter = logging.Formatter('%(name)s:%(levelname)s: %(message)s')
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        self.logger.addHandler(console)

        self.ksparser = ksparser
        self.polist = []
        self.srpmlist = []
        self.resolved_deps = {} # list the deps we've already resolved, short circuit.

        # Create a yum object to use
        self.ayum = PungiYum(config)
        self.ayum.doLoggingSetup(6, 6)
        yumconf = yum.config.YumConf()
        yumconf.debuglevel = 6
        yumconf.errorlevel = 6
        yumconf.cachedir = self.config.get('default', 'cachedir')
        yumconf.persistdir = os.path.join(self.workdir, 'yumlib')
        yumconf.installroot = os.path.join(self.workdir, 'yumroot')
        yumconf.uid = os.geteuid()
        yumconf.cache = 0
        yumconf.failovermethod = 'priority'
        yumvars = yum.config._getEnvVar()
        yumvars['releasever'] = self.config.get('default', 'version')
        yumvars['basearch'] = yum.rpmUtils.arch.getBaseArch(myarch=self.config.get('default', 'arch'))
        yumconf.yumvar = yumvars
        self.ayum._conf = yumconf
        self.ayum.repos.setCacheDir(self.ayum.conf.cachedir)

        arch = self.config.get('default', 'arch')
        if arch == 'i386':
            yumarch = 'athlon'
        elif arch == 'ppc':
            yumarch = 'ppc64'
        elif arch == 'sparc':
            yumarch = 'sparc64v'
        else:
            yumarch = arch

        self.ayum.compatarch = yumarch
        arches = yum.rpmUtils.arch.getArchList(yumarch)
        arches.append('src') # throw source in there, filter it later

        # deal with our repos
        try:
            ksparser.handler.repo.methodToRepo()
        except:
            pass

        for repo in ksparser.handler.repo.repoList:
            self.logger.info('Adding repo %s' % repo.name)
            thisrepo = yum.yumRepo.YumRepository(repo.name)
            thisrepo.name = repo.name
            # add excludes and such here when pykickstart gets them
            if repo.mirrorlist:
                thisrepo.mirrorlist = yum.parser.varReplace(repo.mirrorlist, self.ayum.conf.yumvar)
                self.logger.info('Mirrorlist for repo %s is %s' % (thisrepo.name, thisrepo.mirrorlist))
            else:
                thisrepo.baseurl = yum.parser.varReplace(repo.baseurl, self.ayum.conf.yumvar)
                self.logger.info('URL for repo %s is %s' % (thisrepo.name, thisrepo.baseurl))
            thisrepo.basecachedir = self.ayum.conf.cachedir
            thisrepo.enablegroups = True
            thisrepo.failovermethod = 'priority' # This is until yum uses this failover by default
            thisrepo.exclude = repo.excludepkgs
            thisrepo.includepkgs = repo.includepkgs
            self.ayum.repos.add(thisrepo)
            self.ayum.repos.enableRepo(thisrepo.id)
            self.ayum._getRepos(thisrepo=thisrepo.id, doSetup = True)

        self.ayum.repos.setProgressBar(CallBack())
        self.ayum.repos.callback = CallBack()
        
        # Set the metadata and mirror list to be expired so we always get new ones.
        for repo in self.ayum.repos.listEnabled():
            repo.metadata_expire = 0
            repo.mirrorlist_expire = 0
            if os.path.exists(os.path.join(repo.cachedir, 'repomd.xml')):
                os.remove(os.path.join(repo.cachedir, 'repomd.xml'))

        self.logger.info('Getting sacks for arches %s' % arches)
        self.ayum._getSacks(archlist=arches)

    def _filtersrc(self, po):
        """Filter out package objects that are of 'src' arch."""

        if po.arch == 'src':
            return False

        return True

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
        """Get a list of package names from a ksparser group object

            Returns a list of package names"""

        packages = []

        # Check if we have the group
        if not self.ayum.comps.has_group(group.name):
            self.logger.error("Group %s not found in comps!" % group)
            return packages

        # Get the group object to work with
        groupobj = self.ayum.comps.return_group(group.name)

        # Add the mandatory packages
        packages.extend(groupobj.mandatory_packages.keys())

        # Add the default packages unless we don't want them
        if group.include == 1:
            packages.extend(groupobj.default_packages.keys())

        # Add the optional packages if we want them
        if group.include == 2:
            packages.extend(groupobj.default_packages.keys())
            packages.extend(groupobj.optional_packages.keys())

        # Deal with conditional packages
        # Populate a dict with the name of the required package and value
        # of the package objects it would bring in.  To be used later if
        # we match the conditional.
        for condreq, cond in groupobj.conditional_packages.iteritems():
            pkgs = self.ayum.pkgSack.searchNevra(name=condreq)
            if pkgs:
                pkgs = self.ayum.bestPackagesFromList(pkgs, arch=self.ayum.compatarch)
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

        # First remove the excludes
        self.ayum.conf.exclude.extend(self.ksparser.handler.packages.excludedList)
        self.ayum.excludePackages()
        
        # Always add the core groiup
        self.ksparser.handler.packages.add(['@core'])

        # Check to see if we need the base group
        if self.ksparser.handler.packages.addBase:
            self.ksparser.handler.packages.add(['@base'])

        # Get a list of packages from groups
        for group in self.ksparser.handler.packages.groupList:
            searchlist.extend(self.getPackagesFromGroup(group))

        # Add the adds
        searchlist.extend(self.ksparser.handler.packages.packageList)

        # Make the search list unique
        searchlist = yum.misc.unique(searchlist)

        # Search repos for things in our searchlist, supports globs
        (exactmatched, matched, unmatched) = yum.packages.parsePackages(self.ayum.pkgSack.returnPackages(), searchlist, casematch=1)
        matches = filter(self._filtersrc, exactmatched + matched)

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
                self.logger.warn('Could not find a match for %s in any configured repo' % pkg)

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

    def _downloadPackageList(self, polist, relpkgdir):
        """Cycle through the list of package objects and
           download them from their respective repos."""

        downloads = []
        for pkg in polist:
            downloads.append('%s.%s' % (pkg.name, pkg.arch))
            downloads.sort()
        self.logger.info("Download list: %s" % downloads)

        pkgdir = os.path.join(self.config.get('default', 'destdir'),
                              self.config.get('default', 'version'),
                              self.config.get('default', 'flavor'),
                              relpkgdir)

        # Ensure the pkgdir exists, force if requested, and make sure we clean it out
        pypungi._ensuredir(pkgdir, self.logger, force=self.config.getboolean('default', 'force'), clean=True)

        probs = self.ayum.downloadPkgs(polist)

        if len(probs.keys()) > 0:
            self.logger.error("Errors were encountered while downloading packages.")
            for key in probs.keys():
                errors = yum.misc.unique(probs[key])
                for error in errors:
                    self.logger.error("%s: %s" % (key, error))
            sys.exit(1)

        for po in polist:
            basename = os.path.basename(po.relativepath)

            local = po.localPkg()
            target = os.path.join(pkgdir, basename)

            # Link downloaded package in (or link package from file repo)
            try:
                pypungi._link(local, target, self.logger, force=True)
                continue
            except:
                self.logger.error("Unable to link %s from the yum cache." % po.name)
                sys.exit(1)

        self.logger.info('Finished downloading packages.')

    def downloadPackages(self):
        """Download the package objects obtained in getPackageObjects()."""

        self._downloadPackageList(self.polist,
                                  os.path.join(self.config.get('default', 'arch'),
                                               self.config.get('default', 'osdir'),
                                               self.config.get('default', 'product_path')))

    def makeCompsFile(self):
        """Gather any comps files we can from repos and merge them into one."""

        # get our list of repos
        repos = self.ayum.repos.repos.values()

        compsstub = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">\n<comps>\n'

        closestub = '\n</comps>\n'

        ourcompspath = os.path.join(self.workdir, '%s-%s-comps.xml' % (self.config.get('default', 'name'), self.config.get('default', 'version')))

        ourcomps = open(ourcompspath, 'w')

        ourcomps.write(compsstub)

        # iterate through the list and get what comps we can.
        # Strip the first three lines and the last line of substance off
        # once done, write it to our comps file
        for repo in repos:
            try:
                groupfile = repo.getGroups()
            except yum.Errors.RepoMDError, e:
                self.logger.warn("No group data found for %s" % repo.id)
                pass
            else:
                # Check to see if we got a gzipped comps file
                if groupfile.endswith('.gz'):
                    compslines = gzip.open(groupfile, 'r').readlines()
                else:
                    compslines = open(groupfile, 'r').readlines()
                for line in compslines:
                    if line.startswith('</comps'):
                        end = compslines.index(line)

                for line in compslines:
                    if line.startswith('<comps'):
                        start = compslines.index(line) + 1
                
                ourcomps.writelines(compslines[start:end])

        ourcomps.write(closestub)
        ourcomps.close()

        # Run the xslt filter over our comps file
        compsfilter = ['/usr/bin/xsltproc', '--novalid']
        compsfilter.append('-o')
        compsfilter.append(ourcompspath)
        compsfilter.append('/usr/share/pungi/comps-cleanup.xsl')
        compsfilter.append(ourcompspath)

        pypungi._doRunCommand(compsfilter, self.logger)

    def downloadSRPMs(self):
        """Cycle through the list of srpms and
           find the package objects for them, Then download them."""

        srpmpolist = []

        for srpm in self.srpmlist:
            (sname, sver, srel) = srpm.rsplit('-', 2)
            try:
                srpmpo = self.ayum.pkgSack.searchNevra(name=sname, ver=sver, rel=srel, arch='src')[0]
                if not srpmpo in srpmpolist:
                    srpmpolist.append(srpmpo)
            except IndexError:
                print >> sys.stderr, "Error: Cannot find a source rpm for %s" % srpm
                sys.exit(1)

        # do the downloads
        self._downloadPackageList(srpmpolist, os.path.join('source', 'SRPMS'))
