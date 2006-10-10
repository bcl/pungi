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
import yum.comps

def get_packagelist(myComps):
    pkglist = []
    for group in myComps.groups:
        pkglist += group.packages
    return pkglist


def main():
    try:
        print sys.argv[1]
        compsobj = yum.comps.Comps()
        for srcfile in sys.argv[1:]:
            compsobj.add(srcfile)

        print get_packagelist(compsobj)

    except IOError:
        print >> sys.stderr, "gather.py: No such file:\'%s\'" % sys.argv[1]
        sys.exit(1)

if __name__ == '__main__':
    main()

