# Copyright (C) 2016 East Asian Observatory
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

from unittest import TestCase

from hedwig.db.util import memoized
from hedwig.web.template_util import Counter


class DBUtilTest(TestCase):
    def test_memoized(self):
        n_call = Counter(0)
        self.assertEqual(n_call.value, 0)

        # Define functions which add/subtract their arguments and also
        # increment the n_call counter.
        @memoized
        def memo_add(db, x, y):
            n_call()
            return x + y

        @memoized
        def memo_sub(db, x, y):
            n_call()
            return x - y

        # Try calling the first function (add) with no cache.
        self.assertEqual(memo_add(None, None, 4, 5), 9)
        self.assertEqual(n_call.value, 1)

        self.assertEqual(memo_add(None, None, 4, 5), 9)
        self.assertEqual(n_call.value, 2)

        self.assertEqual(memo_add(None, None, 2, 3), 5)
        self.assertEqual(n_call.value, 3)

        # Set up cache dictionary and try calling with the cache.
        cache = {}

        self.assertEqual(memo_add(cache, None, 1, 2), 3)
        self.assertEqual(n_call.value, 4)

        self.assertEqual(memo_add(cache, None, 1, 2), 3)
        self.assertEqual(n_call.value, 4)

        self.assertEqual(memo_add(cache, None, 1, 2), 3)
        self.assertEqual(n_call.value, 4)

        self.assertEqual(cache, {
            ('memo_add', 1, 2): 3,
        })

        self.assertEqual(memo_add(cache, None, 33, 66), 99)
        self.assertEqual(n_call.value, 5)

        self.assertEqual(memo_add(cache, None, 1, 2), 3)
        self.assertEqual(n_call.value, 5)

        self.assertEqual(memo_add(cache, None, 1, 2), 3)
        self.assertEqual(n_call.value, 5)

        self.assertEqual(cache, {
            ('memo_add', 1, 2): 3,
            ('memo_add', 33, 66): 99,
        })

        # Try calling the second function (sub) and check we can distinguish
        # them.
        self.assertEqual(memo_sub(cache, None, 1, 2), -1)
        self.assertEqual(n_call.value, 6)

        self.assertEqual(memo_sub(cache, None, 1, 2), -1)
        self.assertEqual(n_call.value, 6)

        self.assertEqual(memo_add(cache, None, 1, 2), 3)
        self.assertEqual(n_call.value, 6)

        self.assertEqual(cache, {
            ('memo_add', 1, 2): 3,
            ('memo_add', 33, 66): 99,
            ('memo_sub', 1, 2): -1,
        })
