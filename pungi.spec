%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           pungi
Version:        0.1.2
Release:        1%{?dist}
Summary:        Distribution compose tool

Group:          Development/Tools
License:        GPL
URL:            http://hosted.fedoraproject.org/projects/pungi
Source0:        http://linux.duke.edu/projects/%{name}/release/%{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Requires:       anaconda-runtime, yum => 3.0.3
BuildRequires:  python-devel

BuildArch:      noarch

%description
A tool to create anaconda based installation trees/isos of a set of rpms.


%prep
%setup -q


%build
%{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

 
%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc Authors Changelog COPYING GPL README ToDo
%config(noreplace) %{_sysconfdir}/pungi
# For noarch packages: sitelib
%{python_sitelib}/pypungi
%{_bindir}/pungi


%changelog
* Wed Dec 13 2006 Jesse Keating <jkeating@redhat.com> - 0.1.2-1
- Fix a bug in DVD repodata
- Add correct ppc boot args
- Set ppc arch correctly

* Mon Dec 11 2006 Jesse Keating <jkeating@redhat.com> - 0.1.1-2
- Need BR python-devel in rawhide

* Mon Dec 11 2006 Jesse Keating <jkeating@redhat.com> - 0.1.1-1
- Update to 0.1.1
- Add ability to get srpms
- Add ability to get relnote files
- Use a config file system
- Clean up some docs
- Add config files for composing FC6 respins

* Wed Nov  8 2006 Jesse Keating <jkeating@redhat.com> - 0.1.0-1
- Initial spec
