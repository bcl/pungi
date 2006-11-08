from distutils.core import setup
import glob

setup(name='pungi',
      version='0.1.0',
      description='Distribution compose tool',
      author='Jesse Keating',
      author_email='jkeating@redhat.com',
      url='http://linux.duke.edu/projects/pungi',
      license='GPL',
      packages = ['pypungi'],
      scripts = ['pungi'],
      data_files=[('/etc/pungi', glob.glob('config/*'))]
      )

