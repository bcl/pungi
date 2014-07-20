from distutils.core import setup
import glob

setup(name='pungi',
      version='3.07', # make sure src/bin/pungi.py is updated to match
      description='Distribution compose tool',
      author='Dennis Gilmore',
      author_email='dgilmore@fedoraproject.org',
      url='http://fedorahosted.org/pungi',
      license='GPLv2',
      package_dir = {'': 'src'}, 
      packages = ['pypungi'],
      scripts = ['src/bin/pungi.py'],
      data_files=[
        ('/usr/share/pungi', glob.glob('share/*.xsl')),
        ('/usr/share/pungi', glob.glob('share/*.ks')),
        ('/usr/share/pungi/multilib', glob.glob('share/multilib/*')),
      ]
)

