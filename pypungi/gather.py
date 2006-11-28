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

class Gather(yum.YumBase):
    def __init__(self, config, pkglist):
        # Create a yum object to use
        yum.YumBase.__init__(self)
        self.doConfigSetup(fn=config.get('default', 'yumconf'))
        self.cleanMetadata() # clean metadata that might be in the cache from previous runs
        self.cleanSqlite() # clean metadata that might be in the cache from previous runs
        self.doRepoSetup()
        if config.get('default', 'arch') == 'i386':
            arches = yum.rpmUtils.arch.getArchList('i686')
        else:
            arches = yum.rpmUtils.arch.getArchList(config.get('default', 'arch'))
        self.doSackSetup(arches)
        self.logger = yum.logging.getLogger("yum.verbose.pungi")
        self.config = config
        self.pkglist = pkglist
        self.polist = []

    def getPackageDeps(self, po):
        """Return the dependencies for a given package, as well
           possible solutions for those dependencies.
           
           Returns the deps as a list"""


        if not self.config.has_option('default', 'quiet'):
            self.logger.info('Checking deps of %s.%s' % (po.name, po.arch))

        reqs = po.requires;
        pkgresults = {}

        for req in reqs:
            (r,f,v) = req
            if r.startswith('rpmlib('):
                continue

            provides = self.whatProvides(r, f, v)
            for provide in provides.returnNewestByNameArch():
                if not pkgresults.has_key(provide):
                    pkgresults[provide] = None

        return pkgresults.keys()

    def getPackageObjects(self):
        """Cycle through the list of packages, get package object
           matches, and resolve deps.

           Returns a list of package objects"""


        unprocessed_pkgs = {} # list of packages yet to depsolve ## Use dicts for speed
        final_pkgobjs = {} # The final list of package objects

        for pkg in self.pkglist: # cycle through our package list and get repo matches
            matches = self.pkgSack.searchNevra(name=pkg)
            mysack = yum.packageSack.ListPackageSack(matches)
            
            for match in mysack.returnNewestByNameArch():
                unprocessed_pkgs[match] = None

        if not self.config.has_option('default', 'quiet'):
            for pkg in unprocessed_pkgs.keys():
                self.logger.info('Found %s.%s' % (pkg.name, pkg.arch))

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
                                             self.config.get('default', 'arch'), self.config.get('default', 'osdir'),
                                             self.config.get('default', 'product_path')) 

        if not os.path.exists(pkgdir):
            os.makedirs(pkgdir)

        for pkg in self.polist:
            repo = self.repos.getRepo(pkg.repoid)
            remote = pkg.returnSimple('relativepath')
            local = os.path.basename(remote)
            local = os.path.join(self.config.get('default', 'cachedir'), local)
            if (os.path.exists(local) and
                str(os.path.getsize(local)) == pkg.returnSimple('packagesize')):

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


def main():
# This is used for testing the module
    (opts, args) = get_arguments()

    pkglist = get_packagelist(opts.comps)

    if not os.path.exists(opts.destdir):
        try:
            os.makedirs(opts.destdir)
        except OSError, e:
            print >> sys.stderr, "Error: Cannot create destination dir %s" % opts.destdir
            sys.exit(1)

    if not os.path.exists(opts.cachedir):
        try:
            os.makedirs(opts.cachedir)
        except OSError, e:
            print >> sys.stderr, "Error: Cannot create cache dir %s" % opts.cachedir
            sys.exit(1)

    mygather = Gather(opts, pkglist)
    mygather.getPackageObjects()
    mygather.downloadPackages()


if __name__ == '__main__':
    from optparse import OptionParser
    import sys

    def get_arguments():
    # hack job for now, I'm sure this could be better for our uses
        usage = "usage: %s [options]" % sys.argv[0]
        parser = OptionParser(usage=usage)
        parser.add_option("--destdir", default=".", dest="destdir",
          help='destination directory (defaults to current directory)')
        parser.add_option("--cachedir", default="./cache", dest="cachedir",
          help='cache directory (defaults to cache subdir of current directory)')
        parser.add_option("--comps", default="comps.xml", dest="comps",
          help='comps file to use')
        parser.add_option("--yumconf", default="yum.conf", dest="yumconf",
          help='yum config file to use')
        parser.add_option("--arch", default="i386", dest="arch",
          help='Base arch to use')
        parser.add_option("-q", "--quiet", default=False, action="store_true",
          help="Output as little as possible")



        (opts, args) = parser.parse_args()
        #if len(opts) < 1:
        #    parser.print_help()
        #    sys.exit(0)
        return (opts, args)

    def get_packagelist(myComps):
    # Get the list of packages from the comps file
        try:
            compsobj = yum.comps.Comps()
            compsobj.add(myComps)

        except IOError:
            print >> sys.stderr, "gather.py: No such file:\'%s\'" % opts.comps
            sys.exit(1)

        pkglist = []
        for group in compsobj.groups:
            pkglist += group.packages
        return pkglist

    main()
