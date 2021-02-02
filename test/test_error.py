# Copyright (C) 2021 East Asian Observatory
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

from hedwig.error import DatabaseError, Error, _truncate_message

from .compat import TestCase


class ErrorTest(TestCase):
    def test_database_error(self):
        ten = '0123456789'
        message = ten * 40

        exc = Error(message)
        dbe = DatabaseError(exc)

        self.assertEqual(dbe.message, message)
        self.assertIs(dbe.orig, exc)
        self.assertTrue(dbe.__suppress_context__)

        dbe = DatabaseError(Error(ten * 60))
        self.assertEqual(dbe.message, (ten * 20) + '...' + (ten * 20))

    def test_truncate_message(self):
        ten = '0123456789'

        self.assertEqual(_truncate_message(ten, 20, 2, 2), ten)
        self.assertEqual(_truncate_message(ten, 5, 2, 2), '01...89')
        self.assertEqual(_truncate_message(ten, 5, 3, 3), '012...789')
