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

from contextlib import contextmanager
from datetime import datetime

from hedwig.type.enum import BaseReviewerRole, FormatType, GroupType, \
    ProposalState
from hedwig.view import auth
from hedwig.view.people import _update_session_user, _update_session_person
from hedwig.web.util import session

from .dummy_app import WebAppTestCase


# States for which we will perform tests.  (In vaguely chronological order.)
proposal_states = [
    ProposalState.PREPARATION,
    ProposalState.WITHDRAWN,
    ProposalState.SUBMITTED,
    ProposalState.REVIEW,
    ProposalState.FINAL_REVIEW,
    ProposalState.ACCEPTED,
    ProposalState.REJECTED,
    ProposalState.ABANDONED,
]


class WebAppAuthTestCase(WebAppTestCase):
    def test_view_auth(self):
        # Display default assert method failure messages as well as our
        # identifiers.
        self.longMessage = True

        # Use basic reviewer role class.
        role_class = BaseReviewerRole

        # Set up test database entries.
        facility_id = self.db.ensure_facility('test')
        facility_other = self.db.ensure_facility('other')

        semester_id = self.db.add_semester(
            facility_id, 'Test', 'T',
            datetime(2000, 1, 1), datetime(2000, 7, 1))

        queue_a = self.db.add_queue(facility_id, 'Queue A', 'A')
        queue_b = self.db.add_queue(facility_id, 'Queue B', 'B')

        affiliation_a = self.db.add_affiliation(queue_a, 'Test')
        affiliation_b = self.db.add_affiliation(queue_b, 'Test')

        call_options = (datetime(1999, 9, 1), datetime(1999, 9, 30),
                        100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
                        FormatType.PLAIN)

        call_a = self.db.add_call(semester_id, queue_a, *call_options)
        call_b = self.db.add_call(semester_id, queue_b, *call_options)

        institution_1 = self.db.add_institution('Inst 1', '', '', '', 'AX')
        institution_2 = self.db.add_institution('Inst 2', '', '', '', 'AX')
        institution_3 = self.db.add_institution('Inst 3', '', '', '', 'AX')

        user_admin = self.db.add_user('admin', 'pass')
        person_admin = self.db.add_person('Admin', user_id=user_admin)
        self.db.update_person(person_admin, admin=True)

        # Create proposals and member profiles.
        # Naming convention: <queue><proposal><info>
        # Where <info> is: Editor / Member / Unregistered / Public
        user_a1e = self.db.add_user('a1e', 'pass')
        person_a1e = self.db.add_person('Person A 1 E', user_id=user_a1e)
        self.db.update_person(person_a1e, institution_id=institution_1)

        person_a1u = self.db.add_person('Person A 1 U', user_id=None)
        self.db.update_person(person_a1u, institution_id=institution_2)

        user_a2e = self.db.add_user('a2e', 'pass')
        person_a2e = self.db.add_person('Person A 2 E', user_id=user_a2e)
        self.db.update_person(person_a2e, institution_id=institution_2)

        user_a2m = self.db.add_user('a2r', 'pass')
        person_a2m = self.db.add_person('Person A 2 R', user_id=user_a2m)

        person_a2u = self.db.add_person('Person A 2 U', user_id=None)

        user_a2p = self.db.add_user('a2p', 'pass')
        person_a2p = self.db.add_person('Person A 2 P', user_id=user_a2p)
        self.db.update_person(person_a2p, public=True)

        user_b1e = self.db.add_user('b1e', 'pass')
        person_b1e = self.db.add_person('Person B 1 E', user_id=user_b1e)

        person_b1u = self.db.add_person('Person B 1 U', user_id=None)
        self.db.update_person(person_b1u, institution_id=institution_3)

        user_b2e = self.db.add_user('b2e', 'pass')
        person_b2e = self.db.add_person('Person B 2 E', user_id=user_b2e)

        person_b2u = self.db.add_person('Person B 2 U', user_id=None)
        self.db.update_person(person_b2u, institution_id=institution_3)

        proposal_a1 = self.db.add_proposal(
            call_a, person_a1e, affiliation_a, 'Test proposal A 1')
        self.db.add_member(proposal_a1, person_a1u, affiliation_a)

        proposal_a2 = self.db.add_proposal(
            call_a, person_a2e, affiliation_a, 'Test proposal A 2')
        self.db.add_member(proposal_a2, person_a2m, affiliation_a)
        self.db.add_member(proposal_a2, person_a2u, affiliation_a)
        self.db.add_member(proposal_a2, person_a2p, affiliation_a)

        proposal_b1 = self.db.add_proposal(
            call_b, person_b1e, affiliation_b, 'Test proposal B 1')
        self.db.add_member(proposal_b1, person_b1u, affiliation_b)

        proposal_b2 = self.db.add_proposal(
            call_b, person_b2e, affiliation_b, 'Test proposal B 2')
        self.db.add_member(proposal_b2, person_b2u, affiliation_b)

        # Create review coordinator profiles.
        user_a_rc = self.db.add_user('arc', 'pass')
        person_a_rc = self.db.add_person('Person A RC', user_id=user_a_rc)
        self.db.add_group_member(queue_a, GroupType.COORD, person_a_rc)

        user_b_rc = self.db.add_user('brc', 'pass')
        person_b_rc = self.db.add_person('Person B RC', user_id=user_b_rc)
        self.db.add_group_member(queue_b, GroupType.COORD, person_b_rc)

        # Create reviews and reviewer profiles.
        # Naming convention: <info> = r<type><options>
        # Where <type> is: External / Technical / Committee
        # And <options> are: Unregistered
        # -- technical reviewers
        user_a1rt = self.db.add_user('a1rt', 'pass')
        person_a1rt = self.db.add_person('Person A 1 RT', user_id=user_a1rt)
        self.db.add_group_member(queue_a, GroupType.TECH, person_a1rt)
        reviewer_a1rt = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rt, role_class.TECH)

        # -- external reviewers:
        user_a1re = self.db.add_user('a1re', 'pass')
        person_a1re = self.db.add_person('Person A 1 RE', user_id=user_a1re)
        reviewer_a1re = self.db.add_reviewer(
            role_class, proposal_a1, person_a1re, role_class.EXTERNAL)

        person_a1reu = self.db.add_person('Person A 1 REU', user_id=None)
        reviewer_a1reu = self.db.add_reviewer(
            role_class, proposal_a1, person_a1reu, role_class.EXTERNAL)

        person_b1reu = self.db.add_person('Person B 1 REU', user_id=None)
        reviewer_b1reu = self.db.add_reviewer(
            role_class, proposal_b1, person_b1reu, role_class.EXTERNAL)

        # -- committee reviwers:
        user_a1rc1 = self.db.add_user('a1rc1', 'pass')
        person_a1rc1 = self.db.add_person('Person A 1 RC1', user_id=user_a1rc1)
        self.db.add_group_member(queue_a, GroupType.CTTEE, person_a1rc1)
        reviewer_a1rc1 = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rc1, role_class.CTTEE_PRIMARY)

        user_a1rc2 = self.db.add_user('a1rc2', 'pass')
        person_a1rc2 = self.db.add_person('Person A 1 RC2', user_id=user_a1rc2)
        self.db.add_group_member(queue_a, GroupType.CTTEE, person_a1rc2)
        reviewer_a1rc2 = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rc2, role_class.CTTEE_SECONDARY)

        # Test authorization for call reviews.
        for test_case in [
                # No general access to call reviews.
                (1,  person_a1e,   False, call_a, auth.no),
                (2,  person_a1e,   False, call_b, auth.no),
                # Admin has full access but only when is_admin is set.
                (3,  person_admin, False, call_a, auth.no),
                (4,  person_admin, False, call_b, auth.no),
                (5,  person_admin, True,  call_a, auth.yes),
                (6,  person_admin, True,  call_b, auth.yes),
                # Review coordinators have full access to corresponding call.
                (7,  person_a_rc,  False, call_a, auth.yes),
                (8,  person_a_rc,  False, call_b, auth.no),
                (9,  person_b_rc,  False, call_a, auth.no),
                (10, person_b_rc,  False, call_b, auth.yes),
                # Committee members have view access to corresponding call.
                (11, person_a1rc1, False, call_a, auth.view_only),
                (12, person_a1rc2, False, call_a, auth.view_only),
                (13, person_a1rc1, False, call_b, auth.no),
                (14, person_a1rc2, False, call_b, auth.no),
                ]:
            self._test_auth_call_review(*test_case)

        # Test authorization for person profiles.
        for test_case in [
                # Each person has full access to their own profile only.
                (1,  person_a1e,   False, person_a1e,   auth.yes),
                (2,  person_a1e,   False, person_a2e,   auth.no),
                (3,  person_a2e,   True,  person_a1e,   auth.no),
                (4,  person_a2e,   True,  person_a2e,   auth.yes),
                (5,  person_a_rc,  False, person_a1e,   auth.no),
                (6,  person_b_rc,  False, person_a2e,   auth.no),
                # Admin has full access but only when is_admin is set.
                (7,  person_admin, False, person_a1e,   auth.no),
                (8,  person_admin, False, person_a2e,   auth.no),
                (9,  person_admin, True,  person_a1e,   auth.yes),
                (10, person_admin, True,  person_a2e,   auth.yes),
                # Public user: visible to others.
                (11, person_a2p,   False, person_a2p,   auth.yes),
                (12, person_a1e,   False, person_a2p,   auth.view_only),
                (13, person_admin, False, person_a2p,   auth.view_only),
                (14, person_admin, True,  person_a2p,   auth.yes),
                # Unregistered member: editable by proposal editors.
                (15, person_a1e,   False, person_a2u,   auth.no),
                (16, person_a2m,   False, person_a2u,   auth.view_only),
                (17, person_a2e,   False, person_a2u,   auth.yes),
                (18, person_admin, False, person_a2u,   auth.no),
                (19, person_admin, True,  person_a2u,   auth.yes),
                (20, person_a_rc,  False, person_a2u,   auth.no),
                (21, person_b_rc,  False, person_a2u,   auth.no),
                # Registered reviewer: no special access by anyone.
                (22, person_a_rc,  False, person_a1re,  auth.no),
                (23, person_b_rc,  False, person_a1re,  auth.no),
                (24, person_a1e,   False, person_a1re,  auth.no),
                (25, person_admin, False, person_a1re,  auth.no),
                (26, person_admin, True,  person_a1re,  auth.yes),
                # Unregistered reviewer: editable by review coordinators.
                (27, person_a_rc,  False, person_a1reu, auth.yes),
                (28, person_b_rc,  False, person_a1reu, auth.no),
                (29, person_a_rc,  False, person_b1reu, auth.no),
                (30, person_b_rc,  False, person_b1reu, auth.yes),
                # Reviewers: no special access to proposal members / reviewers.
                (31, person_a1re,  False, person_a1reu, auth.no),
                (32, person_a1re,  False, person_a1e,   auth.no),
                (33, person_a1re,  False, person_a2e,   auth.no),
                (34, person_a1re,  False, person_a2p,   auth.view_only),
                ]:
            self._test_auth_person(*test_case)

        # Test authorization for institution profiles.
        for test_case in [
                # Allow full access to own institution.
                (1,  person_a1e,   False, institution_1, auth.yes),
                (2,  person_a1e,   False, institution_2, auth.view_only),
                (3,  person_a2e,   False, institution_1, auth.view_only),
                (4,  person_a2e,   False, institution_2, auth.yes),
                # Admin has full access but only when is_admin is set.
                (5,  person_admin, False, institution_1, auth.view_only),
                (6,  person_admin, False, institution_2, auth.view_only),
                (7,  person_admin, True,  institution_1, auth.yes),
                (8,  person_admin, True,  institution_2, auth.yes),
                # Proposal editor has full access to a co-member's institution
                # if it has no registered members (only Institution 3).
                (9,  person_a1e,   False, institution_2, auth.view_only),
                (10, person_a1e,   False, institution_3, auth.view_only),
                (11, person_a2e,   False, institution_3, auth.view_only),
                (12, person_b1e,   False, institution_3, auth.yes),
                (13, person_b2e,   False, institution_3, auth.yes),
                ]:
            self._test_auth_institution(*test_case)

        # Test authorization for private MOCs.
        for test_case in [
                # No general access.
                (1,  person_a1e,   False, facility_id,    False),
                (2,  person_a1e,   False, facility_id,    False),
                (3,  person_a1e,   False, facility_other, False),
                (4,  person_a1e,   False, facility_other, False),
                # Admin has access but only when is_admin is set.
                (5,  person_admin, False, facility_id,    False),
                (6,  person_admin, False, facility_other, False),
                (7,  person_admin, True,  facility_id,    True),
                (8,  person_admin, True,  facility_other, True),
                # Tech. assessors have access to the corresponding facility.
                (9,  person_a1rt,  False, facility_id,    True),
                (10, person_a1rt,  False, facility_other, False),
                ]:
            self._test_auth_private_moc(*test_case)

        # Test authorization for proposals and feedback.
        # Checks authorization in each state via codes -- see _expect_code().
        for test_case in [
                # Member access to own proposals.
                (1,  person_a1e,   False, proposal_a1, 'eeevvvvv', 'ooooovvo'),
                (2,  person_a2e,   False, proposal_a2, 'eeevvvvv', 'ooooovvo'),
                (3,  person_a2m,   False, proposal_a2, 'vvvvvvvv', 'ooooovvo'),
                (4,  person_a2u,   False, proposal_a2, 'vvvvvvvv', 'ooooovvo'),
                (5,  person_a2u,   False, proposal_a2, 'vvvvvvvv', 'ooooovvo'),
                # No member access to other proposals.
                (10, person_a1e,   False, proposal_a2, 'oooooooo', 'oooooooo'),
                (11, person_a1u,   False, proposal_a2, 'oooooooo', 'oooooooo'),
                (12, person_a2e,   False, proposal_a1, 'oooooooo', 'oooooooo'),
                (13, person_a2m,   False, proposal_a1, 'oooooooo', 'oooooooo'),
                (14, person_a2u,   False, proposal_a1, 'oooooooo', 'oooooooo'),
                (15, person_a2p,   False, proposal_a1, 'oooooooo', 'oooooooo'),
                # Admin has access but only when is_admin is set.
                (20, person_admin, False, proposal_a1, 'oooooooo', 'oooooooo'),
                (21, person_admin, False, proposal_a2, 'oooooooo', 'oooooooo'),
                (22, person_admin, True,  proposal_a1, 'vvvvvvvv', 'ooooovvo'),
                (23, person_admin, True,  proposal_a2, 'vvvvvvvv', 'ooooovvo'),
                # Review coordinators can see all proposals.
                (30, person_a_rc,  False, proposal_a1, 'oovvvvvo', 'oooooooo'),
                (31, person_a_rc,  False, proposal_a2, 'oovvvvvo', 'oooooooo'),
                (32, person_a_rc,  False, proposal_b1, 'oooooooo', 'oooooooo'),
                (33, person_a_rc,  False, proposal_b2, 'oooooooo', 'oooooooo'),
                (34, person_b_rc,  False, proposal_a1, 'oooooooo', 'oooooooo'),
                (35, person_b_rc,  False, proposal_a2, 'oooooooo', 'oooooooo'),
                (36, person_b_rc,  False, proposal_b1, 'oovvvvvo', 'oooooooo'),
                (37, person_b_rc,  False, proposal_b2, 'oovvvvvo', 'oooooooo'),
                # Committee members can see all proposals.
                (40, person_a1rc1, False, proposal_a1, 'oovvvvvo', 'oooooooo'),
                (41, person_a1rc1, False, proposal_a2, 'oovvvvvo', 'oooooooo'),
                (42, person_a1rc1, False, proposal_b1, 'oooooooo', 'oooooooo'),
                (43, person_a1rc1, False, proposal_b2, 'oooooooo', 'oooooooo'),
                (44, person_a1rc2, False, proposal_a1, 'oovvvvvo', 'oooooooo'),
                (45, person_a1rc2, False, proposal_a2, 'oovvvvvo', 'oooooooo'),
                (46, person_a1rc2, False, proposal_b1, 'oooooooo', 'oooooooo'),
                (47, person_a1rc2, False, proposal_b2, 'oooooooo', 'oooooooo'),
                # Technical reviewers can only see their assigned proposals.
                (50, person_a1rt,  False, proposal_a1, 'ooovvooo', 'oooooooo'),
                (51, person_a1rt,  False, proposal_a2, 'oooooooo', 'oooooooo'),
                (52, person_a1rt,  False, proposal_b1, 'oooooooo', 'oooooooo'),
                (53, person_a1rt,  False, proposal_b2, 'oooooooo', 'oooooooo'),
                # External reviewers can only see their assigned proposals.
                (60, person_a1re,  False, proposal_a1, 'ooovoooo', 'oooooooo'),
                (61, person_a1re,  False, proposal_a2, 'oooooooo', 'oooooooo'),
                (62, person_a1re,  False, proposal_b1, 'oooooooo', 'oooooooo'),
                (63, person_a1re,  False, proposal_b2, 'oooooooo', 'oooooooo'),
                (64, person_a1reu, False, proposal_a1, 'ooovoooo', 'oooooooo'),
                (65, person_a1reu, False, proposal_a2, 'oooooooo', 'oooooooo'),
                (66, person_b1reu, False, proposal_b1, 'ooovoooo', 'oooooooo'),
                (67, person_b1reu, False, proposal_b2, 'oooooooo', 'oooooooo'),
                ]:
            self._test_auth_proposal(role_class, *test_case)

    def _test_auth_call_review(self, case_number, person_id, is_admin,
                               call_id, expect):
        call = self.db.get_call(None, call_id)
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_call_review(self.db, call),
                expect, 'auth call review case {}'.format(case_number))

    def _test_auth_person(self, case_number, person_id, is_admin,
                          for_person_id, expect):
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_person(self.db, self.db.get_person(for_person_id)),
                expect, 'auth person case {}'.format(case_number))

    def _test_auth_institution(self, case_number, person_id, is_admin,
                               institution_id, expect):
        institution = self.db.get_institution(institution_id)
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_institution(self.db, institution),
                expect, 'auth institution case {}'.format(case_number))

    def _test_auth_private_moc(self, case_number, person_id, is_admin,
                               facility_id, expect):
        with self._as_person(person_id, is_admin):
            can = auth.for_private_moc(self.db, facility_id)
        if expect:
            self.assertTrue(can, 'auth private moc {}'.format(case_number))
        else:
            self.assertFalse(can, 'auth private moc {}'.format(case_number))

    def _test_auth_proposal(self, role_class, case_number, person_id, is_admin,
                            proposal_id, expect_codes, expect_codes_fb):
        self.assertEqual(len(expect_codes), len(proposal_states),
                         'codes for proposal case {}'.format(case_number))
        self.assertEqual(len(expect_codes_fb), len(proposal_states),
                         'fb codes for proposal case {}'.format(case_number))

        for (state, expect_code, expect_code_fb) in zip(
                proposal_states, expect_codes, expect_codes_fb):
            expect = self._expect_code('proposal', case_number, expect_code)
            expect_fb = self._expect_code('proposal fb', case_number,
                                          expect_code_fb)
            self.db.update_proposal(proposal_id, state=state)
            proposal = self.db.get_proposal(
                None, proposal_id, with_members=True, with_reviewers=True)
            with self._as_person(person_id, is_admin):
                self.assertEqual(
                    auth.for_proposal(role_class, self.db, proposal),
                    expect, 'auth proposal case {} state {}'.format(
                        case_number, ProposalState.get_name(state)))
                self.assertEqual(
                    auth.for_proposal_feedback(role_class, self.db, proposal),
                    expect_fb, 'auth proposal fb case {} state {}'.format(
                        case_number, ProposalState.get_name(state)))

    def _expect_code(self, case_type, case_number, code):
        if code == 'e':
            return auth.yes
        elif code == 'v':
            return auth.view_only
        elif code == 'o':
            return auth.no
        else:
            self.fail('invalid code for {} case {}'.format(
                case_type, case_number))

    @contextmanager
    def _as_person(self, person_id, is_admin):
        person = self.db.get_person(person_id)

        with self.app.test_request_context():
            _update_session_user(person.user_id)
            _update_session_person(person)

            if is_admin:
                session['is_admin'] = True

            yield

            session.clear()
