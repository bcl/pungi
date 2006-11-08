PKGNAME=pungi
VERSION=$(shell rpm -q --qf "%{VERSION}\n" --specfile ${PKGNAME}.spec)
RELEASE=$(shell rpm -q --qf "%{RELEASE}\n" --specfile ${PKGNAME}.spec)
HGTAG=${PKGNAME}-$(VERSION)-$(RELEASE)
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}"

default: all

all:
	@echo "Nothing to do"

tag:
	@hg tag -m "$(HGTAG)" $(HGTAG)
#	@hg push

archive: tag
	@rm -rf ${PKGNAME}-$(VERSION)/
	@python setup.py sdist > /dev/null
	@echo "The archive is in dist/${PKGNAME}-$(VERSION).tar.gz"

srpm: archive
	@rm -f ${PKGNAME}-$(VERSION)-$(RELEASE).src.rpm
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec
	@echo "The srpm is in ${PKGNAME}-$(VERSION)-$(RELEASE).src.rpm"

