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
    def __init__(self, opts):
        self.opts = opts
        self.prodpath = 'Fedora' # Probably should be defined elsewhere
        self.topdir = os.path.join(self.opts.destdir, self.opts.version, self.opts.arch, 'os')

    def doBuildinstall(self):
        # buildinstall looks for a comps file in base/ for now, copy it into place
        os.makedirs(os.path.join(self.topdir, self.prodpath, 'base'))
        shutil.copy(self.opts.comps, os.path.join(self.topdir, self.prodpath, 'base', 'comps.xml'))
        args = '--product "Fedora" --version %s --release "%s" --prodpath %s %s' % (self.opts.version, 
               'Fedora %s' % self.opts.version, self.prodpath, self.topdir)
        os.system('/usr/lib/anaconda-runtime/buildinstall %s' % args)

    def doPackageorder(self):
        os.system('/usr/lib/anaconda-runtime/pkgorder %s %s %s > %s' % (self.topdir, 
                                                                        self.opts.arch, 
                                                                        self.prodpath, 
                                                                        os.path.join(self.opts.destdir, 'pkgorder-%s' % self.opts.arch)))

    def doSplittree(self):
        timber = splittree.Timber()
        timber.arch = self.opts.arch
        timber.total_discs = self.opts.discs
        timber.bin_discs = self.opts.discs
        timber.src_discs = 0
        timber.release_str = 'Fedora %s' % self.opts.version
        timber.package_order_file = os.path.join(self.opts.destdir, 'pkgorder-%s' % self.opts.arch)
        timber.dist_dir = self.topdir
        timber.src_dir = os.path.join(self.opts.destdir, self.opts.version, 'source', 'SRPMS')
        timber.product_path = self.prodpath
        #timber.reserve_size =  

        output = timber.main()
        for line in output:
            print line

    def doCreateSplitrepo(self):
        discinfo = open('%s-disc1/.discinfo' % self.topdir, 'r').readlines()
        mediaid = discinfo[0].rstrip('\n')
        args = '-g %s --baseurl=media://%s --outputdir=%s-disc1 --basedir=%s-disc1 --split %s-disc?' % \
                (os.path.join(self.topdir, 'repodata', 'comps.xml'), mediaid, self.topdir, self.topdir, self.topdir) 
        os.system('/usr/bin/createrepo %s' % args)

    def doCreateIsos(self):
        mkisofsargs = '-v -U -J -R -T -V' # common mkisofs flags
        bootargs = ''
        isodir = os.path.join(self.opts.destdir, self.opts.version, self.opts.arch, 'iso')
        os.makedirs(isodir)
        for disc in range(1, self.opts.discs + 1): # cycle through the CD isos
            volname = '"%s %s %s Disc %s"' % ('Fedora', self.opts.version, self.opts.arch, disc) # hacky :/
            isoname = 'Fedora-%s-%s-disc%s.iso' % (self.opts.version, self.opts.arch, disc)
            if disc == 1: # if this is the first disc, we want to set boot flags
                if self.opts.arch == 'i386' or self.opts.arch == 'x86_64':
                    bootargs = '-b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table'
                elif self.opts.arch == 'ppc':
                    # Boy, it would be nice if somebody who understood ppc helped out here...
                    bootargs = ''
            else:
                bootargs = '' # clear out any existing bootargs

            os.system('mkisofs %s %s %s -o %s/%s %s' % (mkisofsargs,
                                                        volname,
                                                        bootargs,
                                                        isodir,
                                                        isoname,
                                                        os.path.join('%s-disc%s' % (self.topdir, disc))))
            os.system('cd %s; sha1sum %s >> SHA1SUM' % (isodir, isoname))

        if self.opts.discs > 1: # We've asked for more than one disc, make a DVD image
            # move the main repodata out of the way to use the split repodata
            shutil.move(os.path.join(self.topdir, 'repodata'), os.path.join(self.opts.destdir, 'repodata-%s' % self.opts.arch))
            os.symlink('%s-disc1/repodata' % self.topdir, os.path.join(self.topdir, 'repodata'))

            volname = '"%s %s %s DVD"' % ('Fedora', self.opts.version, self.opts.arch)
            isoname = 'Fedora-%s-%s-DVD.iso' % (self.opts.version, self.opts.arch)
            if self.opts.arch == 'i386' or self.opts.arch == 'x86_64':
                bootargs = '-b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table'
            elif self.opts.arch == 'ppc':
                # Boy, it would be nice if somebody who understood ppc helped out here...
                bootargs = ''
            
            os.system('mkisofs %s %s %s -o %s/%s %s' % (mkisofsargs,
                                                        volname,
                                                        bootargs,
                                                        isodir,
                                                        isoname,
                                                        os.path.join('%s-disc1' % self.topdir)))
            os.system('cd %s; sha1sum %s >> SHA1SUM' % (isodir, isoname))

            os.unlink(os.path.join(self.topdir, 'repodata')) # remove our temp symlink and move the orig repodata back
            shutil.move(os.path.join(self.opts.destdir, 'repodata-%s' % self.opts.arch), os.path.join(self.topdir, 'repodata'))


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
