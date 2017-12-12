# Copyright (C) 2017 East Asian Observatory
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

from hedwig.error import ConsistencyError
from hedwig.facility.ukirt.type import \
    UKIRTBrightness, UKIRTInstrument, \
    UKIRTRequest, UKIRTRequestCollection

from .dummy_db import DBTestCase


class DBUKIRTTest(DBTestCase):
    facility_spec = 'UKIRT'

    def test_ukirt_request(self):
        proposal_id = self._create_test_proposal(facility_code='ukirt')

        request = self.db.search_ukirt_request(proposal_id)
        self.assertIsInstance(request, UKIRTRequestCollection)
        self.assertEqual(len(request), 0)

        records = UKIRTRequestCollection()
        records[1] = UKIRTRequest(
            None, None,
            instrument=UKIRTInstrument.WFCAM,
            brightness=UKIRTBrightness.DARK, time=10.0)
        records[2] = UKIRTRequest(
            None, None,
            instrument=UKIRTInstrument.UFTI,
            brightness=UKIRTBrightness.BRIGHT, time=20.0)

        self.db.sync_ukirt_proposal_request(proposal_id, records)

        request = self.db.search_ukirt_request(proposal_id)
        self.assertIsInstance(request, UKIRTRequestCollection)
        self.assertEqual(len(request), 2)

        request_id = list(request.keys())
        request = list(request.values())

        self.assertIsInstance(request_id[0], int)
        self.assertIsInstance(request[0], UKIRTRequest)
        self.assertIsInstance(request[0].id, int)
        self.assertEqual(request[0].id, request_id[0])
        self.assertEqual(request[0].proposal_id, proposal_id)
        self.assertEqual(request[0].instrument, UKIRTInstrument.WFCAM)
        self.assertEqual(request[0].brightness, UKIRTBrightness.DARK)
        self.assertEqual(request[0].time, 10.0)

        self.assertIsInstance(request_id[1], int)
        self.assertIsInstance(request[1], UKIRTRequest)
        self.assertIsInstance(request[1].id, int)
        self.assertEqual(request[1].id, request_id[1])
        self.assertEqual(request[1].proposal_id, proposal_id)
        self.assertEqual(request[1].instrument, UKIRTInstrument.UFTI)
        self.assertEqual(request[1].brightness, UKIRTBrightness.BRIGHT)
        self.assertEqual(request[1].time, 20.0)

    def test_ukirt_allocation(self):
        proposal_id = self._create_test_proposal(facility_code='ukirt')

        allocation = self.db.search_ukirt_allocation(proposal_id)
        self.assertIsInstance(allocation, UKIRTRequestCollection)
        self.assertEqual(len(allocation), 0)

        records = UKIRTRequestCollection()
        records[1] = UKIRTRequest(
            None, None,
            instrument=UKIRTInstrument.WFCAM,
            brightness=UKIRTBrightness.DARK, time=10.0)
        records[2] = UKIRTRequest(
            None, None,
            instrument=UKIRTInstrument.UFTI,
            brightness=UKIRTBrightness.GREY, time=20.0)

        self.db.sync_ukirt_proposal_allocation(proposal_id, records)

        allocation = self.db.search_ukirt_allocation(proposal_id)
        self.assertIsInstance(allocation, UKIRTRequestCollection)
        self.assertEqual(len(allocation), 2)

        allocation_id = list(allocation.keys())
        allocation = list(allocation.values())

        self.assertIsInstance(allocation_id[0], int)
        self.assertIsInstance(allocation[0], UKIRTRequest)
        self.assertIsInstance(allocation[0].id, int)
        self.assertEqual(allocation[0].id, allocation_id[0])
        self.assertEqual(allocation[0].proposal_id, proposal_id)
        self.assertEqual(allocation[0].instrument, UKIRTInstrument.WFCAM)
        self.assertEqual(allocation[0].brightness, UKIRTBrightness.DARK)
        self.assertEqual(allocation[0].time, 10.0)

        self.assertIsInstance(allocation_id[1], int)
        self.assertIsInstance(allocation[1], UKIRTRequest)
        self.assertIsInstance(allocation[1].id, int)
        self.assertEqual(allocation[1].id, allocation_id[1])
        self.assertEqual(allocation[1].proposal_id, proposal_id)
        self.assertEqual(allocation[1].instrument, UKIRTInstrument.UFTI)
        self.assertEqual(allocation[1].brightness, UKIRTBrightness.GREY)
        self.assertEqual(allocation[1].time, 20.0)
