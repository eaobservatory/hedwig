# Copyright (C) 2015-2019 East Asian Observatory
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
from hedwig.error import ConsistencyError, Error, NoSuchRecord, UserError
from hedwig.type.collection import ResultCollection
from hedwig.type.enum import BaseCallType, FormatType, ReviewState
from hedwig.type.util import null_tuple
from hedwig.facility.jcmt.type import \
    JCMTAncillary, JCMTAvailable, JCMTAvailableCollection, \
    JCMTCallOptions, JCMTInstrument, JCMTOptions, \
    JCMTRequest, JCMTRequestCollection, \
    JCMTReview, JCMTReviewerExpertise, JCMTReviewerRole, \
    JCMTWeather

from .dummy_db import DBTestCase


class DBJCMTTest(DBTestCase):
    facility_spec = 'JCMT'

    def test_jcmt_call_options(self):
        (call_id, affiliation_id) = self._create_test_call()

        result = self.db.search_jcmt_call_options(call_id=call_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 0)

        with self.assertRaises(NoSuchRecord):
            self.db.get_jcmt_call_options(call_id)

        self.db.set_jcmt_call_options(
            call_id, time_min=None, time_max=200.0, time_excl_free=False)

        result = self.db.get_jcmt_call_options(call_id)
        self.assertIsInstance(result, JCMTCallOptions)
        self.assertEqual(result.call_id, call_id)
        self.assertIsNone(result.time_min)
        self.assertAlmostEqual(result.time_max, 200.0)
        self.assertFalse(result.time_excl_free)

        self.db.set_jcmt_call_options(
            call_id, time_min=5.0, time_max=None, time_excl_free=True)

        result = self.db.search_jcmt_call_options(call_id=call_id)
        self.assertEqual(list(result.keys()), [call_id])
        result = result[call_id]
        self.assertAlmostEqual(result.time_min, 5.0)
        self.assertIsNone(result.time_max)
        self.assertTrue(result.time_excl_free)

        with self.assertRaisesRegex(UserError, 'greater than max'):
            self.db.set_jcmt_call_options(
                call_id, time_min=20.0, time_max=10.0, time_excl_free=False)

        self.db.set_jcmt_call_options(
            call_id, time_min=10.0, time_max=20.0, time_excl_free=False)
        result = self.db.get_jcmt_call_options(call_id)
        self.assertAlmostEqual(result.time_min, 10.0)
        self.assertAlmostEqual(result.time_max, 20.0)

    def test_jcmt_options(self):
        proposal_id = self._create_test_proposal()

        with self.assertRaises(NoSuchRecord):
            self.db.get_jcmt_options(proposal_id)

        self.db.set_jcmt_options(proposal_id, target_of_opp=False,
                                 daytime=False, time_specific=False,
                                 polarimetry=False)

        options = self.db.get_jcmt_options(proposal_id)
        self.assertIsInstance(options, JCMTOptions)

        self.assertFalse(options.target_of_opp)
        self.assertFalse(options.daytime)
        self.assertFalse(options.time_specific)
        self.assertFalse(options.polarimetry)

        self.db.set_jcmt_options(proposal_id, target_of_opp=True,
                                 daytime=True, time_specific=True,
                                 polarimetry=True)

        options = self.db.get_jcmt_options(proposal_id)
        self.assertIsInstance(options, JCMTOptions)

        self.assertTrue(options.target_of_opp)
        self.assertTrue(options.daytime)
        self.assertTrue(options.time_specific)
        self.assertTrue(options.polarimetry)

        # Try search interface.
        result = self.db.search_jcmt_options(proposal_id=[proposal_id])
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(set(result.keys()), set((proposal_id,)))

        result_options = result[proposal_id]
        self.assertIsInstance(result_options, JCMTOptions)
        self.assertEqual(result_options, options)

        result = self.db.search_jcmt_options(proposal_id=[1999998, 1999999])
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 0)

    def test_jcmt_request(self):
        proposal_id = self._create_test_proposal()

        request = self.db.search_jcmt_request(proposal_id)
        self.assertIsInstance(request, JCMTRequestCollection)

        self.assertEqual(len(request), 0)

        records = JCMTRequestCollection()
        records[1] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTAncillary.NONE,
            JCMTWeather.BAND4, 5.0)
        records[2] = JCMTRequest(
            None, None, JCMTInstrument.SCUBA2, JCMTAncillary.NONE,
            JCMTWeather.BAND2, 10.0)

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
        self.assertEqual(request[0].ancillary, JCMTAncillary.NONE)
        self.assertEqual(request[0].weather, JCMTWeather.BAND4)
        self.assertEqual(request[0].time, 5.0)

        self.assertIsInstance(request[1], JCMTRequest)
        self.assertIsInstance(request[1].id, int)
        self.assertEqual(request[1].id, request_id[1])
        self.assertEqual(request[1].proposal_id, proposal_id)
        self.assertEqual(request[1].instrument, JCMTInstrument.SCUBA2)
        self.assertEqual(request[1].ancillary, JCMTAncillary.NONE)
        self.assertEqual(request[1].weather, JCMTWeather.BAND2)
        self.assertEqual(request[1].time, 10.0)

    def test_sync_jcmt_request(self):
        """
        Test a JCMT request sync operation which encounters uniqueness
        constraints.
        """

        proposal_id = self._create_test_proposal()

        records = JCMTRequestCollection()
        records[0] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTAncillary.NONE,
            JCMTWeather.BAND1, 10.0)
        records[1] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTAncillary.NONE,
            JCMTWeather.BAND5, 20.0)

        n = self.db.sync_jcmt_proposal_request(proposal_id, records)
        self.assertEqual(n, (2, 0, 0))

        records = self.db.search_jcmt_request(proposal_id)
        id1 = list(records.keys())

        self.assertEqual(records[id1[0]].weather, JCMTWeather.BAND1)
        self.assertEqual(records[id1[0]].time, 10.0)
        self.assertEqual(records[id1[1]].weather, JCMTWeather.BAND5)
        self.assertEqual(records[id1[1]].time, 20.0)

        # Swap the weather bands.
        records[id1[0]] = records[id1[0]]._replace(weather=JCMTWeather.BAND5)
        records[id1[1]] = records[id1[1]]._replace(weather=JCMTWeather.BAND1)

        n = self.db.sync_jcmt_proposal_request(proposal_id, records)
        self.assertEqual(n, (0, 2, 0))

        records = self.db.search_jcmt_request(proposal_id)
        id2 = list(records.keys())

        # Expect the first entry to have been re-inserted since we made a
        # circular update.
        self.assertEqual(id1[1], id2[0])
        self.assertNotEqual(id1[0], id2[1])

        self.assertEqual(records[id2[0]].weather, JCMTWeather.BAND1)
        self.assertEqual(records[id2[0]].time, 20.0)
        self.assertEqual(records[id2[1]].weather, JCMTWeather.BAND5)
        self.assertEqual(records[id2[1]].time, 10.0)

    def test_jcmt_allocation(self):
        proposal_id = self._create_test_proposal()

        allocation = self.db.search_jcmt_allocation(proposal_id)
        self.assertIsInstance(allocation, JCMTRequestCollection)
        self.assertEqual(len(allocation), 0)

        records = JCMTRequestCollection()
        records[0] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTAncillary.NONE,
            JCMTWeather.BAND2, 25.0)
        records[1] = JCMTRequest(
            None, None, JCMTInstrument.HARP, JCMTAncillary.NONE,
            JCMTWeather.BAND5, 75.0)

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
        self.assertEqual(allocation[0].ancillary, JCMTAncillary.NONE)
        self.assertEqual(allocation[0].weather, JCMTWeather.BAND2)
        self.assertEqual(allocation[0].time, 25.0)

        self.assertIsInstance(allocation[1], JCMTRequest)
        self.assertIsInstance(allocation[1].id, int)
        self.assertEqual(allocation[1].id, allocation_id[1])
        self.assertEqual(allocation[1].proposal_id, proposal_id)
        self.assertEqual(allocation[1].instrument, JCMTInstrument.HARP)
        self.assertEqual(allocation[1].ancillary, JCMTAncillary.NONE)
        self.assertEqual(allocation[1].weather, JCMTWeather.BAND5)
        self.assertEqual(allocation[1].time, 75.0)

    def test_sync_jcmt_allocation(self):
        """
        Test JCMT allocation sync operation including unique constraint
        avoidance.
        """

        proposal_id = self._create_test_proposal()

        records = JCMTRequestCollection()
        records[0] = JCMTRequest(
            None, None, JCMTInstrument.SCUBA2, JCMTAncillary.NONE,
            JCMTWeather.BAND1, 10.0)
        records[1] = JCMTRequest(
            None, None, JCMTInstrument.SCUBA2, JCMTAncillary.NONE,
            JCMTWeather.BAND2, 20.0)
        records[2] = JCMTRequest(
            None, None, JCMTInstrument.SCUBA2, JCMTAncillary.NONE,
            JCMTWeather.BAND3, 30.0)

        n = self.db.sync_jcmt_proposal_allocation(proposal_id, records)
        self.assertEqual(n, (3, 0, 0))

        records = self.db.search_jcmt_allocation(proposal_id=proposal_id)
        self.assertEqual(len(records), 3)

        id1 = list(records.keys())

        records[id1[0]] = records[id1[0]]._replace(weather=JCMTWeather.BAND2)
        records[id1[1]] = records[id1[1]]._replace(weather=JCMTWeather.BAND3)
        records[id1[2]] = records[id1[2]]._replace(weather=JCMTWeather.BAND4)

        n = self.db.sync_jcmt_proposal_allocation(proposal_id, records)
        self.assertEqual(n, (0, 3, 0))

        records = self.db.search_jcmt_allocation(proposal_id=proposal_id)

        id2 = list(records.keys())

        # There was no circular update loop so the identifiers should be
        # unchanged.
        self.assertEqual(id1, id2)

        for (record, id_, weather, time) in zip(
                records.values(), id2,
                [JCMTWeather.BAND2, JCMTWeather.BAND3, JCMTWeather.BAND4],
                [10.0, 20.0, 30.0]):
            self.assertEqual(record.id, id_)
            self.assertEqual(record.weather, weather)
            self.assertEqual(record.time, time)
            self.assertEqual(record.instrument, JCMTInstrument.SCUBA2)

    def test_jcmt_available(self):
        """
        Test methods associated with the "jcmt_available" table.
        """

        (call_id, affiliation_id) = self._create_test_call()

        records = self.db.search_jcmt_available(call_id)

        self.assertIsInstance(records, JCMTAvailableCollection)
        self.assertEqual(len(records), 0)

        records = JCMTAvailableCollection()
        records[1] = JCMTAvailable(None, 1, JCMTWeather.BAND1, 100.0)

        with self.assertRaisesRegex(ConsistencyError, 'call does not exist'):
            self.db.sync_jcmt_call_available(1999999, records)

        n = self.db.sync_jcmt_call_available(call_id, records)

        self.assertEqual(n, (1, 0, 0))

        records = self.db.search_jcmt_available(call_id=call_id)

        self.assertIsInstance(records, JCMTAvailableCollection)
        self.assertEqual(len(records), 1)

        for (id_, record) in records.items():
            self.assertIsInstance(id_, int)
            self.assertIsInstance(record, JCMTAvailable)
            self.assertEqual(record.id, id_)
            self.assertEqual(record.weather, JCMTWeather.BAND1)
            self.assertEqual(record.time, 100.0)

    def test_jcmt_review(self):
        """
        Test methods associated with the "jcmt_review" table.
        """

        role_class = JCMTReviewerRole

        proposal_id = self._create_test_proposal()
        person_id = self.db.add_person('Test Reviewer')

        reviewer_id = self.db.add_reviewer(
            role_class, proposal_id, person_id, role_class.CTTEE_PRIMARY)

        self.assertIsInstance(reviewer_id, int)

        with self.assertRaises(NoSuchRecord):
            self.db.get_jcmt_review(reviewer_id)

        with self.assertRaisesRegex(
                UserError, 'expertise level not recognised'):
            self.db.set_jcmt_review(
                role_class, reviewer_id, review_state=ReviewState.DONE,
                review=null_tuple(JCMTReview)._replace(expertise=999))

        with self.assertRaisesRegex(
                Error, 'expertise should be specified'):
            self.db.set_jcmt_review(
                role_class, reviewer_id, review_state=ReviewState.DONE,
                review=null_tuple(JCMTReview)._replace(expertise=None))

        self.db.set_jcmt_review(
            role_class, reviewer_id, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.INTERMEDIATE))

        jcmt_review = self.db.get_jcmt_review(reviewer_id)

        self.assertIsInstance(jcmt_review, JCMTReview)
        self.assertEqual(jcmt_review.expertise,
                         JCMTReviewerExpertise.INTERMEDIATE)

        # Repeat test with missing expertise, but not in the done state.
        self.db.set_jcmt_review(
            role_class, reviewer_id, review_state=ReviewState.PREPARATION,
            review=null_tuple(JCMTReview)._replace(expertise=None))

        jcmt_review = self.db.get_jcmt_review(reviewer_id)

        self.assertIsInstance(jcmt_review, JCMTReview)
        self.assertIsNone(jcmt_review.expertise)

        self.db.set_jcmt_review(
            role_class, reviewer_id, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.EXPERT))

        jcmt_review = self.db.get_jcmt_review(reviewer_id)

        self.assertIsNotNone(jcmt_review)
        self.assertIsInstance(jcmt_review, JCMTReview)
        self.assertEqual(jcmt_review.expertise,
                         JCMTReviewerExpertise.EXPERT)

        # Add a second review and try a multiple-reviewer search.
        reviewer_id_2 = self.db.add_reviewer(
            role_class, proposal_id, person_id, role_class.CTTEE_SECONDARY)

        self.assertIsInstance(reviewer_id_2, int)

        self.db.set_jcmt_review(
            role_class, reviewer_id_2, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.INTERMEDIATE))

        result = self.db.search_jcmt_review(
            reviewer_id=[reviewer_id, reviewer_id_2])

        self.assertIsInstance(result, ResultCollection)

        self.assertEqual(set(result.keys()), set((reviewer_id, reviewer_id_2)))

    def _create_test_proposal(self):
        (call_id, affiliation_id) = self._create_test_call()

        person_id = self.db.add_person('Test Person')

        return self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Test Title')
