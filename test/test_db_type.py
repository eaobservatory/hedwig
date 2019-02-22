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

from hedwig.db.type import encoder
from hedwig.type.misc import SectionedList

from .compat import TestCase


class DBTypeTest(TestCase):
    def test_encoder(self):
        self.assertEqual(
            encoder.encode({'location': 'caf\u00e9'}),
            '{"location": "caf\u00e9"}')

        l = SectionedList()
        l.extend(['a', 'b', 'c'], 'letters')

        self.assertEqual(
            encoder.encode(l),
            '{"letters": ["a", "b", "c"]}')
