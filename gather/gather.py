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

import sys
import yum

class Gather(yum.YumBase):
    def __init__(self, opts):
        yum.YumBase.__init__(self)
        self.logger = logging.getLogger("yum.verbose.fist")
        self.opts = opts

    def getPackageObjects(self)

    def findDeps(self, po):
        """Return the dependencies for a given package, as well
           possible solutions for those dependencies.
           
           Returns the deps as a dict  of:
            dict[reqs] = [list of satisfying pkgs]"""


        reqs = po.returnPrco('requires');
        reqs.sort()
        pkgresults = {}

        for req in reqs:
            (r,f,v) = req
            if r.startswith('rpmlib('):
                continue

            pkgresults[req] = list(self.whatProvides(r, f, v))

        return pkgresults

    def downloadPackages(self, polist):
        """Cycle through the list of package objects and
           download them from their respective repos."""


        for pkg in polist:
            repo = self.repos.getRepo(pkg.repoid)
            remote = pkg.returnSimple('relativepath')
            local = os.path.basename(remote)
            local = os.path.join(opts.destdir, local)
            if (os.path.exists(local) and
                str(os.path.getsize(local)) == pkg.returnSimple('packagesize')):

                if not opts.quiet:
                    self.logger.info("%s already exists and appears to be complete" % local)
                continue

            # Disable cache otherwise things won't download
            repo.cache = 0
            if not opts.quiet:
                self.logger.info('Downloading %s' % os.path.basename(remote))
            pkg.localpath = local # Hack: to set the localpath to what we want.
            repo.getPackage(pkg) 


def create_yumobj(yumconf):
# Create a yum object to act upon.  This may move to a higher
# level file and get passed to this module.
    myYum = yum.yumBase()
    myYum.doConfigSetup(fn=yumconf)
    myYum.doRepoSetup()
    myYum.doSackSetup()
    return myYum

def download_packages(yumobj, pkglist):
# for now a simple function to download packages.
# Needed are ways to define where to put the packages,
# cleaning up multiple returns from searching
    pkgobjs = []
    for pkg in pkglist:
        pkgobjs.extend(yumobj.pkgSack.searchNevra(name=pkg))
    for pkgobj in pkgobjs:
        pkgobj.repo.getPackage(pkgobj)

def main():
# This is used for testing the module
    (opts, args) = get_arguments()
    try:
        compsobj = yum.comps.Comps()
        compsobj.add(opts.comps)

        print get_packagelist(compsobj)

    except IOError:
        print >> sys.stderr, "gather.py: No such file:\'%s\'" % opts.comps
        sys.exit(1)

if __name__ == '__main__':
    from optparse import OptionParser
    def get_arguments():
    # hack job for now, I'm sure this could be better for our uses
        usage = "usage: %s [options]" % sys.argv[0]
        parser = OptionParser(usage=usage)
        parser.add_option("--destdir", default=".", dest="destdir",
          help='destination directory (defaults to current directory)')
        parser.add_option("--comps", default="comps.xml", dest="comps",
          help='comps file to use')
        parser.add_option("--yumconf", default="yum.conf", dest="yumconf",
          help='yum config file to use')


        (opts, args) = parser.parse_args()
        #if len(opts) < 1:
        #    parser.print_help()
        #    sys.exit(0)
        return (opts, args)

    def get_packagelist(myComps):
    # Get the list of packages from the comps file
        pkglist = []
        for group in myComps.groups:
            pkglist += group.packages
        return pkglist
    main()
