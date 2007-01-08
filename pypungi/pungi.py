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
import sys
sys.path.append('/usr/lib/anaconda-runtime')
import splittree
import shutil
import re

class Pungi:
    def __init__(self, config):
        self.config = config
        self.prodpath = 'Fedora' # Probably should be defined elsewhere
        self.topdir = os.path.join(self.config.get('default', 'destdir'), 
                                   self.config.get('default', 'version'), 
                                   self.config.get('default', 'arch'), 
                                   'os')
        self.workdir = os.path.join(self.config.get('default', 'destdir'), 
                                    'work',
                                    self.config.get('default', 'arch'))
        self.common_files = []


    def doBuildinstall(self):
        # buildinstall looks for a comps file in base/ for now, copy it into place
        os.makedirs(os.path.join(self.topdir, self.config.get('default', 'product_path'), 'base'))
        shutil.copy(self.config.get('default', 'comps'), os.path.join(self.topdir, 
            self.config.get('default', 'product_path'), 'base', 'comps.xml'))
        args = '--product "%s" --version %s --release "%s" --prodpath %s %s' % (self.config.get('default', 'product_name'),
            self.config.get('default', 'version'), '%s %s' % (self.config.get('default', 'product_name'), 
            self.config.get('default', 'version')), self.config.get('default', 'product_path'), self.topdir)
        os.system('/usr/lib/anaconda-runtime/buildinstall %s' % args)

    def doPackageorder(self):
        os.system('/usr/lib/anaconda-runtime/pkgorder %s %s %s > %s' % (self.topdir, self.config.get('default', 'arch'), 
            self.config.get('default', 'product_path'), os.path.join(self.config.get('default', 'destdir'), 
            'pkgorder-%s' % self.config.get('default', 'arch'))))

    def doGetRelnotes(self):
        docsdir = os.path.join(self.workdir, 'docs')
        relnoterpms = self.config.get('default', 'relnotepkgs').split()

        fileres = []
        for pattern in self.config.get('default', 'relnotefilere').split():
            fileres.append(re.compile(pattern))

        dirres = []
        for pattern in self.config.get('default', 'relnotedirre').split():
            dirres.append(re.compile(pattern))

        os.makedirs(docsdir)

        # Expload the packages we list as relnote packages
        pkgs = os.listdir(os.path.join(self.topdir, self.config.get('default', 'product_path')))

        for pkg in pkgs:
            pkgname = pkg.rsplit('-', 2)[0]
            for relnoterpm in relnoterpms:
                if pkgname == relnoterpm:
                    output = os.system("pushd %s; rpm2cpio %s |cpio -imud; popd" % 
                                       (docsdir, 
                                        os.path.join(self.topdir, self.config.get('default', 'product_path'), pkg)))

        # Walk the tree for our files
        for dirpath, dirname, filelist in os.walk(docsdir):
            for filename in filelist:
                for regex in fileres:
                    if regex.match(filename) and not os.path.exists(os.path.join(self.topdir, filename)):
                        print "Copying release note file %s" % filename
                        shutil.copy(os.path.join(dirpath, filename), os.path.join(self.topdir, filename))
                        self.common_files.append(filename)

        # Walk the tree for our dirs
        for dirpath, dirname, filelist in os.walk(docsdir):
            for dir in dirname:
                for regex in dirres:
                    if regex.match(dir) and not os.path.exists(os.path.join(self.topdir, dir)):
                        print "Copying release note dir %s" % dir
                        shutil.copytree(os.path.join(dirpath, dir), os.path.join(self.topdir, dir))
        

    def doSplittree(self):
        timber = splittree.Timber()
        timber.arch = self.config.get('default', 'arch')
        timber.total_discs = self.config.getint('default', 'discs')
        timber.bin_discs = self.config.getint('default', 'discs')
        timber.src_discs = 0
        timber.release_str = '%s %s' % (self.config.get('default', 'product_name'), self.config.get('default', 'version'))
        timber.package_order_file = os.path.join(self.config.get('default', 'destdir'), 'pkgorder-%s' % self.config.get('default', 'arch'))
        timber.dist_dir = self.topdir
        timber.src_dir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 'source', 'SRPMS')
        timber.product_path = self.config.get('default', 'product_path')
        timber.common_files = self.common_files
        #timber.reserve_size =  

        output = timber.main()
        for line in output:
            print line

    def doSplitSRPMs(self):
        timber = splittree.Timber()
        timber.arch = self.config.get('default', 'arch')
        #timber.total_discs = self.config.getint('default', 'discs')
        #timber.bin_discs = self.config.getint('default', 'discs')
        timber.src_discs = self.config.getint('default', 'discs')
        #timber.release_str = '%s %s' % (self.config.get('default', 'product_name'), self.config.get('default', 'version'))
        #timber.package_order_file = os.path.join(self.config.get('default', 'destdir'), 'pkgorder-%s' % self.config.get('default', 'arch'))
        timber.dist_dir = os.path.join(self.config.get('default', 'destdir'), 
                                       self.config.get('default', 'version'), 
                                       'source', 'SRPM')
        timber.src_dir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 'source', 'SRPMS')
        #timber.product_path = self.config.get('default', 'product_path')
        #timber.reserve_size =  
        # Set this ourselves, for creating our dirs ourselves
        timber.src_list = range(1, timber.src_discs + 1)

        # this is stolen from splittree.py in anaconda-runtime.  Blame them if its ugly (:
        for i in range(timber.src_list[0], timber.src_list[-1] + 1):
                os.makedirs("%s-disc%d/SRPMS" % (timber.dist_dir, i))
                timber.linkFiles(timber.dist_dir,
                               "%s-disc%d" %(timber.dist_dir, i),
                               timber.common_files)

        timber.splitSRPMS()
        for line in timber.logfile:
            print line

    def doCreateSplitrepo(self):
        discinfo = open('%s-disc1/.discinfo' % self.topdir, 'r').readlines()
        mediaid = discinfo[0].rstrip('\n')
        args = '-g %s --baseurl=media://%s --outputdir=%s-disc1 --basedir=%s-disc1 --split %s-disc?' % \
                (os.path.join(self.topdir, 'repodata', 'comps.xml'), mediaid, self.topdir, self.topdir, self.topdir) 
        os.system('/usr/bin/createrepo %s' % args)

    def doCreateIsos(self):
        anaruntime = '/usr/lib/anaconda-runtime/boot'
        discinfofile = os.path.join(self.topdir, '.discinfo') # we use this a fair amount
        mkisofsargs = '-v -U -J -R -T -V' # common mkisofs flags
        bootargs = ''
        x86bootargs = '-b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table'
        ia64bootargs = '-b images/boot.img -no-emul-boot'
        ppcbootargs = '-part -hfs -r -l -sysid PPC -hfs-bless "./ppc/mac" -map %s -magic %s -no-desktop -allow-multidot -chrp-boot' % (os.path.join(anaruntime, 'mapping'), os.path.join(anaruntime, 'magic'))
        isodir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 
            self.config.get('default', 'arch'), self.config.get('default', 'isodir'))
        os.makedirs(isodir)
        for disc in range(1, self.config.getint('default', 'discs') + 1): # cycle through the CD isos
            volname = '"%s %s %s Disc %s"' % (self.config.get('default', 'product_name'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'), disc) # hacky :/
            isoname = '%s-%s-%s-disc%s.iso' % (self.config.get('default', 'iso_basename'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'), disc)
            if disc == 1: # if this is the first disc, we want to set boot flags
                if self.config.get('default', 'arch') == 'i386' or self.config.get('default', 'arch') == 'x86_64':
                    bootargs = x86bootargs
                elif self.config.get('default', 'arch') == 'ia64':
                    bootargs = ia64bootargs
                elif self.config.get('default', 'arch') == 'ppc':
                    bootargs = ppcbootargs
            else:
                bootargs = '' # clear out any existing bootargs

            os.system('mkisofs %s %s %s -o %s/%s %s' % (mkisofsargs,
                                                        volname,
                                                        bootargs,
                                                        isodir,
                                                        isoname,
                                                        os.path.join('%s-disc%s' % (self.topdir, disc))))
            os.system('cd %s; sha1sum %s >> SHA1SUM' % (isodir, isoname))
            # implant md5 for mediacheck on all but source arches
            if not self.config.get('default', 'arch') == 'source':
                os.system('/usr/lib/anaconda-runtime/implantisomd5 %s' % os.path.join(isodir, isoname))

        # We've asked for more than one disc, and we're not srpms, so make a DVD image
        if self.config.getint('default', 'discs') > 1 and not self.config.get('default', 'arch') == 'source':
            # backup the main .discinfo to use a split one.  This is an ugly hack :/
            content = open(discinfofile, 'r').readlines()
            shutil.move(discinfofile, os.path.join(self.config.get('default', 'destdir'), 
                '.discinfo-%s' % self.config.get('default', 'arch')))
            content[content.index('ALL\n')] = ','.join([str(x) for x in range(1, self.config.getint('default', 'discs') + 1)]) + '\n'
            open(discinfofile, 'w').writelines(content)
            

            # move the main repodata out of the way to use the split repodata
            shutil.move(os.path.join(self.topdir, 'repodata'), os.path.join(self.config.get('default', 'destdir'), 
                'repodata-%s' % self.config.get('default', 'arch')))
            shutil.copytree('%s-disc1/repodata' % self.topdir, os.path.join(self.topdir, 'repodata'))

            volname = '"%s %s %s DVD"' % (self.config.get('default', 'product_name'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'))
            isoname = '%s-%s-%s-DVD.iso' % (self.config.get('default', 'iso_basename'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'))
            if self.config.get('default', 'arch') == 'i386' or self.config.get('default', 'arch') == 'x86_64':
                bootargs = x86bootargs
            elif self.config.get('default', 'arch') == 'ia64':
                bootargs = ia64bootargs
            elif self.config.get('default', 'arch') == 'ppc':
                bootargs = ppcbootargs
            else:
                bootargs = '' # clear out any existing bootargs
            
            os.system('mkisofs %s %s %s -o %s/%s %s' % (mkisofsargs,
                                                        volname,
                                                        bootargs,
                                                        isodir,
                                                        isoname,
                                                        self.topdir))
            os.system('cd %s; sha1sum %s >> SHA1SUM' % (isodir, isoname))
            os.system('/usr/lib/anaconda-runtime/implantisomd5 %s' % os.path.join(isodir, isoname))

            shutil.move(os.path.join(self.config.get('default', 'destdir'), '.discinfo-%s' % self.config.get('default', 'arch')), discinfofile)

            shutil.rmtree(os.path.join(self.topdir, 'repodata')) # remove our copied repodata
            shutil.move(os.path.join(self.config.get('default', 'destdir'), 
                'repodata-%s' % self.config.get('default', 'arch')), os.path.join(self.topdir, 'repodata'))
