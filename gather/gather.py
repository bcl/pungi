#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
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

class Gather(yum.YumBase):
    def __init__(self, opts, pkglist):
        # Create a yum object to use
        yum.YumBase.__init__(self)
        self.doConfigSetup(fn=opts.yumconf)
        self.doRepoSetup()
        self.doSackSetup()
        self.logger = yum.logging.getLogger("yum.verbose.fist")
        self.opts = opts
        self.pkglist = pkglist
        self.polist = []

    def findDeps(self, po):
        """Return the dependencies for a given package, as well
           possible solutions for those dependencies.
           
           Returns the deps as a list"""


        if not self.opts.quiet:
            self.logger.info('Checking deps of %s' % po.name)

        reqs = po.requires;
        reqs.sort()
        pkgresults = []

        for req in reqs:
            (r,f,v) = req
            if r.startswith('rpmlib('):
                continue

            pkgresults.extend(list(self.whatProvides(r, f, v)))

        return pkgresults

    def getPackageObjects(self):
        """Cycle through the list of packages, get package object
           matches, and resolve deps.

           Returns a list of package objects"""


        unprocessed_pkgs = [] # list of packages yet to depsolve
        final_pkgobjs = [] # The final list of package objects

        for pkg in self.pkglist: # cycle through our package list and get repo matches
            unprocessed_pkgs.extend(self.pkgSack.searchNevra(name=pkg)) 

        if len(unprocessed_pkgs) == 0:
            raise yum.Errors.MiscError, 'No packages found to download.'


        while len(unprocessed_pkgs) > 0: # Our fun loop
            for pkg in unprocessed_pkgs:
                final_pkgobjs.append(pkg) # Add the pkg to our final list
                deplist = self.findDeps(pkg) # Get the deps of our package
                unprocessed_pkgs.remove(pkg) # Clear the package out of our todo list.

                for dep in deplist: # Cycle through deps, if we don't already have it, add it.
                    if not dep in unprocessed_pkgs and not dep in final_pkgobjs:
                        unprocessed_pkgs.append(dep)

        self.polist = final_pkgobjs

    def downloadPackages(self):
        """Cycle through the list of package objects and
           download them from their respective repos."""


        if not self.opts.quiet:
            downloads = []
            for pkg in self.polist:
                downloads.append(pkg.name)
            self.logger.info("Download list: %s" % downloads)

        pkgdir = os.path.join(self.opts.destdir, 'tree') # Package location within destdir, name subject to change/config
        if not os.path.exists(pkgdir):
            os.makedirs(pkgdir)

        for pkg in self.polist:
            repo = self.repos.getRepo(pkg.repoid)
            remote = pkg.returnSimple('relativepath')
            local = os.path.basename(remote)
            local = os.path.join(self.opts.cachedir, local)
            if (os.path.exists(local) and
                str(os.path.getsize(local)) == pkg.returnSimple('packagesize')):

                if not self.opts.quiet:
                    self.logger.info("%s already exists and appears to be complete" % local)
                os.link(local, os.path.join(pkgdir, os.path.basename(remote)))
                continue

            # Disable cache otherwise things won't download
            repo.cache = 0
            if not self.opts.quiet:
                self.logger.info('Downloading %s' % os.path.basename(remote))
            pkg.localpath = local # Hack: to set the localpath to what we want.
            repo.getPackage(pkg) 
            os.link(local, os.path.join(pkgdir, os.path.basename(remote)))


def main():
# This is used for testing the module
    (opts, args) = get_arguments()

    pkglist = get_packagelist(opts.comps)
    print pkglist

    if not os.path.exists(opts.destdir):
        try:
            os.makedirs(opts.destdir)
        except OSError, e:
            print >> sys.stderr, "Error: Cannot destination cache dir %s" % opts.destdir
            sys.exit(1)

    if not os.path.exists(opts.cachedir):
        try:
            os.mkdirs(opts.cachedir)
        except OSError, e:
            print >> sys.stderr, "Error: Cannot create cache dir %s" % opts.destdir
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
