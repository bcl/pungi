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

import yum
import os
import re
import shutil
import sys
import gzip
import pypungi.util
import logging
import urlgrabber.progress
import subprocess
import createrepo
import ConfigParser
import pypungi.splittree

class PungiBase(object):
    """The base Pungi class.  Set up config items and logging here"""

    def __init__(self, config):
        self.config = config

        self.doLoggerSetup()

        self.workdir = os.path.join(self.config.get('default', 'destdir'),
                                    'work',
                                    self.config.get('default', 'flavor'),
                                    self.config.get('default', 'arch'))



    def doLoggerSetup(self):
        """Setup our logger"""

        logdir = os.path.join(self.config.get('default', 'destdir'), 'logs')

        pypungi.util._ensuredir(logdir, None, force=True) # Always allow logs to be written out

        if self.config.get('default', 'flavor'):
            logfile = os.path.join(logdir, '%s.%s.log' % (self.config.get('default', 'flavor'),
                                                          self.config.get('default', 'arch')))
        else:
            logfile = os.path.join(logdir, '%s.log' % (self.config.get('default', 'arch')))

        # Create the root logger, that will log to our file
        logging.basicConfig(level=logging.DEBUG,
                            format='%(name)s.%(levelname)s: %(message)s',
                            filename=logfile)


class CallBack(urlgrabber.progress.TextMeter):
    """A call back function used with yum."""

    def progressbar(self, current, total, name=None):
        return


class PungiYum(yum.YumBase):
    """Subclass of Yum"""

    def __init__(self, config):
        self.pungiconfig = config
        yum.YumBase.__init__(self)

    def doLoggingSetup(self, debuglevel, errorlevel, syslog_ident=None, syslog_facility=None):
        """Setup the logging facility."""

        logdir = os.path.join(self.pungiconfig.get('default', 'destdir'), 'logs')
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        if self.pungiconfig.get('default', 'flavor'):
            logfile = os.path.join(logdir, '%s.%s.log' % (self.pungiconfig.get('default', 'flavor'),
                                                          self.pungiconfig.get('default', 'arch')))
        else:
            logfile = os.path.join(logdir, '%s.log' % (self.pungiconfig.get('default', 'arch')))

        yum.logging.basicConfig(level=yum.logging.DEBUG, filename=logfile)

    def doFileLogSetup(self, uid, logfile):
        # This function overrides a yum function, allowing pungi to control
        # the logging.
        pass


class Pungi(pypungi.PungiBase):
    def __init__(self, config, ksparser):
        pypungi.PungiBase.__init__(self, config)
 
        # Set our own logging name space
        self.logger = logging.getLogger('Pungi')

        # Create the stdout/err streams and only send INFO+ stuff there
        formatter = logging.Formatter('%(name)s:%(levelname)s: %(message)s')
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        self.logger.addHandler(console)

        self.destdir = self.config.get('default', 'destdir')
        self.archdir = os.path.join(self.destdir,
                                   self.config.get('default', 'version'),
                                   self.config.get('default', 'flavor'),
                                   self.config.get('default', 'arch'))

        self.topdir = os.path.join(self.archdir, 'os')
        self.isodir = os.path.join(self.archdir, self.config.get('default','isodir'))

        pypungi.util._ensuredir(self.workdir, self.logger, force=True)

        self.common_files = []
        self.infofile = os.path.join(self.config.get('default', 'destdir'),
                                    self.config.get('default', 'version'),
                                    '.composeinfo')

        self.ksparser = ksparser
        self.polist = []
        self.srpmlist = []
        self.debuginfolist = []
        self.resolved_deps = {} # list the deps we've already resolved, short circuit.

    def _inityum(self):
        """Initialize the yum object.  Only needed for certain actions."""

        # Create a yum object to use
        self.repos = []
        self.mirrorlists = []
        self.ayum = PungiYum(self.config)
        self.ayum.doLoggingSetup(6, 6)
        yumconf = yum.config.YumConf()
        yumconf.debuglevel = 6
        yumconf.errorlevel = 6
        yumconf.cachedir = self.config.get('default', 'cachedir')
        yumconf.persistdir = os.path.join(self.workdir, 'yumlib')
        yumconf.installroot = os.path.join(self.workdir, 'yumroot')
        yumconf.uid = os.geteuid()
        yumconf.cache = 0
        yumconf.failovermethod = 'priority'
        yumvars = yum.config._getEnvVar()
        yumvars['releasever'] = self.config.get('default', 'version')
        yumvars['basearch'] = yum.rpmUtils.arch.getBaseArch(myarch=self.config.get('default', 'arch'))
        yumconf.yumvar = yumvars
        self.ayum._conf = yumconf
        self.ayum.repos.setCacheDir(self.ayum.conf.cachedir)

        arch = self.config.get('default', 'arch')
        if arch == 'i386':
            yumarch = 'athlon'
        elif arch == 'ppc':
            yumarch = 'ppc64'
        elif arch == 'sparc':
            yumarch = 'sparc64v'
        else:
            yumarch = arch

        self.ayum.compatarch = yumarch
        arches = yum.rpmUtils.arch.getArchList(yumarch)
        arches.append('src') # throw source in there, filter it later

        # deal with our repos
        try:
            self.ksparser.handler.repo.methodToRepo()
        except:
            pass

        for repo in self.ksparser.handler.repo.repoList:
            self.logger.info('Adding repo %s' % repo.name)
            thisrepo = yum.yumRepo.YumRepository(repo.name)
            thisrepo.name = repo.name
            # add excludes and such here when pykickstart gets them
            if repo.mirrorlist:
                thisrepo.mirrorlist = yum.parser.varReplace(repo.mirrorlist, self.ayum.conf.yumvar)
                self.mirrorlists.append(thisrepo.mirrorlist)
                self.logger.info('Mirrorlist for repo %s is %s' % (thisrepo.name, thisrepo.mirrorlist))
            else:
                thisrepo.baseurl = yum.parser.varReplace(repo.baseurl, self.ayum.conf.yumvar)
                self.repos.extend(thisrepo.baseurl)
                self.logger.info('URL for repo %s is %s' % (thisrepo.name, thisrepo.baseurl))
            thisrepo.basecachedir = self.ayum.conf.cachedir
            thisrepo.enablegroups = True
            thisrepo.failovermethod = 'priority' # This is until yum uses this failover by default
            thisrepo.exclude = repo.excludepkgs
            thisrepo.includepkgs = repo.includepkgs
            if repo.cost:
                thisrepo.cost = repo.cost
            self.ayum.repos.add(thisrepo)
            self.ayum.repos.enableRepo(thisrepo.id)
            self.ayum._getRepos(thisrepo=thisrepo.id, doSetup = True)

        self.ayum.repos.setProgressBar(CallBack())
        self.ayum.repos.callback = CallBack()
        
        # Set the metadata and mirror list to be expired so we always get new ones.
        for repo in self.ayum.repos.listEnabled():
            repo.metadata_expire = 0
            repo.mirrorlist_expire = 0
            if os.path.exists(os.path.join(repo.cachedir, 'repomd.xml')):
                os.remove(os.path.join(repo.cachedir, 'repomd.xml'))

        self.logger.info('Getting sacks for arches %s' % arches)
        self.ayum._getSacks(archlist=arches)

    def _filtersrcdebug(self, po):
        """Filter out package objects that are of 'src' arch."""

        if po.arch == 'src' or 'debuginfo' in po.name:
            return False

        return True

    def verifyCachePkg(self, po, path): # Stolen from yum
        """check the package checksum vs the cache
           return True if pkg is good, False if not"""

        (csum_type, csum) = po.returnIdSum()

        try:
            filesum = yum.misc.checksum(csum_type, path)
        except yum.Errors.MiscError:
            return False

        if filesum != csum:
            return False

        return True

    def getPackageDeps(self, po):
        """Add the dependencies for a given package to the
           transaction info"""

        self.logger.info('Checking deps of %s.%s' % (po.name, po.arch))

        reqs = po.requires
        provs = po.provides

        for req in reqs:
            if self.resolved_deps.has_key(req):
                continue
            (r,f,v) = req
            if r.startswith('rpmlib(') or r.startswith('config('):
                continue
            if req in provs:
                continue

            deps = self.ayum.whatProvides(r, f, v).returnPackages()
            if not deps:
                self.logger.warn("Unresolvable dependency %s in %s.%s" % (r, po.name, po.arch))
                continue

            depsack = yum.packageSack.ListPackageSack(deps)

            for dep in depsack.returnNewestByNameArch():
                self.ayum.tsInfo.addInstall(dep)
                self.logger.info('Added %s.%s for %s.%s' % (dep.name, dep.arch, po.name, po.arch))
           
            self.resolved_deps[req] = None

    def getPackagesFromGroup(self, group):
        """Get a list of package names from a ksparser group object

            Returns a list of package names"""

        packages = []

        # Check if we have the group
        if not self.ayum.comps.has_group(group.name):
            self.logger.error("Group %s not found in comps!" % group)
            return packages

        # Get the group object to work with
        groupobj = self.ayum.comps.return_group(group.name)

        # Add the mandatory packages
        packages.extend(groupobj.mandatory_packages.keys())

        # Add the default packages unless we don't want them
        if group.include == 1:
            packages.extend(groupobj.default_packages.keys())

        # Add the optional packages if we want them
        if group.include == 2:
            packages.extend(groupobj.default_packages.keys())
            packages.extend(groupobj.optional_packages.keys())

        # Deal with conditional packages
        # Populate a dict with the name of the required package and value
        # of the package objects it would bring in.  To be used later if
        # we match the conditional.
        for condreq, cond in groupobj.conditional_packages.iteritems():
            pkgs = self.ayum.pkgSack.searchNevra(name=condreq)
            if pkgs:
                pkgs = self.ayum.bestPackagesFromList(pkgs, arch=self.ayum.compatarch)
            if self.ayum.tsInfo.conditionals.has_key(cond):
                self.ayum.tsInfo.conditionals[cond].extend(pkgs)
            else:
                self.ayum.tsInfo.conditionals[cond] = pkgs

        return packages

    def getPackageObjects(self):
        """Cycle through the list of packages, get package object
           matches, and resolve deps.

           Returns a list of package objects"""

        final_pkgobjs = {} # The final list of package objects
        searchlist = [] # The list of package names/globs to search for
        matchdict = {} # A dict of objects to names

        # First remove the excludes
        self.ayum.conf.exclude.extend(self.ksparser.handler.packages.excludedList)
        self.ayum.excludePackages()
        
        # Always add the core groiup
        self.ksparser.handler.packages.add(['@core'])

        # Check to see if we need the base group
        if self.ksparser.handler.packages.addBase:
            self.ksparser.handler.packages.add(['@base'])

        # Get a list of packages from groups
        for group in self.ksparser.handler.packages.groupList:
            searchlist.extend(self.getPackagesFromGroup(group))

        # Add the adds
        searchlist.extend(self.ksparser.handler.packages.packageList)

        # Make the search list unique
        searchlist = yum.misc.unique(searchlist)

        # Search repos for things in our searchlist, supports globs
        (exactmatched, matched, unmatched) = yum.packages.parsePackages(self.ayum.pkgSack.returnPackages(), searchlist, casematch=1)
        matches = filter(self._filtersrcdebug, exactmatched + matched)

        # Populate a dict of package objects to their names
        for match in matches:
            matchdict[match.name] = match
            
        # Get the newest results from the search
        mysack = yum.packageSack.ListPackageSack(matches)
        for match in mysack.returnNewestByNameArch():
            self.ayum.tsInfo.addInstall(match)
            self.logger.debug('Found %s.%s' % (match.name, match.arch))

        for pkg in unmatched:
            if not pkg in matchdict.keys():
                self.logger.warn('Could not find a match for %s in any configured repo' % pkg)

        if len(self.ayum.tsInfo) == 0:
            raise yum.Errors.MiscError, 'No packages found to download.'

        moretoprocess = True
        while moretoprocess: # Our fun loop
            moretoprocess = False
            for txmbr in self.ayum.tsInfo:
                if not final_pkgobjs.has_key(txmbr.po):
                    final_pkgobjs[txmbr.po] = None # Add the pkg to our final list
                    self.getPackageDeps(txmbr.po) # Get the deps of our package
                    moretoprocess = True

        self.polist = final_pkgobjs.keys()
        self.logger.info('Finished gathering package objects.')

    def getSRPMList(self):
        """Cycle through the list of package objects and
           find the sourcerpm for them.  Requires yum still
           configured and a list of package objects"""
 
        for po in self.polist:
            srpm = po.sourcerpm.split('.src.rpm')[0]
            if not srpm in self.srpmlist:
                self.srpmlist.append(srpm)

    def getDebuginfoList(self):
        """Cycle through the list of package objects and find
           debuginfo rpms for them.  Requires yum still
           configured and a list of package objects"""

        for po in self.polist:
            debugname = '%s-debuginfo' % po.name
            results = self.ayum.pkgSack.searchNevra(name=debugname,
                                                    epoch=po.epoch,
                                                    ver=po.version,
                                                    rel=po.release,
                                                    arch=po.arch)
            if results:
                if not results[0] in self.debuginfolist:
                    self.logger.debug('Added %s found by name' % results[0].name)
                    self.debuginfolist.append(results[0])
            else:
                srpm = po.sourcerpm.split('.src.rpm')[0]
                sname, sver, srel = srpm.rsplit('-', 2)
                debugname = '%s-debuginfo' % sname
                srcresults = self.ayum.pkgSack.searchNevra(name=debugname,
                                                           ver=sver,
                                                           rel=srel,
                                                           arch=po.arch)
                if srcresults:
                    if not srcresults[0] in self.debuginfolist:
                        self.logger.debug('Added %s found by srpm' % srcresults[0].name)
                        self.debuginfolist.append(srcresults[0])

            if po.name == 'kernel' or po.name == 'glibc':
                debugcommon = '%s-debuginfo-common' % po.name
                commonresults = self.ayum.pkgSack.searchNevra(name=debugcommon,
                                                              epoch=po.epoch,
                                                              ver=po.version,
                                                              rel=po.release,
                                                              arch=po.arch)
                if commonresults:
                    if not commonresults[0] in self.debuginfolist:
                        self.logger.debug('Added %s found by common' % commonresults[0].name)
                        self.debuginfolist.append(commonresults[0])

    def _downloadPackageList(self, polist, relpkgdir):
        """Cycle through the list of package objects and
           download them from their respective repos."""

        downloads = []
        for pkg in polist:
            downloads.append('%s.%s' % (pkg.name, pkg.arch))
            downloads.sort()
        self.logger.info("Download list: %s" % downloads)

        pkgdir = os.path.join(self.config.get('default', 'destdir'),
                              self.config.get('default', 'version'),
                              self.config.get('default', 'flavor'),
                              relpkgdir)

        # Ensure the pkgdir exists, force if requested, and make sure we clean it out
        if relpkgdir.endswith('SRPMS'):
            # Since we share source dirs with other arches don't clean, but do allow us to use it
            pypungi.util._ensuredir(pkgdir, self.logger, force=True, clean=False)
        else:
            pypungi.util._ensuredir(pkgdir, self.logger, force=self.config.getboolean('default', 'force'), clean=True)

        probs = self.ayum.downloadPkgs(polist)

        if len(probs.keys()) > 0:
            self.logger.error("Errors were encountered while downloading packages.")
            for key in probs.keys():
                errors = yum.misc.unique(probs[key])
                for error in errors:
                    self.logger.error("%s: %s" % (key, error))
            sys.exit(1)

        for po in polist:
            basename = os.path.basename(po.relativepath)

            local = po.localPkg()
            target = os.path.join(pkgdir, basename)

            # Link downloaded package in (or link package from file repo)
            try:
                pypungi.util._link(local, target, self.logger, force=True)
                continue
            except:
                self.logger.error("Unable to link %s from the yum cache." % po.name)
                sys.exit(1)

        self.logger.info('Finished downloading packages.')

    def downloadPackages(self):
        """Download the package objects obtained in getPackageObjects()."""

        self._downloadPackageList(self.polist,
                                  os.path.join(self.config.get('default', 'arch'),
                                               self.config.get('default', 'osdir'),
                                               self.config.get('default', 'product_path')))

    def makeCompsFile(self):
        """Gather any comps files we can from repos and merge them into one."""

        ourcompspath = os.path.join(self.workdir, '%s-%s-comps.xml' % (self.config.get('default', 'name'), self.config.get('default', 'version')))

        ourcomps = open(ourcompspath, 'w')

        ourcomps.write(self.ayum.comps.xml())

        ourcomps.close()

        # Disable this until https://bugzilla.redhat.com/show_bug.cgi?id=442097 is fixed.
        # Run the xslt filter over our comps file
        #compsfilter = ['/usr/bin/xsltproc', '--novalid']
        #compsfilter.append('-o')
        #compsfilter.append(ourcompspath)
        #compsfilter.append('/usr/share/pungi/comps-cleanup.xsl')
        #compsfilter.append(ourcompspath)

        #pypungi.util._doRunCommand(compsfilter, self.logger)

    def downloadSRPMs(self):
        """Cycle through the list of srpms and
           find the package objects for them, Then download them."""

        srpmpolist = []

        for srpm in self.srpmlist:
            (sname, sver, srel) = srpm.rsplit('-', 2)
            try:
                srpmpo = self.ayum.pkgSack.searchNevra(name=sname, ver=sver, rel=srel, arch='src')[0]
                if not srpmpo in srpmpolist:
                    srpmpolist.append(srpmpo)
            except IndexError:
                print >> sys.stderr, "Error: Cannot find a source rpm for %s" % srpm
                sys.exit(1)

        # do the downloads
        self._downloadPackageList(srpmpolist, os.path.join('source', 'SRPMS'))

    def downloadDebuginfo(self):
        """Cycle through the list of debuginfo rpms and
           download them."""

        # do the downloads
        self._downloadPackageList(self.debuginfolist, os.path.join(self.config.get('default', 'arch'),
                                                           'debug'))

    def writeinfo(self, line):
        """Append a line to the infofile in self.infofile"""


        f=open(self.infofile, "a+")
        f.write(line.strip() + "\n")
        f.close()

    def mkrelative(self, subfile):
        """Return the relative path for 'subfile' underneath the version dir."""

        basedir = os.path.join(self.destdir, self.config.get('default', 'version'))
        if subfile.startswith(basedir):
            return subfile.replace(basedir + os.path.sep, '')
        
    def _makeMetadata(self, path, cachedir, comps=False, repoview=False, repoviewtitle=False,
                      baseurl=False, output=False, basedir=False, split=False, update=True):
        """Create repodata and repoview."""
        
        conf = createrepo.MetaDataConfig()
        conf.cachedir = os.path.join(cachedir, 'createrepocache')
        conf.update = update
        if output:
            conf.outputdir = output
        else:
            conf.outputdir = path
        conf.directory = path
        conf.database = True
        if comps:
           conf.groupfile = comps
        if basedir:
            conf.basedir = basedir
        if baseurl:
            conf.baseurl = baseurl
        if split:
            conf.split = True
            conf.directories = split
            repomatic = createrepo.SplitMetaDataGenerator(conf)
        else:
            repomatic = createrepo.MetaDataGenerator(conf)
        self.logger.info('Making repodata')
        repomatic.doPkgMetadata()
        repomatic.doRepoMetadata()
        repomatic.doFinalMove()
        
        if repoview:
            # setup the repoview call
            repoview = ['/usr/bin/repoview']
            repoview.append('--quiet')
            
            repoview.append('--state-dir')
            repoview.append(os.path.join(cachedir, 'repoviewcache'))
            
            if repoviewtitle:
                repoview.append('--title')
                repoview.append(repoviewtitle)
    
            repoview.append(path)
    
            # run the command
            pypungi.util._doRunCommand(repoview, self.logger)
        
    def doCreaterepo(self, comps=True):
        """Run createrepo to generate repodata in the tree."""


        compsfile = None
        if comps:
            compsfile = os.path.join(self.workdir, '%s-%s-comps.xml' % (self.config.get('default', 'name'), self.config.get('default', 'version')))
        
        # setup the cache dirs
        for target in ['createrepocache', 'repoviewcache']:
            pypungi.util._ensuredir(os.path.join(self.config.get('default', 'cachedir'),
                                            target), 
                               self.logger, 
                               force=True)
            
        repoviewtitle = '%s %s - %s' % (self.config.get('default', 'name'), 
                                        self.config.get('default', 'version'),
                                        self.config.get('default', 'arch'))

        cachedir = self.config.get('default', 'cachedir')

        # setup the createrepo call
        self._makeMetadata(self.topdir, cachedir, compsfile, repoview=True, repoviewtitle=repoviewtitle)

        # create repodata for debuginfo
        if self.config.getboolean('default', 'debuginfo'):
            path = os.path.join(self.archdir, 'debug')
            if not os.path.isdir(path):
                self.logger.debug("No debuginfo for %s" % self.config.get('default', 'arch'))
                return
            self._makeMetadata(path, cachedir, repoview=False)

    def doBuildinstall(self):
        """Run anaconda-runtime's buildinstall on the tree."""


        # setup the buildinstall call
        buildinstall = ['/usr/lib/anaconda-runtime/buildinstall']
        #buildinstall.append('TMPDIR=%s' % self.workdir) # TMPDIR broken in buildinstall

        buildinstall.append('--product')
        buildinstall.append(self.config.get('default', 'name'))

        if not self.config.get('default', 'flavor') == "":
            buildinstall.append('--variant')
            buildinstall.append(self.config.get('default', 'flavor'))

        buildinstall.append('--version')
        buildinstall.append(self.config.get('default', 'version'))

        buildinstall.append('--release')
        buildinstall.append('%s %s' % (self.config.get('default', 'name'), self.config.get('default', 'version')))

        if self.config.has_option('default', 'bugurl'):
            buildinstall.append('--bugurl')
            buildinstall.append(self.config.get('default', 'bugurl'))

        buildinstall.append('--output')
        buildinstall.append(self.topdir)

        for mirrorlist in self.mirrorlists:
            buildinstall.append('--mirrorlist')
            buildinstall.append(mirrorlist)

        buildinstall.append(self.topdir)

        # Add any extra repos of baseurl type
        for repo in self.repos:
            buildinstall.append(repo)

        # run the command
        # TMPDIR is still broken with buildinstall.
        pypungi.util._doRunCommand(buildinstall, self.logger) #, env={"TMPDIR": self.workdir})

        # write out the tree data for snake
        self.writeinfo('tree: %s' % self.mkrelative(self.topdir))

        # Write out checksums for verifytree
        # First open the treeinfo file so that we can config parse it
        treeinfofile = os.path.join(self.topdir, '.treeinfo')

        try:
            treefile = open(treeinfofile, 'r')
        except IOError:
            self.logger.error("Could not read .treeinfo file: %s" % treefile)
            sys.exit(1)

        # Create a ConfigParser object out of the contents so that we can
        # write it back out later and not worry about formatting
        treeinfo = ConfigParser.SafeConfigParser()
        treeinfo.readfp(treefile)
        treefile.close()
        treeinfo.add_section('checksums')

        # Create a function to use with os.path.walk to sum the files
        # basepath is used to make the sum output relative
        sums = []
        def getsum(basepath, dir, files):
            for file in files:
                path = os.path.join(dir, file)
                # don't bother summing directories.  Won't work.
                if os.path.isdir(path):
                    continue
                sum = pypungi.util._doCheckSum(path, 'sha1', self.logger)
                outpath = path.replace(basepath, '')
                sums.append((outpath, sum))

        # Walk the os/images path to get sums of all the files
        os.path.walk(os.path.join(self.topdir, 'images'), getsum, self.topdir + '/')
        
        # Capture PPC images
        if self.config.get('default', 'arch') == 'ppc':
            os.path.walk(os.path.join(self.topdir, 'ppc'), getsum, self.topdir + '/')

        # Get a checksum of repomd.xml since it has within it sums for other files
        repomd = os.path.join(self.topdir, 'repodata', 'repomd.xml')
        sum = pypungi.util._doCheckSum(repomd, 'sha1', self.logger)
        sums.append((os.path.join('repodata', 'repomd.xml'), sum))

        # Now add the sums, and write the config out
        try:
            treefile = open(treeinfofile, 'w')
        except IOError:
            self.logger.error("Could not open .treeinfo for writing: %s" % treefile)
            sys.exit(1)

        for path, sum in sums:
            treeinfo.set('checksums', path, sum)

        treeinfo.write(treefile)
        treefile.close()

    def doPackageorder(self):
        """Run anaconda-runtime's pkgorder on the tree, used for splitting media."""


        pkgorderfile = open(os.path.join(self.workdir, 'pkgorder-%s' % self.config.get('default', 'arch')), 'w')
        # setup the command
        pkgorder = ['/usr/bin/pkgorder']
        #pkgorder.append('TMPDIR=%s' % self.workdir)
        pkgorder.append(self.topdir)
        pkgorder.append(self.config.get('default', 'arch'))
        pkgorder.append(self.config.get('default', 'product_path'))

        # run the command
        pypungi.util._doRunCommand(pkgorder, self.logger, output=pkgorderfile)
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

        pypungi.util._ensuredir(docsdir, self.logger, force=self.config.getboolean('default', 'force'), clean=True)

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
                            stderr=subprocess.PIPE, universal_newlines=True).communicate()
                    except:
                        self.logger.error("Got an error from rpm2cpio")
                        self.logger.error(err)
                        raise

                    if out:
                        self.logger.debug(out)

        # Walk the tree for our files
        for dirpath, dirname, filelist in os.walk(docsdir):
            for filename in filelist:
                for regex in fileres:
                    if regex.match(filename) and not os.path.exists(os.path.join(self.topdir, filename)):
                        self.logger.info("Linking release note file %s" % filename)
                        pypungi.util._link(os.path.join(dirpath, filename), os.path.join(self.topdir, filename), self.logger)
                        self.common_files.append(filename)

        # Walk the tree for our dirs
        for dirpath, dirname, filelist in os.walk(docsdir):
            for directory in dirname:
                for regex in dirres:
                    if regex.match(directory) and not os.path.exists(os.path.join(self.topdir, directory)):
                        self.logger.info("Copying release note dir %s" % directory)
                        shutil.copytree(os.path.join(dirpath, directory), os.path.join(self.topdir, directory))
        
    def doSplittree(self):
        """Use anaconda-runtime's splittree to split the tree into appropriate
           sized chunks."""


        timber = splittree.Timber()
        timber.arch = self.config.get('default', 'arch')
        timber.target_size = self.config.getfloat('default', 'cdsize') * 1024 * 1024
        timber.total_discs = self.config.getint('default', 'discs')
        timber.bin_discs = self.config.getint('default', 'discs')
        timber.src_discs = 0
        timber.release_str = '%s %s' % (self.config.get('default', 'name'), self.config.get('default', 'version'))
        timber.package_order_file = os.path.join(self.workdir, 'pkgorder-%s' % self.config.get('default', 'arch'))
        timber.dist_dir = self.topdir
        timber.src_dir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 'source', 'SRPMS')
        timber.product_path = self.config.get('default', 'product_path')
        timber.common_files = self.common_files
        #timber.reserve_size =  

        self.logger.info("Running splittree.")

        output = timber.main()
        if output:
            self.logger.debug("Output from splittree: %s" % '\n'.join(output))

    def doSplitSRPMs(self):
        """Use anaconda-runtime's splittree to split the srpms into appropriate
           sized chunks."""


        timber = splittree.Timber()
        timber.arch = self.config.get('default', 'arch')
        #timber.total_discs = self.config.getint('default', 'discs')
        #timber.bin_discs = self.config.getint('default', 'discs')
        timber.src_discs = self.config.getint('default', 'discs')
        #timber.release_str = '%s %s' % (self.config.get('default', 'name'), self.config.get('default', 'version'))
        #timber.package_order_file = os.path.join(self.config.get('default', 'destdir'), 'pkgorder-%s' % self.config.get('default', 'arch'))
        timber.dist_dir = os.path.join(self.config.get('default', 'destdir'),
                                       self.config.get('default', 'version'),
                                       self.config.get('default', 'flavor'),
                                       'source', 'SRPMS')
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
                pypungi.util._ensuredir('%s-disc%d/SRPMS' % (timber.dist_dir, i),
                                   self.logger,
                                   force=self.config.getboolean('default', 'force'),
                                   clean=True)
                timber.linkFiles(timber.dist_dir,
                               "%s-disc%d" %(timber.dist_dir, i),
                               timber.common_files)

        self.logger.info("Splitting SRPMs")
        timber.splitSRPMS()
        self.logger.info("splitSRPMS complete")

    def doCreateMediarepo(self, split=False):
        """Create the split metadata for the isos"""


        discinfo = open(os.path.join(self.topdir, '.discinfo'), 'r').readlines()
        mediaid = discinfo[0].rstrip('\n')

        compsfile = os.path.join(self.workdir, '%s-%s-comps.xml' % (self.config.get('default', 'name'), self.config.get('default', 'version')))

        if not split:
            pypungi.util._ensuredir('%s-disc1' % self.topdir, self.logger, 
                               clean=True) # rename this for single disc
            path = self.topdir
            basedir=None
        else:
            path = '%s-disc1' % self.topdir
            basedir = path
            split=[]
            for disc in range(1, self.config.getint('default', 'discs') + 1):
                split.append('%s-disc%s' % (self.topdir, disc))
            
        # set up the process
        self._makeMetadata(path, self.config.get('default', 'cachedir'), compsfile, repoview=False, 
                                                 baseurl='media://%s' % mediaid, 
                                                 output='%s-disc1' % self.topdir, 
                                                 basedir=basedir, split=split, update=False)

        # Write out a repo file for the disc to be used on the installed system
        self.logger.info('Creating media repo file.')
        repofile = open(os.path.join(self.topdir, 'media.repo'), 'w')
        repocontent = """[InstallMedia]
name=%s %s
mediaid=%s
metadata_expire=-1
gpgcheck=0
cost=500
""" % (self.config.get('default', 'name'), self.config.get('default', 'version'), mediaid)

        repofile.write(repocontent)
        repofile.close()

    def _doIsoSha1(self, path, shafile):
        """Simple function to wrap creating sha1sums of iso files."""

        try:
            sha1file = open(shafile, 'a')
        except IOError:
            self.logger.error("Could not open sha1sum file: %s" % shafile)

        self.logger.info("Generating sha1sum of %s" % path)
        sha1sum = pypungi.util._doCheckSum(path, 'sha1', self.logger)
        if sha1sum:
            sha1file.write("%s *%s\n" % (sha1sum.replace('sha1:', ''), os.path.basename(path)))
        else:
            self.logger.error('Failed to generate sha1sum for %s' % sha1file)
            sys.exit(1)
        sha1file.close()

    def doCreateIsos(self, split=True):
        """Create isos of the tree, optionally splitting the tree for split media."""


        isolist=[]
        anaruntime = '/usr/lib/anaconda-runtime/boot'
        discinfofile = os.path.join(self.topdir, '.discinfo') # we use this a fair amount

        pypungi.util._ensuredir(self.isodir, self.logger,
                           force=self.config.getboolean('default', 'force'),
                           clean=True) # This is risky...

        # setup the base command
        mkisofs = ['/usr/bin/mkisofs']
        mkisofs.extend(['-v', '-U', '-J', '-R', '-T', '-m', 'repoview']) # common mkisofs flags

        x86bootargs = ['-b', 'isolinux/isolinux.bin', '-c', 'isolinux/boot.cat', 
            '-no-emul-boot', '-boot-load-size', '4', '-boot-info-table']

        ia64bootargs = ['-b', 'images/boot.img', '-no-emul-boot']

        ppcbootargs = ['-part', '-hfs', '-r', '-l', '-sysid', 'PPC', '-no-desktop', '-allow-multidot', '-chrp-boot']

        ppcbootargs.append('-map')
        ppcbootargs.append(os.path.join(anaruntime, 'mapping'))

        ppcbootargs.append('-magic')
        ppcbootargs.append(os.path.join(anaruntime, 'magic'))

        ppcbootargs.append('-hfs-bless') # must be last

        sparcbootargs = ['-G', '/boot/isofs.b', '-B', '...', '-s', '/boot/silo.conf', '-sparc-label', '"sparc"']

        # Check the size of the tree
        # This size checking method may be bunk, accepting patches...
        if not self.config.get('default', 'arch') == 'source':
            treesize = int(subprocess.Popen(mkisofs + ['-print-size', '-quiet', self.topdir], stdout=subprocess.PIPE).communicate()[0])
        else:
            srcdir = os.path.join(self.config.get('default', 'destdir'), self.config.get('default', 'version'), 
                                  self.config.get('default', 'flavor'), 'source', 'SRPMS')

            treesize = int(subprocess.Popen(mkisofs + ['-print-size', '-quiet', srcdir], stdout=subprocess.PIPE).communicate()[0])
        # Size returned is 2KiB clusters or some such.  This translates that to MiB.
        treesize = treesize * 2048 / 1024 / 1024

        cdsize = self.config.getfloat('default', 'cdsize')

        # Do some math to figure out how many discs we'd need
        if treesize < cdsize or not split:
            self.config.set('default', 'discs', '1')
        else:
            discs = int(treesize / cdsize + 1)
            self.config.set('default', 'discs', str(discs))

        if not self.config.get('default', 'arch') == 'source':
            self.doCreateMediarepo(split=False)

        if treesize > 700: # we're larger than a 700meg CD
            isoname = '%s-%s-%s-DVD.iso' % (self.config.get('default', 'iso_basename'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'))
        else:
            isoname = '%s-%s-%s.iso' % (self.config.get('default', 'iso_basename'), self.config.get('default', 'version'), 
                self.config.get('default', 'arch'))

        isofile = os.path.join(self.isodir, isoname)

        if not self.config.get('default', 'arch') == 'source':
            # move the main repodata out of the way to use the split repodata
            if os.path.isdir(os.path.join(self.config.get('default', 'destdir'), 
                                          'repodata-%s' % self.config.get('default', 'arch'))):
                shutil.rmtree(os.path.join(self.config.get('default', 'destdir'), 
                                           'repodata-%s' % self.config.get('default', 'arch')))
                
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
            extraargs.append(os.path.join(self.topdir, "ppc/mac"))
        elif self.config.get('default', 'arch') == 'sparc':
            extraargs.extend(sparcbootargs)

        extraargs.append('-V')
        if treesize > 700:
            extraargs.append('%s %s %s DVD' % (self.config.get('default', 'name'),
                self.config.get('default', 'version'), self.config.get('default', 'arch')))
        else:
            extraargs.append('%s %s %s' % (self.config.get('default', 'name'),
                self.config.get('default', 'version'), self.config.get('default', 'arch')))

        extraargs.append('-o')
        extraargs.append(isofile)
        
        if not self.config.get('default', 'arch') == 'source':
            extraargs.append(self.topdir)
        else:
            extraargs.append(os.path.join(self.archdir, 'SRPMS'))

        # run the command
        pypungi.util._doRunCommand(mkisofs + extraargs, self.logger)

        # implant md5 for mediacheck on all but source arches
        if not self.config.get('default', 'arch') == 'source':
            pypungi.util._doRunCommand(['/usr/bin/implantisomd5', isofile], self.logger)

        # shove the sha1sum into a file
        sha1file = os.path.join(self.isodir, 'SHA1SUM')
        self._doIsoSha1(isofile, sha1file)

        # return the .discinfo file
        if not self.config.get('default', 'arch') == 'source':
            shutil.rmtree(os.path.join(self.topdir, 'repodata')) # remove our copied repodata
            shutil.move(os.path.join(self.config.get('default', 'destdir'), 
                'repodata-%s' % self.config.get('default', 'arch')), os.path.join(self.topdir, 'repodata'))
            
        # Move the unified disk out
        if not self.config.get('default', 'arch') == 'source':
            shutil.rmtree(os.path.join(self.workdir, 'os-unified'), ignore_errors=True)
            shutil.move('%s-disc1' % self.topdir, os.path.join(self.workdir, 'os-unified'))

        # Write out a line describing the media
        self.writeinfo('media: %s' % self.mkrelative(isofile))

        if self.config.getint('default', 'discs') > 1:
            if self.config.get('default', 'arch') == 'source':
                self.doSplitSRPMs()
            else:
                self.doPackageorder()
                self.doSplittree()
                self.doCreateMediarepo(split=True)
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
                    elif self.config.get('default', 'arch') == 'sparc':
                        extraargs.extend(sparcbootargs)

                extraargs.append('-V')
                extraargs.append('%s %s %s Disc %s' % (self.config.get('default', 'name'),
                    self.config.get('default', 'version'), self.config.get('default', 'arch'), disc))

                extraargs.append('-o')
                extraargs.append(isofile)

                extraargs.append(os.path.join('%s-disc%s' % (self.topdir, disc)))

                # run the command
                pypungi.util._doRunCommand(mkisofs + extraargs, self.logger)

                # implant md5 for mediacheck on all but source arches
                if not self.config.get('default', 'arch') == 'source':
                    pypungi.util._doRunCommand(['/usr/bin/implantisomd5', isofile], self.logger)

                # shove the sha1sum into a file
                sha1file = os.path.join(self.isodir, 'SHA1SUM')
                self._doIsoSha1(isofile, sha1file)

                # keep track of the CD images we've written
                isolist.append(self.mkrelative(isofile))

            # Write out a line describing the CD set
            self.writeinfo('mediaset: %s' % ' '.join(isolist))

        # Now link the boot iso
        if not self.config.get('default', 'arch') == 'source' and \
        os.path.exists(os.path.join(self.topdir, 'images', 'boot.iso')):
            isoname = '%s-%s-%s-netinst.iso' % (self.config.get('default', 'iso_basename'),
                self.config.get('default', 'version'), self.config.get('default', 'arch'))
            isofile = os.path.join(self.isodir, isoname)

            # link the boot iso to the iso dir
            pypungi.util._link(os.path.join(self.topdir, 'images', 'boot.iso'), isofile, self.logger)

            # shove the sha1sum into a file
            sha1file = os.path.join(self.isodir, 'SHA1SUM')
            self._doIsoSha1(isofile, sha1file)

        # Do some clean up
        dirs = os.listdir(self.archdir)

        for directory in dirs:
            if directory.startswith('os-disc') or directory.startswith('SRPMS-disc'):
                if os.path.exists(os.path.join(self.workdir, directory)):
                    shutil.rmtree(os.path.join(self.workdir, directory))
                shutil.move(os.path.join(self.archdir, directory), os.path.join(self.workdir, directory))

        self.logger.info("CreateIsos is done.")
