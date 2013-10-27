#!/usr/bin/python
# -*- coding: utf-8 -*-


import unittest

import os
import sys
import tempfile
import shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "pypungi")))

from arch import *


class TestArch(unittest.TestCase):

    def test_i386(self):
        arches = get_valid_arches("i386")
        self.assertEqual(arches, ['athlon', 'i686', 'i586', 'i486', 'i386', 'noarch'])

        arches = get_valid_arches("i386", multilib=False)
        self.assertEqual(arches, ['athlon', 'i686', 'i586', 'i486', 'i386', 'noarch'])

        arches = get_valid_arches("i386", add_src=True)
        self.assertEqual(arches, ['athlon', 'i686', 'i586', 'i486', 'i386', 'noarch', 'src'])

    def test_x86_64(self):
        arches = get_valid_arches("x86_64")
        self.assertEqual(arches, ['x86_64', 'athlon', 'i686', 'i586', 'i486', 'i386', 'noarch'])

        arches = get_valid_arches("x86_64", multilib=False)
        self.assertEqual(arches, ['x86_64', 'noarch'])

        arches = get_valid_arches("x86_64", add_src=True)
        self.assertEqual(arches, ['x86_64', 'athlon', 'i686', 'i586', 'i486', 'i386', 'noarch', 'src'])

    def test_get_compatible_arches(self):
        self.assertEqual(get_compatible_arches("noarch"), ["noarch"])
        self.assertEqual(get_compatible_arches("i386"), get_valid_arches("i386"))
        self.assertEqual(get_compatible_arches("i586"), get_valid_arches("i386"))
        self.assertEqual(get_compatible_arches("x86_64"), get_valid_arches("x86_64", multilib=False))
        self.assertEqual(get_compatible_arches("ppc64p7"), get_valid_arches("ppc64", multilib=False))

    def test_is_valid_arch(self):
        self.assertEqual(is_valid_arch("i386"), True)
        self.assertEqual(is_valid_arch("x86_64"), True)
        self.assertEqual(is_valid_arch("noarch"), True)
        self.assertEqual(is_valid_arch("src"), True)
        self.assertEqual(is_valid_arch("nosrc"), True)
        self.assertEqual(is_valid_arch("foo"), False)

    def test_split_name_arch(self):
        self.assertEqual(split_name_arch("package"), ("package", None))
        self.assertEqual(split_name_arch("package.x86_64"), ("package", "x86_64"))
        self.assertEqual(split_name_arch("package.foo"), ("package.foo", None))
        self.assertEqual(split_name_arch("i386"), ("i386", None)) # we suppose that $name is never empty

    def test_get_valid_multilib_arches(self):
        self.assertEqual(get_valid_multilib_arches("noarch"), [])
        self.assertEqual(get_valid_multilib_arches("athlon"), [])
        self.assertEqual(get_valid_multilib_arches("x86_64"), ['athlon', 'i686', 'i586', 'i486', 'i386'])


if __name__ == "__main__":
    unittest.main()
