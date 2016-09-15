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

from hedwig.compat import byte_type
from hedwig.file.csv import CSVWriter

from .compat import TestCase


class FileTest(TestCase):
    def test_create_csv(self):
        writer = CSVWriter()

        writer.add_row([1, 'a'])
        writer.add_row([2, 'b'])

        csv = writer.get_csv()
        self.assertIsInstance(csv, byte_type)

        self.assertEqual(csv, b'1,"a"\n2,"b"\n')
