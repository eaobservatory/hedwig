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

from astropy.coordinates import SkyCoord

from insertnamehere.astro.coord import CoordSystem, \
    parse_coord, format_coord, \
    coord_to_dec_deg, coord_from_dec_deg
from insertnamehere.error import UserError


class AstroCoordTest(TestCase):
    def test_coordsystem(self):
        for val in (CoordSystem.ICRS, CoordSystem.GAL):
            self.assertIsInstance(val, int)
            self.assertIsInstance(CoordSystem.get_name(val), unicode)

        self.assertFalse(CoordSystem.is_valid(0))
        self.assertTrue(CoordSystem.is_valid(1))
        self.assertFalse(CoordSystem.is_valid(999))

        opt = CoordSystem.get_options()
        self.assertIsInstance(opt, OrderedDict)

        names = set(opt.values())
        for name in ('ICRS', 'Galactic'):
            self.assertIn(name, names)

    def test_parse_format(self):
        # Test basic input.
        c = parse_coord(CoordSystem.ICRS, '12:34:56', '+78:09:00', 'test')
        self.assertIsInstance(c, SkyCoord)

        self.assertAlmostEqual(c.ra.deg, 188.7333333)
        self.assertAlmostEqual(c.dec.deg, 78.15)

        # Check we can't format with the wrong system.
        with self.assertRaises(AssertionError):
            format_coord(CoordSystem.GAL, c)

        # Test decimal input.
        c = parse_coord(CoordSystem.ICRS, '15.0', '75', 'test')
        self.assertIsInstance(c, SkyCoord)

        self.assertAlmostEqual(c.ra.deg, 15)
        self.assertAlmostEqual(c.dec.deg, 75)
        self.assertEqual(format_coord(CoordSystem.ICRS, c)[0], '01:00:00')
        self.assertEqual(format_coord(CoordSystem.ICRS, c)[1], '+75:00:00')

        # Test some good coordinates.
        for (system, x, y) in [
                (CoordSystem.ICRS, '15:30:00', '+45:15:00'),
                (CoordSystem.ICRS, '05:30:15', '-00:15:00'),
                (CoordSystem.GAL, '135.75', '-15.25'),
                ]:
            c = parse_coord(system, x, y, 'test')

            formatted = format_coord(system, c)
            self.assertEqual(formatted[0], x)
            self.assertEqual(formatted[1], y)

        # Test some bad coordinates.
        for (system, x, y) in [
                (CoordSystem.ICRS, '25:30:00', '45:15:00'),
                (CoordSystem.ICRS, '15:300:00', '+45:15:00'),
                (CoordSystem.ICRS, '15:30:00', '-95:15:00'),
                (CoordSystem.GAL, '135.7.5', '-15.25'),
                ]:
            with self.assertRaises(UserError):
                c = parse_coord(system, x, y, 'test')
                print(repr(c))

    def test_dec_deg(self):
        c = parse_coord(CoordSystem.ICRS, '112.35', '8.13', 'test')
        (ra, dec) = coord_to_dec_deg(c)
        self.assertAlmostEqual(ra, 112.35)
        self.assertAlmostEqual(dec, 8.13)

        cc = coord_from_dec_deg(CoordSystem.ICRS, 21.34, 55.89)
        self.assertEqual(format_coord(CoordSystem.ICRS, cc)[0], '01:25:21.6')
        self.assertEqual(format_coord(CoordSystem.ICRS, cc)[1], '+55:53:24')
