PKGNAME=pungi
VERSION=$(shell rpm -q --qf "%{VERSION}\n" --specfile ${PKGNAME}.spec)
RELEASE=$(shell rpm -q --qf "%{RELEASE}\n" --specfile ${PKGNAME}.spec)
HGTAG=${PKGNAME}-$(VERSION)-$(RELEASE)
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"

RPM="noarch/${PKGNAME}-$(VERSION)-$(RELEASE).noarch.rpm"
SRPM="${PKGNAME}-$(VERSION)-$(RELEASE).src.rpm"


default: all

all:
	@echo "Nothing to do"

tag:
	@hg tag -m "$(HGTAG)" $(HGTAG)
#	@hg push

archive:
	@rm -rf ${PKGNAME}-$(VERSION)/
	@python setup.py sdist > /dev/null
	@echo "The archive is in dist/${PKGNAME}-$(VERSION).tar.gz"

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
