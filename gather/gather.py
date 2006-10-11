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
from optparse import OptionParser

def create_yumobj(yumconf):
# Create a yum object to act upon
    myYum = yum.yumBase()
    myYum.doConfigSetup(fn=yumconf)
    myYum.doRepoSetup()
    return myYum

def main():
# This is used for testing the module
    usage = "usage: %s [options]" % sys.argv[0]
    parser = OptionParser(usage=usage)
    parser.add_option("--destdir", default=".", dest="destdir",
      help='destination directory (defaults to current directory)')
    parser.add_option("--comps", default="comps.xml", dest="comps",
      help='comps file to use')
    parser.add_option("--yumconf", default="yum.conf", dest="yumconf",
      help='yum config file to use')
    (opts, args) = parser.parse_args()


    try:
        compsobj = yum.comps.Comps()
        compsobj.add(opts.comps)

        pkglist = []
        for group in compsobj.groups:
            pkglist += group.packages
        print pkglist

    except IOError:
        print >> sys.stderr, "gather.py: No such file:\'%s\'" % opts.comps
        sys.exit(1)

if __name__ == '__main__':
    main()

