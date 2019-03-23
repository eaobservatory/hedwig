# Copyright (C) 2019 East Asian Observatory
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

from hedwig.admin.proposal import close_call_proposals, close_mid_call, \
    finalize_call_review, send_call_proposal_feedback
from hedwig.compat import first_value
from hedwig.type.collection import CallMidCloseCollection
from hedwig.type.enum import BaseCallType, ProposalState
from hedwig.type.simple import CallMidClose
from hedwig.type.util import null_tuple

from .dummy_db import DBTestCase
from .util import null_log


class AdminProposalTestCase(DBTestCase):
    def test_proposal_admin_call(self):
        inst_1 = self.db.add_institution('I 1', '', '', '', 'US')
        person_id = self.db.add_person('Test Person', institution_id=inst_1)

        # Create proposals for a regular call.
        (call_1, aff_id) = self._create_test_call(facility_name='test_1')

        proposal_1_a = self.db.add_proposal(call_1, person_id, aff_id, 'Title')
        proposal_1_b = self.db.add_proposal(call_1, person_id, aff_id, 'Title')
        proposal_1_c = self.db.add_proposal(call_1, person_id, aff_id, 'Title')
        proposal_1_d = self.db.add_proposal(call_1, person_id, aff_id, 'Title')
        proposal_1_e = self.db.add_proposal(call_1, person_id, aff_id, 'Title')

        # Create proposals for a multiclose call.  Use a different facility
        # to avoid clashes in '_create_test_call' database structures.
        # Note: this method sets dates 1999-09-01 - 1999-09-30.
        (call_2, aff_id) = self._create_test_call(
            call_type=BaseCallType.MULTICLOSE, facility_name='test_2')

        self.db.sync_call_call_mid_close(
            call_2, CallMidCloseCollection((
                ('new1', null_tuple(CallMidClose)._replace(
                    date=datetime(1999, 9, 10))),
                ('new2', null_tuple(CallMidClose)._replace(
                    date=datetime(1999, 9, 15))),
                ('new3', null_tuple(CallMidClose)._replace(
                    date=datetime(1999, 9, 20))),

            )))
        (mid_1, mid_2, mid_3) = self.db.search_call_mid_close().keys()

        proposal_2_a = self.db.add_proposal(call_2, person_id, aff_id, 'Title')
        proposal_2_b = self.db.add_proposal(call_2, person_id, aff_id, 'Title')
        proposal_2_c = self.db.add_proposal(call_2, person_id, aff_id, 'Title')
        proposal_2_d = self.db.add_proposal(call_2, person_id, aff_id, 'Title')
        proposal_2_e = self.db.add_proposal(call_2, person_id, aff_id, 'Title')

        # Create dictionary of proposal ID values and thier states.
        proposal_ids = [
            proposal_1_a, proposal_1_b, proposal_1_c, proposal_1_d, proposal_1_e,
            proposal_2_a, proposal_2_b, proposal_2_c, proposal_2_d, proposal_2_e]
        proposals = {x: ProposalState.PREPARATION for x in proposal_ids}
        institutions = {x: inst_1 for x in proposal_ids}

        # Check initial status.
        self._check_proposal_state(proposals)
        self._check_member_institution(institutions)
        self._check_mid_close_closed([False, False, False])

        # Close first intermediate closing -- nothing should happen.
        n_closed = close_mid_call(self.db, call_2, mid_1)
        self.assertEqual(n_closed, 0)

        inst_2 = self.db.add_institution('I 2', '', '', '', 'US')
        self.db.update_person(person_id, institution_id=inst_2)
        institutions.update({
            proposal_1_a: inst_2,
            proposal_1_b: inst_2,
            proposal_1_c: inst_2,
            proposal_1_d: inst_2,
            proposal_1_e: inst_2,
            proposal_2_a: inst_2,
            proposal_2_b: inst_2,
            proposal_2_c: inst_2,
            proposal_2_d: inst_2,
            proposal_2_e: inst_2,
        })

        self._check_proposal_state(proposals)
        self._check_member_institution(institutions)
        self._check_mid_close_closed([True, False, False])

        # Update proposal states.
        self.db.update_proposal(proposal_1_a, state=ProposalState.WITHDRAWN)
        self.db.update_proposal(proposal_1_b, state=ProposalState.SUBMITTED)
        self.db.update_proposal(proposal_1_c, state=ProposalState.ABANDONED)
        self.db.update_proposal(proposal_2_a, state=ProposalState.WITHDRAWN)
        self.db.update_proposal(proposal_2_b, state=ProposalState.SUBMITTED)

        proposals.update({
            proposal_1_a: ProposalState.WITHDRAWN,
            proposal_1_b: ProposalState.SUBMITTED,
            proposal_1_c: ProposalState.ABANDONED,
            proposal_2_a: ProposalState.WITHDRAWN,
            proposal_2_b: ProposalState.SUBMITTED})

        self._check_proposal_state(proposals)

        # Close second intermediate closing.
        n_closed = close_mid_call(self.db, call_2, mid_2)
        self.assertEqual(n_closed, 1)

        proposals.update({
            proposal_2_b: ProposalState.REVIEW})

        inst_3 = self.db.add_institution('I 3', '', '', '', 'US')
        self.db.update_person(person_id, institution_id=inst_3)

        institutions.update({
            proposal_1_a: inst_3,
            proposal_1_b: inst_3,
            proposal_1_c: inst_3,
            proposal_1_d: inst_3,
            proposal_1_e: inst_3,
            proposal_2_a: inst_3,
            proposal_2_c: inst_3,
            proposal_2_d: inst_3,
            proposal_2_e: inst_3,
        })

        self._check_proposal_state(proposals)
        self._check_member_institution(institutions)
        self._check_mid_close_closed([True, True, False])

        # Update proposal states again.
        self.db.update_proposal(proposal_2_c, state=ProposalState.SUBMITTED)

        proposals.update({
            proposal_2_c: ProposalState.SUBMITTED})

        self._check_proposal_state(proposals)

        # Close third intermediate closing.
        n_closed = close_mid_call(self.db, call_2, mid_3)
        self.assertEqual(n_closed, 1)

        proposals.update({
            proposal_2_c: ProposalState.REVIEW})

        inst_4 = self.db.add_institution('I 4', '', '', '', 'US')
        self.db.update_person(person_id, institution_id=inst_4)

        institutions.update({
            proposal_1_a: inst_4,
            proposal_1_b: inst_4,
            proposal_1_c: inst_4,
            proposal_1_d: inst_4,
            proposal_1_e: inst_4,
            proposal_2_a: inst_4,
            proposal_2_d: inst_4,
            proposal_2_e: inst_4,
        })

        self._check_proposal_state(proposals)
        self._check_member_institution(institutions)
        self._check_mid_close_closed([True, True, True])

        # Advance to final review.
        (n_update, n_error) = finalize_call_review(self.db, call_2)
        self.assertEqual(n_update, 2)
        self.assertEqual(n_error, 0)

        proposals.update({
            proposal_2_b: ProposalState.FINAL_REVIEW,
            proposal_2_c: ProposalState.FINAL_REVIEW})

        self._check_proposal_state(proposals)

        # Submit final proposals.
        self.db.update_proposal(proposal_2_d, state=ProposalState.SUBMITTED)

        proposals.update({
            proposal_2_d: ProposalState.SUBMITTED})

        self._check_proposal_state(proposals)
        self._check_member_institution(institutions)

        # Close calls themselves.
        # Suppress the logger warning about a proposal already being
        # in the ABANDONED state.
        with null_log('hedwig.admin.proposal'):
            n_closed = close_call_proposals(self.db, call_1)

        self.assertEqual(n_closed, 4)

        n_closed = close_call_proposals(self.db, call_2)

        self.assertEqual(n_closed, 3)

        proposals.update({
            proposal_1_a: ProposalState.ABANDONED,
            proposal_1_b: ProposalState.REVIEW,
            proposal_1_d: ProposalState.ABANDONED,
            proposal_1_e: ProposalState.ABANDONED,
            proposal_2_a: ProposalState.ABANDONED,
            proposal_2_d: ProposalState.REVIEW,
            proposal_2_e: ProposalState.ABANDONED})

        inst_5 = self.db.add_institution('I 5', '', '', '', 'US')
        self.db.update_person(person_id, institution_id=inst_5)

        institutions.update({
            proposal_1_c: inst_5})

        self._check_proposal_state(proposals)
        self._check_member_institution(institutions)

        # Advance to final review again.
        (n_update, n_error) = finalize_call_review(self.db, call_1)
        self.assertEqual(n_update, 1)
        self.assertEqual(n_error, 0)

        (n_update, n_error) = finalize_call_review(self.db, call_2)
        self.assertEqual(n_update, 1)
        self.assertEqual(n_error, 0)

        proposals.update({
            proposal_1_b: ProposalState.FINAL_REVIEW,
            proposal_2_d: ProposalState.FINAL_REVIEW})

        self._check_proposal_state(proposals)

    def _check_proposal_state(self, proposal_state_expected):
        self.assertEqual(
            {x.id: x.state for x in self.db.search_proposal().values()},
            proposal_state_expected)

    def _check_member_institution(self, institution_expected):
        self.assertEqual(
            {x.id: first_value(x.members).resolved_institution_id
             for x in self.db.search_proposal(with_members=True).values()},
            institution_expected)

    def _check_mid_close_closed(self, closed_expected):
        self.assertEqual(
            [x.closed for x in self.db.search_call_mid_close().values()],
            closed_expected)
