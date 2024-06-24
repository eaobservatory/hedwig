# Copyright (C) 2024 East Asian Observatory
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

from hedwig.view.query import truncate

from .compat import TestCase


class ViewQueryTest(TestCase):
    def test_truncate(self):
        value = 'Original Text'

        self.assertEqual(
            truncate(value, 20),
            'Original Text')

        self.assertEqual(
            truncate('Original Te', 11),
            'Original Te')

        self.assertEqual(
            truncate(value, 11),
            'Original T\u2026')

        self.assertEqual(
            truncate(value, 10),
            'Original\u2026')

        self.assertEqual(
            truncate(value, 9),
            'Original\u2026')

        self.assertEqual(
            truncate(value, 20, abbreviation='O.T.'),
            'Original Text')

        self.assertEqual(
            truncate(value, 10, abbreviation='O.T.'),
            'O.T.')
