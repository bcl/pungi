PKGNAME=pungi
VERSION=$(shell rpm -q --qf "%{VERSION}\n" --specfile ${PKGNAME}.spec)
RELEASE=$(shell rpm -q --qf "%{RELEASE}\n" --specfile ${PKGNAME}.spec)
GITTAG=${PKGNAME}-$(VERSION)-$(RELEASE)
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"

RPM="noarch/${PKGNAME}-$(VERSION)-$(RELEASE).noarch.rpm"
SRPM="${PKGNAME}-$(VERSION)-$(RELEASE).src.rpm"


default: all

all:
	@echo "Nothing to do"

tag:
	@git tag -a -m "Tag as $(GITTAG)" -f $(GITTAG)
	@echo "Tagged as $(GITTAG)"
#	@hg push

Changelog:
	(GIT_DIR=.git git-log > .changelog.tmp && mv .changelog.tmp Changelog; rm -f .changelog.tmp) || (touch Changelog; echo 'git directory not found: installing possibly empty changelog.' >&2)

archive:
	@rm -f Changelog
	@make Changelog
	@rm -rf ${PKGNAME}-$(VERSION)/
	@python setup.py sdist --formats=bztar > /dev/null
	@echo "The archive is in dist/${PKGNAME}-$(VERSION).tar.bz2"

srpm: archive
	@rm -f $(SRPM)
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec
	@echo "The srpm is in $(SRPM)"

rpm: archive
	@rpmbuild --clean -bb ${PKGRPMFLAGS} ${PKGNAME}.spec
	@echo "The rpm is in $(RPM)"

rpminstall: rpm
	@rpm -ivh --force $(RPM)

release: tag srpm

install:
	@python setup.py install

clean:
	@rm -vf *.rpm 
	@rm -vrf noarch
	@rm -vf *.tar.gz
	@rm -vrf dist
	@rm -vf MANIFEST
	@rm -vf Changelog
