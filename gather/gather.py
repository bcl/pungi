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

def create_yumobj(yumconf):
# Create a yum object to act upon
    myYum = yum.yumBase()
    myYum.doConfigSetup(fn=yumconf)
    myYum.doRepoSetup()
    myYum.doSackSetup()
    return myYum

def download_packages(yumobj, pkglist):
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
