# Copyright (C) 2026 East Asian Observatory
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

from datetime import datetime, time, timedelta

from astropy.coordinates import EarthLocation

from hedwig.astro.coord import CoordSystem, parse_coord
from hedwig.facility.generic.view import Generic
from hedwig.facility.generic.tool_avail import AvailabilityTool
from hedwig.type.simple import FacilityObsInfo, TargetObject
from hedwig.type.util import null_tuple
from hedwig.view.tool import BaseTargetTool

from .compat import TestCase


class AvailToolTest(TestCase):
    def test_search(self):
        facility = DummyFacility(id_=None)
        tool = AvailabilityTool(facility=facility, id_=None)
        self.assertIsInstance(tool, BaseTargetTool)
        self.assertIsInstance(tool.location, EarthLocation)

        ctx = tool._do_availability_search(
            target_objects=[
                TargetObject(
                    name='Test',
                    system=None,
                    # Target object which should transit at midnight but
                    # be low enough not to be seen in the adjacent hours.
                    coord=parse_coord(
                        CoordSystem.ICRS,
                        '6:21:26',
                        '-39:00:00',
                        'Test'),
                    time=None,
                ),
            ],
            date_start=datetime(2027, 1, 1),
            date_end=datetime(2027, 1, 1))
        self.assertIsInstance(ctx, dict)

        dates = ctx['avail_date']
        times = ctx['avail_time']

        self.assertEqual(list(dates.keys()), ['2027-01-01'])
        self.assertEqual(times, ['09:00', '10:00', '11:00'])

        # Target only seen in the central time.
        self.assertEqual(dates['2027-01-01'], [0, 1, 0])

        # TODO: check other elements of the ctx dictionary.


class DummyFacility(Generic):
    def get_observing_info(self):
        # Location of JCMT but time limited to two hours around midnight.
        return null_tuple(FacilityObsInfo)._replace(
            geo_x=-5464588.652191697,
            geo_y=-2493003.0215722183,
            geo_z=2150655.6609171447,
            time_start=time(9, 0),
            time_duration=timedelta(hours=2),
            el_min=30)
