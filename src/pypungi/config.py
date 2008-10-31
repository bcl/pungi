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
import time
import yum

from ConfigParser import SafeConfigParser

class Config(SafeConfigParser):
    def __init__(self):
        SafeConfigParser.__init__(self)

        self.add_section('default')

        self.set('default', 'osdir', 'os')
        self.set('default', 'sourcedir', 'source')
        self.set('default', 'debugdir', 'debug')
        self.set('default', 'isodir', 'iso')
        self.set('default', 'relnotefilere', 'GPL README-BURNING-ISOS-en_US.txt ^RPM-GPG')
        self.set('default', 'relnotedirre', '')
        self.set('default', 'relnotepkgs', 'fedora-release fedora-release-notes')
        self.set('default', 'product_path', 'Packages')
        self.set('default', 'cachedir', '/var/cache/pungi')
        self.set('default', 'arch', yum.rpmUtils.arch.getBaseArch(os.uname()[4]))
        self.set('default', 'name', 'Fedora')
        self.set('default', 'iso_basename', 'Fedora')
        self.set('default', 'version', time.strftime('%Y%m%d', time.localtime()))
        self.set('default', 'flavor', '')
        self.set('default', 'destdir', os.getcwd())
        self.set('default', 'bugurl', 'https://bugzilla.redhat.com')
        self.set('default', 'cdsize', '650.0')
        self.set('default', 'debuginfo', "True")

