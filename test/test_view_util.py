# Copyright (C) 2019 East Asian Observatory
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

from hedwig.view.util import float_or_none, int_or_none

from .compat import TestCase


class ViewUtilTestCase(TestCase):
    def test_float_or_none(self):
        self.assertIsNone(float_or_none(''))
        self.assertAlmostEqual(float_or_none('12.34'), 12.34)

    def test_int_or_none(self):
        self.assertIsNone(int_or_none(''))
        self.assertEqual(int_or_none('4'), 4)
