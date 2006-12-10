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
#sys.path.append('/usr/lib/anaconda-runtime') # use our patched splittree for now
import splittree
import shutil

class Pungi:
    def __init__(self, config):
        self.config = config
        self.prodpath = 'Fedora' # Probably should be defined elsewhere
        self.topdir = os.path.join(self.config.get('default', 'destdir'), 
                                   self.config.get('default', 'version'), 
                                   self.config.get('default', 'arch'), 
                                   'os')

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
        discinfofile = os.path.join(self.topdir, '.discinfo') # we use this a fair amount
        mkisofsargs = '-v -U -J -R -T -V' # common mkisofs flags
        bootargs = ''
        x86bootargs = '-b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table'
        ia64bootargs = '-b images/boot.img -no-emul-boot'
        ppcbootargs = '' # Boy, it would be nice if somebody who understood ppc helped out here...
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
            os.symlink('%s-disc1/repodata' % self.topdir, os.path.join(self.topdir, 'repodata'))

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

            os.unlink(os.path.join(self.topdir, 'repodata')) # remove our temp symlink and move the orig repodata back
            shutil.move(os.path.join(self.config.get('default', 'destdir'), 
                'repodata-%s' % self.config.get('default', 'arch')), os.path.join(self.topdir, 'repodata'))


def main():
# This is used for testing the module
    (opts, args) = get_arguments()

    if not os.path.exists(os.path.join(opts.destdir, opts.version, 'os')):
        print >> sys.stderr, "Error: Cannot read top dir %s" % os.path.join(opts.destdir, opts.version, 'os')
        sys.exit(1)

    myPungi = Pungi(opts)
    myPungi.doBuildinstall()
    myPungi.doPackageorder()
    myPungi.doSplittree()
    myPungi.doCreateSplitrepo()
    myPungi.doCreateIsos()


if __name__ == '__main__':
    from optparse import OptionParser
    import sys

    def get_arguments():
    # hack job for now, I'm sure this could be better for our uses
        usage = "usage: %s [options]" % sys.argv[0]
        parser = OptionParser(usage=usage)
        parser.add_option("--destdir", default=".", dest="destdir",
          help='Directory that contains the package set')
        parser.add_option("--comps", default="comps.xml", dest="comps",
          help='comps file to use')
        parser.add_option("--arch", default="i386", dest="arch",
          help='Base arch to use')
        parser.add_option("--version", default="test", dest="version",
          help='Version of the spin')
        parser.add_option("--discs", default="5", dest="discs",
          help='Number of discs to spin')
        parser.add_option("-q", "--quiet", default=False, action="store_true",
          help="Output as little as possible")



        (opts, args) = parser.parse_args()
        #if len(opts) < 1:
        #    parser.print_help()
        #    sys.exit(0)
        return (opts, args)

    main()
