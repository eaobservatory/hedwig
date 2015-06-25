# Copyright (C) 2015 East Asian Observatory
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful,but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,51 Franklin
# Street, Fifth Floor, Boston, MA  02110-1301, USA

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import OrderedDict
from unittest import TestCase

from hedwig.util import get_countries


class UtilTest(TestCase):
    def test_countries(self):
        c = get_countries()

        # Check we got a sensible-looking dictionary of countries.
        self.assertIsInstance(c, OrderedDict)
        self.assertLess(len(c), 300)
        self.assertGreater(len(c), 200)
        self.assertIn('AX', c)
        self.assertNotIn('BX', c)
        self.assertIn('CX', c)

        # Try countries with and without "common_name" records.
        self.assertEqual(c['TW'], 'Taiwan')
        self.assertEqual(c['JP'], 'Japan')

        # Check we get the same object if we call the function again.
        cc = get_countries()
        self.assertIs(cc, c)
