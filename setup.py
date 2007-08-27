from distutils.core import setup
import glob

setup(name='pungi',
      version='1.0.0',
      description='Distribution compose tool',
      author='Jesse Keating',
      author_email='jkeating@redhat.com',
      url='http://hosted.fedoraproject.org/projects/pungi',
      license='GPL',
      packages = ['pypungi'],
      scripts = ['pungi'],
      data_files=[('/usr/share/pungi', glob.glob('share/*'))]
      )

