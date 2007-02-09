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

class Gather(yum.YumBase):
    def __init__(self, config, pkglist):
        # Create a yum object to use
        yum.YumBase.__init__(self)
        self.doConfigSetup(fn=config.get('default', 'yumconf'), debuglevel=6, errorlevel=6, root="/tmp")
        self.cleanMetadata() # clean metadata that might be in the cache from previous runs
        self.cleanSqlite() # clean metadata that might be in the cache from previous runs
        self.doRepoSetup()
        self.doTsSetup()
        self.doRpmDBSetup()
        if config.get('default', 'arch') == 'i386':
            arches = yum.rpmUtils.arch.getArchList('i686')
            self.compatarch = 'i686'
        elif config.get('default', 'arch') == 'ppc':
            arches = yum.rpmUtils.arch.getArchList('ppc64')
            self.compatarch = 'ppc64'
        else:
            arches = yum.rpmUtils.arch.getArchList(config.get('default', 'arch'))
            self.compatarch = config.get('default', 'arch')
        self.doSackSetup(arches)
        self.doSackFilelistPopulate()
        self.logger = yum.logging.getLogger("yum.verbose.pungi")
        self.config = config
        self.pkglist = pkglist
        self.polist = []
        self.srpmlist = []
        self.resolved_deps = {} # list the deps we've already resolved, short circuit.

    def _provideToPkg(self, req): #this is stolen from Anaconda
            bestlist = None
            (r, f, v) = req

            satisfiers = []
            for po in self.whatProvides(r, f, v):
                # if we already have something installed which does the provide
                # then that's obviously the one we want to use.  this takes
                # care of the case that we select, eg, kernel-smp and then
                # have something which requires kernel
                if self.tsInfo.getMembers(po.pkgtup):
                    return [po]
                if po not in satisfiers:
                    satisfiers.append(po)

            if satisfiers:
                bestlist = self.bestPackagesFromList(satisfiers, arch=self.compatarch)
                return bestlist
            return None

    def getPackageDeps(self, po):
        """Return the dependencies for a given package, as well
           possible solutions for those dependencies.
           
           Returns the deps as a list"""


        if not self.config.has_option('default', 'quiet'):
            self.logger.info('Checking deps of %s.%s' % (po.name, po.arch))

        reqs = po.requires
        provs = po.provides
        pkgresults = {}

        for req in reqs:
            if self.resolved_deps.has_key(req):
                continue
            (r,f,v) = req
            if r.startswith('rpmlib(') or r.startswith('config('):
                continue
            if req in provs:
                continue

            deps = self._provideToPkg(req)
            if deps is None:
                self.logger.warning("Unresolvable dependency %s in %s" % (r, po.name))
                continue

            for dep in deps:
                if not pkgresults.has_key(dep):
                    pkgresults[dep] = None
                    self.tsInfo.addInstall(dep)
           
            self.resolved_deps[req] = None

        return pkgresults.keys()

    def getPackageObjects(self):
        """Cycle through the list of packages, get package object
           matches, and resolve deps.

           Returns a list of package objects"""


        unprocessed_pkgs = {} # list of packages yet to depsolve ## Use dicts for speed
        final_pkgobjs = {} # The final list of package objects

        # Search repos for things in our manifest, supports globs
        (exactmatched, matched, unmatched) = yum.packages.parsePackages(self.pkgSack.returnPackages(), self.pkglist, casematch=1)
        matches = exactmatched + matched

        # Get the newest results from the search
        mysack = yum.packageSack.ListPackageSack(matches)
        for match in mysack.returnNewestByNameArch():
            unprocessed_pkgs[match] = None
            self.tsInfo.addInstall(match)

        if not self.config.has_option('default', 'quiet'):
            for pkg in unprocessed_pkgs.keys():
                self.logger.info('Found %s.%s' % (pkg.name, pkg.arch))

        for pkg in unmatched:
            self.logger.warn('Could not find a match for %s' % pkg)

        if len(unprocessed_pkgs) == 0:
            raise yum.Errors.MiscError, 'No packages found to download.'

        while len(unprocessed_pkgs) > 0: # Our fun loop
            for pkg in unprocessed_pkgs.keys():
                if not final_pkgobjs.has_key(pkg):
                    final_pkgobjs[pkg] = None # Add the pkg to our final list
                deplist = self.getPackageDeps(pkg) # Get the deps of our package

                for dep in deplist: # Cycle through deps, if we don't already have it, add it.
                    if not unprocessed_pkgs.has_key(dep) and not final_pkgobjs.has_key(dep):
                        unprocessed_pkgs[dep] = None

                del unprocessed_pkgs[pkg] # Clear the package out of our todo list.

        self.polist = final_pkgobjs.keys()

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


        if not self.config.has_option('default', 'quiet'):
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
            repo = self.repos.getRepo(pkg.repoid)
            remote = pkg.relativepath
            local = os.path.basename(remote)
            local = os.path.join(self.config.get('default', 'cachedir'), local)
            if (os.path.exists(local) and
                str(os.path.getsize(local)) == pkg.packagesize):

                if not self.config.has_option('default', 'quiet'):
                    self.logger.info("%s already exists and appears to be complete" % local)
                os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
                continue

            # Disable cache otherwise things won't download
            repo.cache = 0
            if not self.config.has_option('default', 'quiet'):
                self.logger.info('Downloading %s' % os.path.basename(remote))
            pkg.localpath = local # Hack: to set the localpath to what we want.

            # do a little dance for file:// repos...
            path = repo.getPackage(pkg)
            if not os.path.exists(local) or not os.path.samefile(path, local):
                shutil.copy2(path, local)
 
            os.link(local, os.path.join(pkgdir, os.path.basename(remote)))


    def downloadSRPMs(self):
        """Cycle through the list of srpms and
           find the package objects for them, Then download them."""


        srpmpolist = []

        # Work around for yum bug
        for sack in self.pkgSack.sacks.values():
            sack.excludes = {}

        self.pkgSack.excludes = {}

        # We need to reset the yum object
        self.pkgSack = None

        # Setup the sack with just src arch
        self.doSackSetup(archlist=['src'])

        for srpm in self.srpmlist:
            (sname, sver, srel) = srpm.rsplit('-', 2)
            try:
                srpmpo = self.pkgSack.searchNevra(name=sname, ver=sver, rel=srel)[0]
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
            repo = self.repos.getRepo(pkg.repoid)
            remote = pkg.relativepath
            local = os.path.basename(remote)
            local = os.path.join(self.config.get('default', 'cachedir'), local)
            if os.path.exists(local) and str(os.path.getsize(local)) == pkg.packagesize:

                if not self.config.has_option('default', 'quiet'):
                    self.logger.info("%s already exists and appears to be complete" % local)
                if os.path.exists(os.path.join(pkgdir, os.path.basename(remote))) and str(os.path.getsize(os.path.join(pkgdir, os.path.basename(remote)))) == pkg.packagesize:
                    if not self.config.has_option('default', 'quiet'):
                        self.logger.info("%s already exists in tree and appears to be complete" % local)
                else:
                    os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
                continue

            # Disable cache otherwise things won't download
            repo.cache = 0
            if not self.config.has_option('default', 'quiet'):
                self.logger.info('Downloading %s' % os.path.basename(remote))
            pkg.localpath = local # Hack: to set the localpath to what we want.

            # do a little dance for file:// repos...
            path = repo.getPackage(pkg)
            if not os.path.exists(local) or not os.path.samefile(path, local):
                shutil.copy2(path, local)

            os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
