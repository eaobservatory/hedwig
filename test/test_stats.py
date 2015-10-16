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

from random import randint, random
from unittest import TestCase

from hedwig.stats.quartile import label_quartiles


class StatsTest(TestCase):
    def test_label_quartiles(self):
        # Perform a few pre-defined tests.
        test_sets = [
            (
                {},
                {}
            ),
            (
                {
                    'a': 5,
                    'b': 9,
                    'c': 2,
                    'd': 3,
                },
                {
                    'a': 3,
                    'b': 4,
                    'c': 1,
                    'd': 2,
                }
            ),
            (
                {
                    'a': 5,
                    'b': 3,
                    'c': 10,
                    'd': 1,
                    'e': 2,
                    'f': 11,
                    'g': 9,
                    'h': 8,
                    'i': 4,
                    'j': 7,
                    'k': 0,
                    'l': 6,
                },
                {
                    'a': 2,
                    'b': 2,
                    'c': 4,
                    'd': 1,
                    'e': 1,
                    'f': 4,
                    'g': 4,
                    'h': 3,
                    'i': 2,
                    'j': 3,
                    'k': 1,
                    'l': 3,
                }
            )
        ]

        for (mapping, expected) in test_sets:
            self.assertEqual(label_quartiles(mapping), expected)

        # Perform some randomly defined tests.
        for i in range(0, 100):
            mapping = {x: random() for x in range(0, randint(0, 100))}
            result = label_quartiles(mapping)

            self.assertIsInstance(result, dict)
            self.assertEqual(set(mapping.keys()), set(result.keys()))

            # Divide the mapping into four lists by quartile number.
            quartiles = {1: [], 2: [], 3: [], 4: []}

            for (key, quartile) in result.items():
                self.assertIn(quartile, [1, 2, 3, 4])
                quartiles[quartile].append(mapping[key])

            # Check quartile divisions all similar lengths, but only if the
            # mapping doesn't contain duplicates, which can throw this off.
            if len(mapping) == len(set(mapping.values())):
                lengths = [len(x) for x in quartiles.values()]
                min_length = min(lengths)
                for length in lengths:
                    self.assertTrue((length == min_length) or
                                    (length == (min_length + 1)))

            # Check ordering of quartiles: all values in Q1 should be less
            # than those in Q2, etc.
            for q1 in [1, 2, 3, 4]:
                for q2 in [1, 2, 3, 4]:
                    if q1 == q2:
                        continue

                    for v1 in quartiles[q1]:
                        for v2 in quartiles[q2]:
                            if q1 < q2:
                                self.assertLess(v1, v2)
                            else:
                                self.assertGreater(v1, v2)
