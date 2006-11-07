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

import os
import gather
import pungi
import yum

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

    mygather = gather.Gather(opts, pkglist)
    mygather.getPackageObjects()
    mygather.downloadPackages()

    mypungi = pungi.Pungi(opts)
    mypungi.doBuildinstall()
    mypungi.doPackageorder()
    mypungi.doSplittree()
    mypungi.doCreateSplitrepo()


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
        parser.add_option("--version", default="test", dest="version",
          help='Version of the spin')
        parser.add_option("--discs", default=5, type="int", dest="discs",
          help='Number of discs to spin')
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
            print >> sys.stderr, "pungi: No such file:\'%s\'" % opts.comps
            sys.exit(1)

        pkglist = []
        for group in compsobj.groups:
            pkglist += group.packages
        return pkglist

    main()
