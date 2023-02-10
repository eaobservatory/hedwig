# Copyright (C) 2017-2023 East Asian Observatory
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

from astropy.coordinates import SkyCoord

from hedwig.astro.catalog import parse_source_list, write_source_list
from hedwig.astro.coord import CoordSystem
from hedwig.compat import byte_type
from hedwig.type.collection import TargetCollection
from hedwig.type.simple import TargetFracTime, TargetObject

from .compat import TestCase

example_catalog = b'''IC1234 16:52:51 +56:52:40 ICRS 4.5 1
LDN123 3.75 -3.43 Galactic
M99 12:18:50 +14:24:59 ICRS 9.9
WithNote 12:34:56 +17:08:09 ICRS 1.2 3 "Flux = 1, Distance = 2"
'''


class AstroCatalogTest(TestCase):
    def test_catalog(self):
        # Parse the source catalog.
        catalog = parse_source_list(example_catalog)

        self.assertIsInstance(catalog, TargetCollection)
        self.assertEqual(len(catalog), 4)

        # Check the catalog entries.
        catalog_entries = list(catalog.values())

        self.assertEqual(catalog_entries[0].name, 'IC1234')
        self.assertAlmostEqual(catalog_entries[0].x, 253.2125)
        self.assertAlmostEqual(catalog_entries[0].y, 56.87777777777778)
        self.assertEqual(catalog_entries[0].system, CoordSystem.ICRS)
        self.assertAlmostEqual(catalog_entries[0].time, 4.5)
        self.assertEqual(catalog_entries[0].priority, 1)
        self.assertIsNone(catalog_entries[0].note)

        self.assertEqual(catalog_entries[1].name, 'LDN123')
        self.assertAlmostEqual(catalog_entries[1].x, 3.75)
        self.assertAlmostEqual(catalog_entries[1].y, -3.43)
        self.assertEqual(catalog_entries[1].system, CoordSystem.GAL)
        self.assertIsNone(catalog_entries[1].time)
        self.assertIsNone(catalog_entries[1].priority)
        self.assertIsNone(catalog_entries[1].note)

        self.assertEqual(catalog_entries[2].name, 'M99')
        self.assertAlmostEqual(catalog_entries[2].x, 184.70833333333334)
        self.assertAlmostEqual(catalog_entries[2].y, 14.41638888888889)
        self.assertEqual(catalog_entries[2].system, CoordSystem.ICRS)
        self.assertAlmostEqual(catalog_entries[2].time, 9.9)
        self.assertIsNone(catalog_entries[2].priority)
        self.assertIsNone(catalog_entries[2].note)

        self.assertEqual(catalog_entries[3].name, 'WithNote')
        self.assertAlmostEqual(catalog_entries[3].x, 188.73333333333335)
        self.assertAlmostEqual(catalog_entries[3].y, 17.135833333333334)
        self.assertEqual(catalog_entries[3].system, CoordSystem.ICRS)
        self.assertAlmostEqual(catalog_entries[3].time, 1.2)
        self.assertEqual(catalog_entries[3].priority, 3)
        self.assertEqual(catalog_entries[3].note, 'Flux = 1, Distance = 2')

        # Generate a new copy of the source catalog and ensure that it
        # matches the input catalog.
        generated = write_source_list(catalog)

        self.assertIsInstance(generated, byte_type)
        self.assertEqual(generated, example_catalog)

        # Test TargetCollection methods of the catalog.
        self.assertAlmostEqual(catalog.total_time(), 15.6)

        objects = catalog.to_object_list()
        self.assertIsInstance(objects, list)
        self.assertEqual(len(objects), 4)

        for object_ in objects:
            self.assertIsInstance(object_, TargetObject)
            self.assertIsInstance(object_.coord, SkyCoord)

        frac_times = catalog.to_frac_time_list()
        self.assertIsInstance(frac_times, list)
        self.assertEqual(len(frac_times), 3)

        for frac_time in frac_times:
            self.assertIsInstance(frac_time, TargetFracTime)
            self.assertIsInstance(frac_time.coord, SkyCoord)

        self.assertAlmostEqual(frac_times[0].frac_time, 0.2884615384615385)
        self.assertAlmostEqual(frac_times[1].frac_time, 0.6346153846153847)
        self.assertAlmostEqual(frac_times[2].frac_time, 0.07692307692307693)

        catalog_without_times = catalog.map_values(
            lambda x: x._replace(time=None))
        frac_times = catalog_without_times.to_frac_time_list()
        self.assertIsInstance(frac_times, list)
        self.assertEqual(len(frac_times), 4)

        for frac_time in frac_times:
            self.assertIsInstance(frac_time, TargetFracTime)
            self.assertIsInstance(frac_time.coord, SkyCoord)
            self.assertAlmostEqual(frac_time.frac_time, 0.25)
