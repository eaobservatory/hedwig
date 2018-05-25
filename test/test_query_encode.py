# Copyright (C) 2018 East Asian Observatory
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

from hedwig.web.query_encode import decode_query, encode_query
from hedwig.compat import string_type
from hedwig.error import ParseError

from .compat import TestCase


class QueryEncodeTest(TestCase):
    def test_query(self):
        # Test encoding a mixture of types.
        encoded = encode_query([42, 3.14, 'hello', True, False, None])
        self.assertIsInstance(encoded, string_type)
        self.assertEqual(encoded[0], 'M')
        decoded = decode_query(encoded)
        self.assertIsInstance(decoded[0], int)
        self.assertIsInstance(decoded[1], float)
        self.assertIsInstance(decoded[2], string_type)
        self.assertIs(decoded[3], True)
        self.assertIs(decoded[4], False)
        self.assertIsNone(decoded[5])
        self.assertEqual(decoded[0], 42)
        self.assertAlmostEqual(decoded[1], 3.14)
        self.assertEqual(decoded[2], 'hello')

        # Test various length strings (to check Base 64 re-padding).
        encoded = encode_query([])
        self.assertEqual(encoded, 'MkA')
        self.assertEqual(decode_query(encoded), [])

        encoded = encode_query([None])
        self.assertEqual(encoded, 'MkcA')
        self.assertEqual(decode_query(encoded), [None])

        encoded = encode_query([None, None])
        self.assertEqual(encoded, 'MksDA')
        self.assertEqual(decode_query(encoded), [None, None])

        encoded = encode_query([None, None, None])
        self.assertEqual(encoded, 'Mk8DAwA')
        self.assertEqual(decode_query(encoded), [None, None, None])

        encoded = encode_query([None, None, None, None])
        self.assertEqual(encoded, 'MlMDAwMA')
        self.assertEqual(decode_query(encoded), [None, None, None, None])

        # Check error handling.
        with self.assertRaisesRegex(ParseError, '^Unknown query encoding'):
            decode_query('Xxxxxxx')

        with self.assertRaisesRegex(ParseError, '^Unexpected character'):
            decode_query('M\u00b5')

        with self.assertRaisesRegex(ParseError, '^Could not decode'):
            decode_query('Mxxxxxx')
