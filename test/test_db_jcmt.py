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

from datetime import datetime
from hedwig.type import FormatType
from hedwig.facility.jcmt.type import \
    JCMTInstrument, JCMTOptions, \
    JCMTRequest, JCMTRequestCollection, JCMTWeather

from .dummy_db import DBTestCase


class DBJCMTTest(DBTestCase):
    facility_spec = 'JCMT'

    def test_jcmt_options(self):
        proposal_id = self._create_test_proposal()

        options = self.db.get_jcmt_options(proposal_id)
        self.assertIsNone(options)

        self.db.set_jcmt_options(proposal_id, target_of_opp=False,
                                 daytime=False, time_specific=False)

        options = self.db.get_jcmt_options(proposal_id)
        self.assertIsInstance(options, JCMTOptions)

        self.assertFalse(options.target_of_opp)
        self.assertFalse(options.daytime)
        self.assertFalse(options.time_specific)

        self.db.set_jcmt_options(proposal_id, target_of_opp=True,
                                 daytime=True, time_specific=True)

        options = self.db.get_jcmt_options(proposal_id)
        self.assertIsInstance(options, JCMTOptions)

        self.assertTrue(options.target_of_opp)
        self.assertTrue(options.daytime)
        self.assertTrue(options.time_specific)

    def test_jcmt_request(self):
        proposal_id = self._create_test_proposal()

        request = self.db.search_jcmt_request(proposal_id)
        self.assertIsInstance(request, JCMTRequestCollection)

        self.assertEqual(len(request), 0)

        records = JCMTRequestCollection()
        records[1] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTWeather.BAND4, 5.0)
        records[2] = JCMTRequest(
            None, None, JCMTInstrument.SCUBA2, JCMTWeather.BAND2, 10.0)

        self.db.sync_jcmt_proposal_request(proposal_id, records)

        request = self.db.search_jcmt_request(proposal_id)
        self.assertEqual(len(request), 2)

        request_id = list(request.keys())
        request = list(request.values())

        self.assertIsInstance(request[0], JCMTRequest)
        self.assertIsInstance(request[0].id, int)
        self.assertEqual(request[0].id, request_id[0])
        self.assertEqual(request[0].proposal_id, proposal_id)
        self.assertEqual(request[0].instrument, JCMTInstrument.HARP)
        self.assertEqual(request[0].weather, JCMTWeather.BAND4)
        self.assertEqual(request[0].time, 5.0)

        self.assertIsInstance(request[1], JCMTRequest)
        self.assertIsInstance(request[1].id, int)
        self.assertEqual(request[1].id, request_id[1])
        self.assertEqual(request[1].proposal_id, proposal_id)
        self.assertEqual(request[1].instrument, JCMTInstrument.SCUBA2)
        self.assertEqual(request[1].weather, JCMTWeather.BAND2)
        self.assertEqual(request[1].time, 10.0)

    def test_jcmt_allocation(self):
        proposal_id = self._create_test_proposal()

        allocation = self.db.search_jcmt_allocation(proposal_id)
        self.assertIsInstance(allocation, JCMTRequestCollection)
        self.assertEqual(len(allocation), 0)

        records = JCMTRequestCollection()
        records[0] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTWeather.BAND2, 25.0)
        records[1] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTWeather.BAND5, 75.0)

        self.db.sync_jcmt_proposal_allocation(proposal_id, records)

        allocation = self.db.search_jcmt_allocation(proposal_id)
        self.assertIsInstance(allocation, JCMTRequestCollection)
        self.assertEqual(len(allocation), 2)

        allocation_id = list(allocation.keys())
        allocation = list(allocation.values())

        self.assertIsInstance(allocation[0], JCMTRequest)
        self.assertIsInstance(allocation[0].id, int)
        self.assertEqual(allocation[0].id, allocation_id[0])
        self.assertEqual(allocation[0].proposal_id, proposal_id)
        self.assertEqual(allocation[0].instrument, JCMTInstrument.HARP)
        self.assertEqual(allocation[0].weather, JCMTWeather.BAND2)
        self.assertEqual(allocation[0].time, 25.0)

        self.assertIsInstance(allocation[1], JCMTRequest)
        self.assertIsInstance(allocation[1].id, int)
        self.assertEqual(allocation[1].id, allocation_id[1])
        self.assertEqual(allocation[1].proposal_id, proposal_id)
        self.assertEqual(allocation[1].instrument, JCMTInstrument.HARP)
        self.assertEqual(allocation[1].weather, JCMTWeather.BAND5)
        self.assertEqual(allocation[1].time, 75.0)

    def _create_test_proposal(self):
        facility_id = self.db.ensure_facility('jcmt')
        semester_id = self.db.add_semester(
            facility_id, 'test', 'test',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        queue_id = self.db.add_queue(facility_id, 'test', 'test')
        call_id = self.db.add_call(
            semester_id, queue_id,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
            FormatType.PLAIN)
        affiliation_id = self.db.add_affiliation(queue_id, 'test')
        person_id = self.db.add_person('Test Person')
        return self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Test Title')
