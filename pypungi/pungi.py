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

import subprocess
import logging
import os
import sys
sys.path.append('/usr/lib/anaconda-runtime')
import splittree
import shutil
import re

log = logging.getLogger("pypungi.pungi")

class Pungi:
    def __init__(self, config):
        self.config = config
        self.prodpath = 'Fedora' # Probably should be defined elsewhere
        self.destdir = self.config.get('default', 'destdir')
        self.archdir = os.path.join(self.destdir,
                                   self.config.get('default', 'version'),
                                   self.config.get('default', 'flavor'),
                                   self.config.get('default', 'arch'))

        self.topdir = os.path.join(self.archdir, 'os')
        self.isodir = os.path.join(self.archdir, self.config.get('default','isodir'))

        self.workdir = os.path.join(self.config.get('default', 'destdir'), 
                                    'work',
                                    self.config.get('default', 'flavor'),
                                    self.config.get('default', 'arch'))

        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

        self.common_files = []
        self.infofile = os.path.join(self.config.get('default', 'destdir'),
                                     '.composeinfo')

    def writeinfo(self, line):
        """Append a line to the infofile in self.infofile"""


        f=open(self.infofile, "a+")
        f.write(line.strip() + "\n")
        f.close()

    def mkrelative(self, subfile):
        """Return the relative path for 'subfile' underneath 'self.destdir'."""


        if subfile.startswith(self.destdir):
            return subfile.replace(self.destdir + os.path.sep, '')

    def _doRunCommand(self, command, rundir='/tmp', output=subprocess.PIPE, error=subprocess.PIPE):
        """Run a command and log the output.  Error out if we get something on stderr"""


        log.info("Running %s" % ' '.join(command))

        p1 = subprocess.Popen(command, cwd=rundir, stdout=output, stderr=error)
        (out, err) = p1.communicate()
        if p1.returncode != 0:
            log.error("Got an error from %s" % command[0])
            log.error(err)
            raise OSError, "Got an error from %s" % command[0]

        log.info(out)

    def doBuildinstall(self):
        """Run anaconda-runtime's buildinstall on the tree."""


        # create repodata for the tree
        createrepo = ['/usr/bin/createrepo']
        createrepo.append('--database')

        createrepo.append('--groupfile')
        createrepo.append(self.config.get('default', 'comps'))

        createrepo.append(self.topdir)

        # run the command
        self._doRunCommand(createrepo, rundir=self.topdir)

        # setup the buildinstall call
        buildinstall = ['/usr/lib/anaconda-runtime/buildinstall']
        #buildinstall.append('TMPDIR=%s' % self.workdir) # TMPDIR broken in buildinstall

        buildinstall.append('--product')
        buildinstall.append(self.config.get('default', 'product_name'))

        if not self.config.get('default', 'flavor') == "":
            buildinstall.append('--variant')
            buildinstall.append(self.config.get('default', 'flavor'))

        buildinstall.append('--version')
        buildinstall.append(self.config.get('default', 'version'))

        buildinstall.append('--release')
        buildinstall.append('"%s %s"' % (self.config.get('default', 'product_name'), self.config.get('default', 'version')))

        buildinstall.append('--prodpath')
        buildinstall.append(self.config.get('default', 'product_path'))

        if self.config.has_option('default', 'bugurl'):
            buildinstall.append('--bugurl')
            buildinstall.append(self.config.get('default', 'bugurl'))

        buildinstall.append(self.topdir)

        # run the command
        self._doRunCommand(buildinstall)

        # write out the tree data for snake
        self.writeinfo('tree: %s' % self.mkrelative(self.topdir))

    def doPackageorder(self):
        """Run anaconda-runtime's pkgorder on the tree, used for splitting media."""


        # non-op for only one disc
        if self.config.getint('default', 'discs') == 1:
            return

        pkgorderfile = open(os.path.join(self.workdir, 'pkgorder-%s' % self.config.get('default', 'arch')), 'w')
        # setup the command
        pkgorder = ['/usr/lib/anaconda-runtime/pkgorder']
        #pkgorder.append('TMPDIR=%s' % self.workdir)
        pkgorder.append(self.topdir)
        pkgorder.append(self.config.get('default', 'arch'))
        pkgorder.append(self.config.get('default', 'product_path'))

        # run the command
        self._doRunCommand(pkgorder, output=pkgorderfile)
        pkgorderfile.close()

    def doGetRelnotes(self):
        """Get extra files from packages in the tree to put in the topdir of
           the tree."""


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

        rpm2cpio = ['/usr/bin/rpm2cpio']
        cpio = ['cpio', '-imud']

        for pkg in pkgs:
            pkgname = pkg.rsplit('-', 2)[0]
            for relnoterpm in relnoterpms:
                if pkgname == relnoterpm:
                    extraargs = [os.path.join(self.topdir, self.config.get('default', 'product_path'), pkg)]
                    try:
                        p1 = subprocess.Popen(rpm2cpio + extraargs, cwd=docsdir, stdout=subprocess.PIPE)
                        (out, err) = subprocess.Popen(cpio, cwd=docsdir, stdin=p1.stdout, stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE).communicate()
                    except:
                        log.error("Got an error from rpm2cpio")
                        log.error(err)
                        raise

                    log.info(out)

        # Walk the tree for our files
        for dirpath, dirname, filelist in os.walk(docsdir):
            for filename in filelist:
                for regex in fileres:
                    if regex.match(filename) and not os.path.exists(os.path.join(self.topdir, filename)):
                        log.info("Copying release note file %s" % filename)
                        shutil.copy(os.path.join(dirpath, filename), os.path.join(self.topdir, filename))
                        self.common_files.append(filename)

        # Walk the tree for our dirs
        for dirpath, dirname, filelist in os.walk(docsdir):
            for directory in dirname:
                for regex in dirres:
                    if regex.match(directory) and not os.path.exists(os.path.join(self.topdir, directory)):
                        log.info("Copying release note dir %s" % directory)
                        shutil.copytree(os.path.join(dirpath, directory), os.path.join(self.topdir, directory))
        

    def doSplittree(self):
        """Use anaconda-runtime's splittree to split the tree into appropriate
           sized chunks."""


        # non-op for only one disc
        if self.config.getint('default', 'discs') == 1:
            return

        timber = splittree.Timber()
        timber.arch = self.config.get('default', 'arch')
        timber.target_size = float(self.config.get('default', 'cdsize')) * 1024 * 1024
        timber.total_discs = self.config.getint('default', 'discs')
        timber.bin_discs = self.config.getint('default', 'discs')
        timber.src_discs = 0
        timber.release_str = '%s %s' % (self.config.get('default', 'product_name'), self.config.get('default', 'version'))
        timber.package_order_file = os.path.join(self.workdir, 'pkgorder-%s' % self.config.get('default', 'arch'))
        timber.dist_dir = self.topdir
        timber.src_dir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 'source', 'SRPMS')
        timber.product_path = self.config.get('default', 'product_path')
        timber.common_files = self.common_files
        #timber.reserve_size =  

        output = timber.main()
        log.info("Output from splittree: %s" % '\n'.join(output))

    def doSplitSRPMs(self):
        """Use anaconda-runtime's splittree to split the srpms into appropriate
           sized chunks."""

        # non-op for only one disc
        if self.config.getint('default', 'discs') == 1:
            return

        timber = splittree.Timber()
        timber.arch = self.config.get('default', 'arch')
        #timber.total_discs = self.config.getint('default', 'discs')
        #timber.bin_discs = self.config.getint('default', 'discs')
        timber.src_discs = self.config.getint('default', 'discs')
        #timber.release_str = '%s %s' % (self.config.get('default', 'product_name'), self.config.get('default', 'version'))
        #timber.package_order_file = os.path.join(self.config.get('default', 'destdir'), 'pkgorder-%s' % self.config.get('default', 'arch'))
        timber.dist_dir = os.path.join(self.config.get('default', 'destdir'),
                                       self.config.get('default', 'version'),
                                       self.config.get('default', 'flavor'),
                                       'source', 'SRPM')
        timber.src_dir = os.path.join(self.config.get('default', 'destdir'),
                                      self.config.get('default', 'version'),
                                      self.config.get('default', 'flavor'),
                                      'source', 'SRPMS')
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
        log.info("splitSRPMS complete")

    def doCreateSplitrepo(self):
        """Create the split metadata for the isos"""


        if self.config.getint('default', 'discs') > 1:
            discinfo = open('%s-disc1/.discinfo' % self.topdir, 'r').readlines()
        else:
            discinfo = open(os.path.join(self.topdir, '.discinfo'), 'r').readlines()
        mediaid = discinfo[0].rstrip('\n')

        # set up the process
        createrepo = ['/usr/bin/createrepo']
        createrepo.append('--database')

        createrepo.append('--groupfile')
        createrepo.append(self.config.get('default', 'comps'))

        createrepo.append('--baseurl')
        createrepo.append('media://%s' % mediaid)

        createrepo.append('--outputdir')
        if self.config.getint('default', 'discs') == 1:
            os.makedirs('%s-disc1' % self.topdir)
        createrepo.append('%s-disc1' % self.topdir)

        createrepo.append('--basedir')
        if self.config.getint('default', 'discs') == 1:
            createrepo.append(self.topdir)
            createrepo.append(self.topdir)
        else:
            createrepo.append('%s-disc1' % self.topdir)

        if self.config.getint('default', 'discs') > 1:
            createrepo.append('--split')

            for disc in range(1, self.config.getint('default', 'discs') + 1):
                createrepo.append('%s-disc%s' % (self.topdir, disc))

        # run the command
        self._doRunCommand(createrepo)

    def doCreateIsos(self):
        """Create isos from the various split directories."""


        isolist=[]
        anaruntime = '/usr/lib/anaconda-runtime/boot'
        discinfofile = os.path.join(self.topdir, '.discinfo') # we use this a fair amount

        os.makedirs(self.isodir)

        # setup the base command
        mkisofs = ['/usr/bin/mkisofs']
        mkisofs.extend(['-v', '-U', '-J', '-R', '-T']) # common mkisofs flags

        x86bootargs = ['-b', 'isolinux/isolinux.bin', '-c', 'isolinux/boot.cat', 
            '-no-emul-boot', '-boot-load-size', '4', '-boot-info-table']

        ia64bootargs = ['-b', 'images/boot.img', '-no-emul-boot']

        ppcbootargs = ['-part', '-hfs', '-r', '-l', '-sysid', 'PPC', '-no-desktop', '-allow-multidot', '-chrp-boot']

        ppcbootargs.append('-map')
        ppcbootargs.append(os.path.join(anaruntime, 'mapping'))

        ppcbootargs.append('-magic')
        ppcbootargs.append(os.path.join(anaruntime, 'magic'))

        ppcbootargs.append('-hfs-bless') # must be last

        if self.config.getint('default', 'discs') > 1:
            for disc in range(1, self.config.getint('default', 'discs') + 1): # cycle through the CD isos
                isoname = '%s-%s-%s-disc%s.iso' % (self.config.get('default', 'iso_basename'), self.config.get('default', 'version'), 
                    self.config.get('default', 'arch'), disc)
                isofile = os.path.join(self.isodir, isoname)

                extraargs = []

                if disc == 1: # if this is the first disc, we want to set boot flags
                    if self.config.get('default', 'arch') == 'i386' or self.config.get('default', 'arch') == 'x86_64':
                        extraargs.extend(x86bootargs)
                    elif self.config.get('default', 'arch') == 'ia64':
                        extraargs.extend(ia64bootargs)
                    elif self.config.get('default', 'arch') == 'ppc':
                        extraargs.extend(ppcbootargs)
                        extraargs.append(os.path.join('%s-disc%s' % (self.topdir, disc), "ppc/mac"))

                extraargs.append('-V')
                extraargs.append('"%s %s %s Disc %s"' % (self.config.get('default', 'product_name'),
                    self.config.get('default', 'version'), self.config.get('default', 'arch'), disc))

                extraargs.append('-o')
                extraargs.append(isofile)

                extraargs.append(os.path.join('%s-disc%s' % (self.topdir, disc)))

                # run the command
                self._doRunCommand(mkisofs + extraargs)

                # implant md5 for mediacheck on all but source arches
                if not self.config.get('default', 'arch') == 'source':
                    self._doRunCommand(['/usr/lib/anaconda-runtime/implantisomd5', isofile])

                # shove the sha1sum into a file
                sha1file = open(os.path.join(self.isodir, 'SHA1SUM'), 'a')
                self._doRunCommand(['/usr/bin/sha1sum', isoname], rundir=self.isodir, output=sha1file)
                sha1file.close()

                # keep track of the CD images we've written
                isolist.append(self.mkrelative(isofile))

            # Write out a line describing the CD set
            self.writeinfo('cdset: %s' % ' '.join(isolist))

        isolist=[]
        # We've asked for one or more discs, so make a DVD image
        if self.config.getint('default', 'discs') >= 1:
            isoname = '%s-%s-%s-DVD.iso' % (self.config.get('default', 'iso_basename'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'))
            isofile = os.path.join(self.isodir, isoname)

            if not self.config.get('default', 'arch') == 'source':
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

            # setup the extra mkisofs args
            extraargs = []

            if self.config.get('default', 'arch') == 'i386' or self.config.get('default', 'arch') == 'x86_64':
                extraargs.extend(x86bootargs)
            elif self.config.get('default', 'arch') == 'ia64':
                extraargs.extend(ia64bootargs)
            elif self.config.get('default', 'arch') == 'ppc':
                extraargs.extend(ppcbootargs)
                if self.config.getint('default', 'discs') == 1:
                    extraargs.append(os.path.join(self.topdir, "ppc/mac")) # this may work for both cases.. test
                else:
                    extraargs.append(os.path.join('%s-disc%s' % (self.topdir, disc), "ppc/mac"))

            extraargs.append('-V')
            extraargs.append('"%s %s %s DVD"' % (self.config.get('default', 'product_name'),
                self.config.get('default', 'version'), self.config.get('default', 'arch')))

            extraargs.append('-o')
            extraargs.append(isofile)
            
            if not self.config.get('default', 'arch') == 'source':
                extraargs.append(self.topdir)
            else:
                extraargs.append(os.path.join(self.archdir, 'SRPMS'))

            # run the command
            self._doRunCommand(mkisofs + extraargs)

            # implant md5 for mediacheck on all but source arches
            if not self.config.get('default', 'arch') == 'source':
                self._doRunCommand(['/usr/lib/anaconda-runtime/implantisomd5', isofile])

            # shove the sha1sum into a file
            sha1file = open(os.path.join(self.isodir, 'SHA1SUM'), 'a')
            self._doRunCommand(['/usr/bin/sha1sum', isoname], rundir=self.isodir, output=sha1file)
            sha1file.close()

            # return the .discinfo file
            if not self.config.get('default', 'arch') == 'source':
                shutil.move(os.path.join(self.config.get('default', 'destdir'), '.discinfo-%s' % self.config.get('default', 'arch')), discinfofile)

                shutil.rmtree(os.path.join(self.topdir, 'repodata')) # remove our copied repodata
                shutil.move(os.path.join(self.config.get('default', 'destdir'), 
                    'repodata-%s' % self.config.get('default', 'arch')), os.path.join(self.topdir, 'repodata'))

            # keep track of the DVD images we've written 
            isolist.append(self.mkrelative(isofile))

        # Write out a line describing the DVD set
        self.writeinfo('dvdset: %s' % ' '.join(isolist))

        # Now make rescue images
        if not self.config.get('default', 'arch') == 'source' and \
            os.path.exists('/usr/lib/anaconda-runtime/mk-rescueimage.%s' % self.config.get('default', 'arch')):
            isoname = '%s-%s-%s-rescuecd.iso' % (self.config.get('default', 'iso_basename'),
                self.config.get('default', 'version'), self.config.get('default', 'arch'))
            isofile = os.path.join(self.isodir, isoname)

            # make the rescue tree
            rescue = ['/usr/lib/anaconda-runtime/mk-rescueimage.%s' % self.config.get('default', 'arch')]
            rescue.append(self.topdir)
            rescue.append(self.workdir)
            rescue.append(self.config.get('default', 'iso_basename'))
            rescue.append(self.config.get('default', 'product_path'))

            # run the command
            self._doRunCommand(rescue)

            # write the iso
            extraargs = []

            if self.config.get('default', 'arch') == 'i386' or self.config.get('default', 'arch') == 'x86_64':
                extraargs.extend(x86bootargs)
            elif self.config.get('default', 'arch') == 'ia64':
                extraargs.extend(ia64bootargs)
            elif self.config.get('default', 'arch') == 'ppc':
                extraargs.extend(ppcbootargs)
                extraargs.append(os.path.join(self.workdir, "%s-rescueimage" % self.config.get('default', 'arch'), "ppc/mac"))

            extraargs.append('-V')
            extraargs.append('"%s %s %s Rescue"' % (self.config.get('default', 'product_name'),
                    self.config.get('default', 'version'), self.config.get('default', 'arch')))

            extraargs.append('-o')
            extraargs.append(isofile)

            extraargs.append(os.path.join(self.workdir, "%s-rescueimage" % self.config.get('default', 'arch')))

            # run the command
            self._doRunCommand(mkisofs + extraargs)

            # shove the sha1sum into a file
            sha1file = open(os.path.join(self.isodir, 'SHA1SUM'), 'a')
            self._doRunCommand(['/usr/bin/sha1sum', isoname], rundir=self.isodir, output=sha1file)
            sha1file.close()

        # Do some clean up
        dirs = os.listdir(self.archdir)

        for directory in dirs:
            if directory.startswith('os-disc') or directory.startswith('SRPM-disc'):
                shutil.move(os.path.join(self.archdir, directory), os.path.join(self.workdir, directory))

        log.info("CreateIsos is done.")
