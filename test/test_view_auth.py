# Copyright (C) 2016-2020 East Asian Observatory
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

from hedwig.type.enum import BaseCallType, BaseReviewerRole, \
    FormatType, GroupType, \
    ProposalState
from hedwig.type.simple import Person
from hedwig.view import auth
from hedwig.view.people import _update_session_user, _update_session_person
from hedwig.web.util import session, HTTPForbidden, HTTPRedirectWithReferrer

from .base_app import WebAppTestCase


class WebAppAuthTestCase(WebAppTestCase):
    def test_can_be_admin(self):
        # Create test user accounts.
        user = self.db.add_user('user', 'pass')
        person_user = self.db.add_person('user', user_id=user)

        admin = self.db.add_user('admin', 'pass')
        person_admin = self.db.add_person('admin', user_id=admin)
        self.db.update_person(person_admin, admin=True)

        unreg = self.db.add_user('unreg', 'pass')

        # Basic tests with no auth cache.
        with self._as_person(person_user):
            self.assertFalse(auth.can_be_admin(self.db))

        with self._as_person(person_admin):
            self.assertTrue(auth.can_be_admin(self.db))

        with self._as_person(None, user_id=unreg):
            with self.assertRaises(HTTPForbidden):
                self.assertFalse(auth.can_be_admin(self.db))

        # Repeat tests with auth cache.
        auth_cache = {}

        with self._as_person(person_user):
            self.assertFalse(auth.can_be_admin(self.db, auth_cache=auth_cache))

        with self._as_person(person_admin):
            self.assertTrue(auth.can_be_admin(self.db, auth_cache=auth_cache))

        with self._as_person(None, user_id=unreg):
            with self.assertRaises(HTTPForbidden):
                self.assertFalse(auth.can_be_admin(self.db,
                                                   auth_cache=auth_cache))

        # Check contents of auth cache.
        self.assertEqual(len(auth_cache), 3)

        value = auth_cache[('_get_user_profile', user)]
        self.assertIsInstance(value, Person)
        self.assertEqual(value.id, person_user)

        value = auth_cache[('_get_user_profile', admin)]
        self.assertIsInstance(value, Person)
        self.assertEqual(value.id, person_admin)

        value = auth_cache[('_get_user_profile', unreg)]
        self.assertIsNone(value)

    def test_view_auth(self):
        # Display default assert method failure messages as well as our
        # identifiers.
        self.longMessage = True

        # Use basic call type and reviewer role classes.
        type_class = BaseCallType
        role_class = BaseReviewerRole

        # Select whether to simulate proposal state updates.
        self.quick_proposal_state = True

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

        call_options = (type_class.STANDARD,
                        datetime(1999, 9, 1), datetime(1999, 9, 30),
                        100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
                        FormatType.PLAIN, False)

        call_a = self.db.add_call(
            type_class, semester_id, queue_a, *call_options)
        call_b = self.db.add_call(
            type_class, semester_id, queue_b, *call_options)

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
        self.db.update_person(person_a1reu, institution_id=institution_3)
        reviewer_a1reu = self.db.add_reviewer(
            role_class, proposal_a1, person_a1reu, role_class.EXTERNAL)

        person_b1reu = self.db.add_person('Person B 1 REU', user_id=None)
        reviewer_b1reu = self.db.add_reviewer(
            role_class, proposal_b1, person_b1reu, role_class.EXTERNAL)

        # -- peer reviewers:
        user_a1rpn = self.db.add_user('a1rpn', 'pass')
        person_a1rpn = self.db.add_person('Person A 1 RPN', user_id=user_a1rpn)
        reviewer_a1rpn = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rpn, role_class.PEER)

        user_a1rpa = self.db.add_user('a1rpa', 'pass')
        person_a1rpa = self.db.add_person('Person A 1 RPA', user_id=user_a1rpa)
        reviewer_a1rpa = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rpa, role_class.PEER)
        self.db.update_reviewer(role_class, reviewer_a1rpa, accepted=True)

        user_a1rpr = self.db.add_user('a1rpr', 'pass')
        person_a1rpr = self.db.add_person('Person A 1 RPR', user_id=user_a1rpr)
        reviewer_a1rpr = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rpr, role_class.PEER)
        self.db.update_reviewer(role_class, reviewer_a1rpr, accepted=False)

        # -- committee reviewers:
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

        user_b2rc1 = self.db.add_user('b2rc1', 'pass')
        person_b2rc1 = self.db.add_person('Person B 2 RC1', user_id=user_b2rc1)
        self.db.add_group_member(queue_b, GroupType.CTTEE, person_b2rc1)
        reviewer_b2rc1 = self.db.add_reviewer(
            role_class, proposal_b2, person_b2rc1, role_class.CTTEE_PRIMARY)

        user_b2rc2 = self.db.add_user('b2rc2', 'pass')
        person_b2rc2 = self.db.add_person('Person B 2 RC2', user_id=user_b2rc2)
        self.db.add_group_member(queue_b, GroupType.CTTEE, person_b2rc2)
        reviewer_b2rc2 = self.db.add_reviewer(
            role_class, proposal_b2, person_b2rc2, role_class.CTTEE_SECONDARY)

        # -- feedback reviewers:
        user_a1rf = self.db.add_user('a1rf', 'pass')
        person_a1rf = self.db.add_person('Person A 1 RF', user_id=user_a1rf)
        self.db.add_group_member(queue_a, GroupType.CTTEE, person_a1rf)
        reviewer_a1rf = self.db.add_reviewer(
            role_class, proposal_a1, person_a1rf, role_class.FEEDBACK)

        user_b1rf = self.db.add_user('b1rf', 'pass')
        person_b1rf = self.db.add_person('Person A 2 RF', user_id=user_b1rf)
        self.db.add_group_member(queue_b, GroupType.CTTEE, person_b1rf)
        reviewer_b1rf = self.db.add_reviewer(
            role_class, proposal_b1, person_b1rf, role_class.FEEDBACK)

        # -- members who are also reviewers / committee / coordinator / admin:
        user_a1x1 = self.db.add_user('a1x1', 'pass')
        person_a1x1 = self.db.add_person('Person A 1 X1', user_id=user_a1x1)
        self.db.add_member(proposal_a1, person_a1x1, affiliation_a)
        reviewer_a1x1 = self.db.add_reviewer(
            role_class, proposal_a1, person_a1x1, role_class.EXTERNAL)

        user_a1x2 = self.db.add_user('a1x2', 'pass')
        person_a1x2 = self.db.add_person('Person A 1 X2', user_id=user_a1x2)
        self.db.add_member(proposal_a1, person_a1x2, affiliation_a)
        self.db.add_group_member(queue_a, GroupType.CTTEE, person_a1x2)

        user_a1x3 = self.db.add_user('a1x3', 'pass')
        person_a1x3 = self.db.add_person('Person A 1 X3', user_id=user_a1x3)
        self.db.add_member(proposal_a1, person_a1x3, affiliation_a)
        self.db.add_group_member(queue_a, GroupType.COORD, person_a1x3)

        user_a1x4 = self.db.add_user('a1x4', 'pass')
        person_a1x4 = self.db.add_person('Person A 1 X4', user_id=user_a1x4)
        self.db.add_member(proposal_a1, person_a1x4, affiliation_a)
        self.db.update_person(person_a1x4, admin=True)

        user_a2x1 = self.db.add_user('a2x1', 'pass')
        person_a2x1 = self.db.add_person('Person A 2 X1', user_id=user_a2x1)
        self.db.add_member(proposal_a2, person_a2x1, affiliation_a)
        reviewer_a2x1 = self.db.add_reviewer(
            role_class, proposal_a2, person_a2x1, role_class.CTTEE_SECONDARY)

        # Create additional profiles.
        user_a_v = self.db.add_user('av', 'pass')
        person_a_v = self.db.add_person('Person V', user_id=user_a_v)
        self.db.add_group_member(queue_a, GroupType.VIEWER, person_a_v)

        all_proposals = [proposal_a1, proposal_a2, proposal_b1, proposal_b2]

        # Create auth cache dictionary.  The database should not be updated
        # in ways which would affect the information which the auth module
        # might memoize beyond this point without clearing this.
        auth_cache = {}

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
            self._test_auth_call_review(auth_cache, *test_case)

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
                # Unregistered reviewer: not editable by review coordinators
                # until proposal in review state.
                (27, person_a_rc,  False, person_a1reu, auth.no),
                (28, person_b_rc,  False, person_a1reu, auth.no),
                (29, person_a_rc,  False, person_b1reu, auth.no),
                (30, person_b_rc,  False, person_b1reu, auth.no),
                # Reviewers: no special access to proposal members / reviewers.
                (31, person_a1re,  False, person_a1reu, auth.no),
                (32, person_a1re,  False, person_a1e,   auth.no),
                (33, person_a1re,  False, person_a2e,   auth.no),
                (34, person_a1re,  False, person_a2p,   auth.view_only),
                ]:
            self._test_auth_person(auth_cache, *test_case)

        self._set_state(all_proposals, ProposalState.REVIEW)
        if auth_cache is not None:
            auth_cache.clear()

        for test_case in [
                # Unregistered co-member: no special access when not editable.
                (91, person_a2m,   False, person_a2u,   auth.no),
                (92, person_a2e,   False, person_a2u,   auth.no),
                # Unregistered reviewer: editable by review coordinators.
                (93, person_a_rc,  False, person_a1reu, auth.yes),
                (94, person_b_rc,  False, person_a1reu, auth.no),
                (95, person_a_rc,  False, person_b1reu, auth.no),
                (96, person_b_rc,  False, person_b1reu, auth.yes),
                ]:
            self._test_auth_person(auth_cache, *test_case)

        self._set_state(all_proposals, ProposalState.PREPARATION)
        if auth_cache is not None:
            auth_cache.clear()

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
                # Review coordinators: no special access when not in review
                # state.
                (14, person_a_rc,  False, institution_1, auth.view_only),
                (15, person_a_rc,  False, institution_2, auth.view_only),
                (16, person_a_rc,  False, institution_3, auth.view_only),
                (17, person_b_rc,  False, institution_3, auth.view_only),
                ]:
            self._test_auth_institution(auth_cache, *test_case)

        self._set_state(all_proposals, ProposalState.REVIEW)
        if auth_cache is not None:
            auth_cache.clear()

        for test_case in [
                # Proposal editor co-member has no special access when
                # proposal not editable.
                (91, person_b1e,   False, institution_3, auth.view_only),
                # Review coordinators: has special access when in review state.
                (92, person_a_rc,  False, institution_1, auth.view_only),
                (93, person_a_rc,  False, institution_2, auth.view_only),
                (94, person_a_rc,  False, institution_3, auth.yes),
                (95, person_b_rc,  False, institution_3, auth.view_only),
                ]:
            self._test_auth_institution(auth_cache, *test_case)

        # Test authorization for private MOCs.
        for test_case in [
                # No general access.
                (1,  person_a1e,   False, facility_id,    auth.no),
                (2,  person_a1e,   False, facility_id,    auth.no),
                (3,  person_a1e,   False, facility_other, auth.no),
                (4,  person_a1e,   False, facility_other, auth.no),
                # Admin has access but only when is_admin is set.
                (5,  person_admin, False, facility_id,    auth.no),
                (6,  person_admin, False, facility_other, auth.no),
                (7,  person_admin, True,  facility_id,    auth.view_only),
                (8,  person_admin, True,  facility_other, auth.view_only),
                # Tech. assessors have access to the corresponding facility.
                (9,  person_a1rt,  False, facility_id,    auth.view_only),
                (10, person_a1rt,  False, facility_other, auth.no),
                ]:
            self._test_auth_private_moc(auth_cache, *test_case)

        # Test authorization for proposals and feedback.
        # Checks authorization in each state via codes -- see _expect_code().
        for test_case in [
                # Member access to own proposals.
                (1,  person_a1e,   False, proposal_a1, 'eeevvvvv', 'ooooovvo', 'oooooooo'),
                (2,  person_a2e,   False, proposal_a2, 'eeevvvvv', 'ooooovvo', 'oooooooo'),
                (3,  person_a2m,   False, proposal_a2, 'vvvvvvvv', 'ooooovvo', 'oooooooo'),
                (4,  person_a2u,   False, proposal_a2, 'vvvvvvvv', 'ooooovvo', 'oooooooo'),
                (5,  person_a2u,   False, proposal_a2, 'vvvvvvvv', 'ooooovvo', 'oooooooo'),
                # No member access to other proposals.
                (10, person_a1e,   False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (11, person_a1u,   False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (12, person_a2e,   False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (13, person_a2m,   False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (14, person_a2u,   False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (15, person_a2p,   False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                # Admin has access but only when is_admin is set.
                (20, person_admin, False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (21, person_admin, False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (22, person_admin, True,  proposal_a1, 'vvvvvvvv', 'ooooovvo', 'oooowooo'),
                (23, person_admin, True,  proposal_a2, 'vvvvvvvv', 'ooooovvo', 'oooowooo'),
                # Review coordinators can see all proposals.
                (30, person_a_rc,  False, proposal_a1, 'oovvvvvo', 'oooooooo', 'oooowooo'),
                (31, person_a_rc,  False, proposal_a2, 'oovvvvvo', 'oooooooo', 'oooowooo'),
                (32, person_a_rc,  False, proposal_b1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (33, person_a_rc,  False, proposal_b2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (34, person_b_rc,  False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (35, person_b_rc,  False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (36, person_b_rc,  False, proposal_b1, 'oovvvvvo', 'oooooooo', 'oooowooo'),
                (37, person_b_rc,  False, proposal_b2, 'oovvvvvo', 'oooooooo', 'oooowooo'),
                # Committee members can see all proposals.
                (40, person_a1rc1, False, proposal_a1, 'oovvvvvo', 'oooooooo', 'oooooooo'),
                (41, person_a1rc1, False, proposal_a2, 'oovvvvvo', 'oooooooo', 'oooooooo'),
                (42, person_a1rc1, False, proposal_b1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (43, person_a1rc1, False, proposal_b2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (44, person_a1rc2, False, proposal_a1, 'oovvvvvo', 'oooooooo', 'oooooooo'),
                (45, person_a1rc2, False, proposal_a2, 'oovvvvvo', 'oooooooo', 'oooooooo'),
                (46, person_a1rc2, False, proposal_b1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (47, person_a1rc2, False, proposal_b2, 'oooooooo', 'oooooooo', 'oooooooo'),
                # Technical reviewers can only see their assigned proposals.
                (50, person_a1rt,  False, proposal_a1, 'ooovvooo', 'oooooooo', 'oooooooo'),
                (51, person_a1rt,  False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (52, person_a1rt,  False, proposal_b1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (53, person_a1rt,  False, proposal_b2, 'oooooooo', 'oooooooo', 'oooooooo'),
                # External reviewers can only see their assigned proposals.
                (60, person_a1re,  False, proposal_a1, 'ooovoooo', 'oooooooo', 'oooooooo'),
                (61, person_a1re,  False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (62, person_a1re,  False, proposal_b1, 'oooooooo', 'oooooooo', 'oooooooo'),
                (63, person_a1re,  False, proposal_b2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (64, person_a1reu, False, proposal_a1, 'ooovoooo', 'oooooooo', 'oooooooo'),
                (65, person_a1reu, False, proposal_a2, 'oooooooo', 'oooooooo', 'oooooooo'),
                (66, person_b1reu, False, proposal_b1, 'ooovoooo', 'oooooooo', 'oooooooo'),
                (67, person_b1reu, False, proposal_b2, 'oooooooo', 'oooooooo', 'oooooooo'),
                # Peer reviewers.
                (68, person_a1rpn, False, proposal_a1, 'oooroooo', 'oooooooo', 'oooooooo'),
                (69, person_a1rpa, False, proposal_a1, 'ooovoooo', 'oooooooo', 'oooooooo'),
                (70, person_a1rpr, False, proposal_a1, 'oooooooo', 'oooooooo', 'oooooooo'),
                # Viewers: view access for proposals and feedback in same queue.
                (71, person_a_v,   False, proposal_a1, 'oovvvvvo', 'ooooovvo', 'oooooooo'),
                (72, person_a_v,   False, proposal_b1, 'oooooooo', 'oooooooo', 'oooooooo'),
                ]:
            self._test_auth_proposal(role_class, auth_cache, *test_case)

        # Test authorization for reviews.
        for test_case in [
                # No general access.
                (1,  person_a1rt,  False, reviewer_a1re,  'oooooooo'),
                (2,  person_a1rt,  False, reviewer_a1rc1, 'oooooooo'),
                (3,  person_a1rt,  False, reviewer_a1rc2, 'oooooooo'),
                (4,  person_a1re,  False, reviewer_a1rt,  'oooooooo'),
                (5,  person_a1re,  False, reviewer_a1rc1, 'oooooooo'),
                (6,  person_a1re,  False, reviewer_a1rc2, 'oooooooo'),
                # Ensure no proposal members have access.
                (10, person_a1e,   False, reviewer_a1re,  'oooooooo'),
                (11, person_b1e,   False, reviewer_b1reu, 'oooooooo'),
                (12, person_a1x1,  False, reviewer_a1x1,  'oooooooo'),
                (13, person_a1x2,  False, reviewer_a1re,  'oooooooo'),
                (14, person_a1x3,  False, reviewer_a1re,  'oooooooo'),
                (15, person_a1x4,  True,  reviewer_a1re,  'oooooooo'),
                # Admin has access but only when is_admin is set.
                (20, person_admin, False, reviewer_a1rt,  'oooooooo'),
                (21, person_admin, False, reviewer_a1re,  'oooooooo'),
                (22, person_admin, False, reviewer_a1rc1, 'oooooooo'),
                (23, person_admin, False, reviewer_a1rc2, 'oooooooo'),
                (24, person_admin, False, reviewer_b1reu, 'oooooooo'),
                (25, person_admin, True,  reviewer_a1rt,  'vvvEEVVv'),
                (26, person_admin, True,  reviewer_a1re,  'vvvEVVVv'),
                (27, person_admin, True,  reviewer_a1rc1, 'vvveEVVv'),
                (28, person_admin, True,  reviewer_a1rc2, 'vvveEVVv'),
                (29, person_admin, True,  reviewer_b1reu, 'vvvEVVVv'),
                # Admin-like access for review coordinators.
                (30, person_a_rc,  False, reviewer_a1rt,  'vvvEEVVv'),
                (31, person_a_rc,  False, reviewer_a1re,  'vvvEVVVv'),
                (32, person_a_rc,  False, reviewer_a1rc1, 'vvveEVVv'),
                (33, person_a_rc,  False, reviewer_a1rc2, 'vvveEVVv'),
                (34, person_b_rc,  False, reviewer_a1rt,  'oooooooo'),
                (35, person_b_rc,  False, reviewer_a1re,  'oooooooo'),
                (36, person_b_rc,  False, reviewer_a1rc1, 'oooooooo'),
                (37, person_b_rc,  False, reviewer_a1rc2, 'oooooooo'),
                (38, person_a_rc,  False, reviewer_b1reu, 'oooooooo'),
                (39, person_b_rc,  False, reviewer_b1reu, 'vvvEVVVv'),
                # View access for committee members.
                (40, person_a1rc1, False, reviewer_a1rt,  'vvvVVVVv'),
                (41, person_a1rc1, False, reviewer_a1re,  'vvvVVVVv'),
                (42, person_a1rc1, False, reviewer_a1rc2, 'vvvvVVVv'),
                (43, person_a1rc1, False, reviewer_b1reu, 'oooooooo'),
                (44, person_a1rc2, False, reviewer_a1rt,  'vvvVVVVv'),
                (45, person_a1rc2, False, reviewer_a1re,  'vvvVVVVv'),
                (46, person_a1rc2, False, reviewer_a1rc1, 'vvvvVVVv'),
                (47, person_a1rc2, False, reviewer_b1reu, 'oooooooo'),
                # Allow reviewers access to their own reviews.
                (50, person_a1rt,  False, reviewer_a1rt,  'oooEEooo'),
                (51, person_a1re,  False, reviewer_a1re,  'oooEoooo'),
                (52, person_a1reu, False, reviewer_a1reu, 'oooEoooo'),
                (54, person_b1reu, False, reviewer_b1reu, 'oooEoooo'),
                (55, person_a1rc1, False, reviewer_a1rc1, 'vvvEEVVv'),
                (56, person_a1rc2, False, reviewer_a1rc2, 'vvvEEVVv'),
                (57, person_a1rf,  False, reviewer_a1rf,  'vvvVEVVv'),
                (58, person_b1rf,  False, reviewer_b1rf,  'vvvVEVVv'),
                # Committee member special case access to feedback review.
                (60, person_a1rc1, False, reviewer_a1rf,  'vvvVEVVv'),
                (61, person_a1rc2, False, reviewer_a1rf,  'vvvVEVVv'),
                (62, person_a1rc1, False, reviewer_b1rf,  'oooooooo'),
                (63, person_a1rc2, False, reviewer_b1rf,  'oooooooo'),
                # Peer reviewers.
                (64, person_a1rpn, False, reviewer_a1rpn, 'oooroooo'),
                (65, person_a1rpa, False, reviewer_a1rpa, 'oooEoooo'),
                (66, person_a1rpr, False, reviewer_a1rpr, 'oooooooo'),
                # Special case: proposal member can access feedback.
                (67, person_a1x3,  False, reviewer_a1rf,  'vvvVEVVv'),
                # Viewers: view access for reviews in same queue.
                (68, person_a_v,   False, reviewer_a1rt,  'vvvVVVVv'),
                (69, person_a_v,   False, reviewer_b1reu, 'oooooooo'),
                ]:
            self._test_auth_review(role_class, auth_cache, *test_case)

        # Test authorization to add new reviews.
        for test_case in [
                # Admin can add feedback when is_admin is set.
                (1,  person_admin, False, proposal_a1, {}),
                (2,  person_admin, False, proposal_a2, {}),
                (3,  person_admin, True,  proposal_a1, {}),
                (4,  person_admin, True,  proposal_a2, {
                    ProposalState.FINAL_REVIEW: [role_class.FEEDBACK],
                }),
                # Committee primary/secondary can add feedback.
                (10, person_a1rc1, False, proposal_a1, {}),
                (11, person_a1rc2, False, proposal_a1, {}),
                (12, person_b2rc1, False, proposal_b2, {
                    ProposalState.FINAL_REVIEW: [role_class.FEEDBACK],
                }),
                (13, person_b2rc2, False, proposal_b2, {
                    ProposalState.FINAL_REVIEW: [role_class.FEEDBACK],
                }),
                # Committee members can add other reviews.
                (20, person_a1rc1, False, proposal_a2, {
                    ProposalState.REVIEW: [role_class.CTTEE_OTHER],
                    ProposalState.FINAL_REVIEW: [role_class.CTTEE_OTHER],
                }),
                (21, person_a1rc2, False, proposal_a2, {
                    ProposalState.REVIEW: [role_class.CTTEE_OTHER],
                    ProposalState.FINAL_REVIEW: [role_class.CTTEE_OTHER],
                }),
                # No access to add reviews to own proposals.
                (30, person_a1x2,  False, proposal_a1, {}),
                (31, person_a2x1,  False, proposal_a2, {}),
                # Review coordinators can add feedback.
                (40, person_a_rc,  False, proposal_a2, {
                    ProposalState.FINAL_REVIEW: [role_class.FEEDBACK],
                }),
                (41, person_a_rc,  False, proposal_b2, {}),
                (42, person_b_rc,  False, proposal_a2, {}),
                (43, person_b_rc,  False, proposal_b2, {
                    ProposalState.FINAL_REVIEW: [role_class.FEEDBACK],
                }),
                ]:
            self._test_auth_add_review(
                type_class, role_class, auth_cache, *test_case)

    def _test_auth_call_review(self, auth_cache,
                               case_number, person_id, is_admin,
                               call_id, expect):
        call = self.db.get_call(None, call_id)
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_call_review(self.db, call, auth_cache=auth_cache),
                expect, 'auth call review case {}'.format(case_number))

    def _test_auth_person(self, auth_cache, case_number, person_id, is_admin,
                          for_person_id, expect):
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_person(self.db, self.db.get_person(for_person_id),
                                auth_cache=auth_cache),
                expect, 'auth person case {}'.format(case_number))

    def _test_auth_institution(self, auth_cache,
                               case_number, person_id, is_admin,
                               institution_id, expect):
        institution = self.db.get_institution(institution_id)
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_institution(self.db, institution,
                                     auth_cache=auth_cache),
                expect, 'auth institution case {}'.format(case_number))

    def _test_auth_private_moc(self, auth_cache,
                               case_number, person_id, is_admin,
                               facility_id, expect):
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_private_moc(self.db, facility_id,
                                     auth_cache=auth_cache),
                expect, 'auth private moc {}'.format(case_number))

    def _test_auth_proposal(self, role_class, auth_cache,
                            case_number, person_id, is_admin,
                            proposal_id, expect_codes, expect_codes_fb,
                            expect_codes_dec):
        proposal_states = ProposalState.get_options()
        self.assertEqual(len(expect_codes), len(proposal_states),
                         'codes for proposal case {}'.format(case_number))
        self.assertEqual(len(expect_codes_fb), len(proposal_states),
                         'fb codes for proposal case {}'.format(case_number))
        self.assertEqual(len(expect_codes_dec), len(proposal_states),
                         'dec codes for proposal case {}'.format(case_number))

        if self.quick_proposal_state:
            proposal_orig = self.db.get_proposal(
                None, proposal_id, with_members=True, with_reviewers=True)

        for (state_info, expect_code, expect_code_fb, expect_code_dec) in zip(
                proposal_states.items(), expect_codes,
                expect_codes_fb, expect_codes_dec):
            (state, state_name) = state_info

            ctx_kwargs = {}
            if expect_code == 'r':
                expect = HTTPRedirectWithReferrer
                ctx_kwargs['path'] = '/generic/'

            else:
                expect = self._expect_code('proposal', case_number, expect_code)

            expect_fb = self._expect_code('proposal fb', case_number,
                                          expect_code_fb)
            expect_dec = self._expect_code('proposal dec', case_number,
                                           expect_code_dec)

            if self.quick_proposal_state:
                proposal = proposal_orig._replace(state=state)
            else:
                self.db.update_proposal(proposal_id, state=state)
                proposal = self.db.get_proposal(
                    None, proposal_id, with_members=True, with_reviewers=True)

            with self._as_person(person_id, is_admin, ctx_kwargs=ctx_kwargs):
                if isinstance(expect, type):
                    with self.assertRaises(expect):
                        auth.for_proposal(role_class, self.db, proposal,
                                          auth_cache=auth_cache)
                    self.assertEqual(
                        auth.for_proposal(role_class, self.db, proposal,
                                          auth_cache=auth_cache,
                                          allow_unaccepted_review=False),
                        auth.no,
                        'auth proposal case {} state {} no unaccepted'.format(
                            case_number, state_name))

                    self.assertEqual(
                        auth.for_proposal(role_class, self.db, proposal,
                                          auth_cache=auth_cache,
                                          allow_unaccepted_review=True),
                        auth.view_only,
                        'auth proposal case {} state {} w/ unaccepted'.format(
                            case_number, state_name))

                else:
                    self.assertEqual(
                        auth.for_proposal(role_class, self.db, proposal,
                                          auth_cache=auth_cache),
                        expect, 'auth proposal case {} state {}'.format(
                            case_number, state_name))
                self.assertEqual(
                    auth.for_proposal_feedback(role_class, self.db, proposal,
                                               auth_cache=auth_cache),
                    expect_fb, 'auth proposal fb case {} state {}'.format(
                        case_number, state_name))
                self.assertEqual(
                    auth.for_proposal_decision(self.db, proposal,
                                               auth_cache=auth_cache),
                    expect_dec, 'auth proposal dec case {} state {}'.format(
                        case_number, state_name))

    def _test_auth_review(self, role_class, auth_cache,
                          case_number, person_id, is_admin,
                          reviewer_id, expect_codes):
        proposal_states = ProposalState.get_options()
        self.assertEqual(len(expect_codes), len(proposal_states),
                         'codes for review case {}'.format(case_number))
        reviewer = self.db.search_reviewer(
            reviewer_id=reviewer_id,
            with_review=True).get_single()

        if self.quick_proposal_state:
            proposal_orig = self.db.get_proposal(
                None, reviewer.proposal_id, with_members=True)

        for (state_info, expect_code) in zip(
                proposal_states.items(), expect_codes):
            (state, state_name) = state_info

            ctx_kwargs = {}
            if expect_code == 'r':
                expect = HTTPRedirectWithReferrer
                ctx_kwargs['path'] = '/generic/'

            else:
                expect = self._expect_code('review', case_number, expect_code,
                                           rating=True)

            if self.quick_proposal_state:
                proposal = proposal_orig._replace(state=state)
            else:
                self.db.update_proposal(reviewer.proposal_id, state=state)
                proposal = self.db.get_proposal(
                    None, reviewer.proposal_id, with_members=True)

            with self._as_person(person_id, is_admin, ctx_kwargs=ctx_kwargs):
                if isinstance(expect, type):
                    with self.assertRaises(expect):
                        auth.for_review(role_class, self.db, reviewer, proposal,
                                        auth_cache=auth_cache)

                    self.assertEqual(
                        auth.for_review(role_class, self.db, reviewer, proposal,
                                        auth_cache=auth_cache,
                                        allow_unaccepted=False),
                        auth.AuthorizationWithRating(False, False, False),
                        'auth review case {} state {} no unaccepted'.format(
                            case_number, state_name))

                    self.assertEqual(
                        auth.for_review(role_class, self.db, reviewer, proposal,
                                        auth_cache=auth_cache,
                                        allow_unaccepted=True),
                        auth.AuthorizationWithRating(True, True, True),
                        'auth review case {} state {} with unaccepted'.format(
                            case_number, state_name))

                else:
                    self.assertEqual(
                        auth.for_review(role_class, self.db, reviewer, proposal,
                                        auth_cache=auth_cache),
                        expect, 'auth review case {} state {}'.format(
                            case_number, state_name))

    def _test_auth_add_review(self, type_class, role_class, auth_cache,
                              case_number, person_id, is_admin,
                              proposal_id, expect_by_state):
        if self.quick_proposal_state:
            proposal_orig = self.db.get_proposal(
                None, proposal_id, with_members=True, with_reviewers=True)

        for (state, state_name) in ProposalState.get_options().items():
            expect = set(expect_by_state.get(state, []))

            if self.quick_proposal_state:
                proposal = proposal_orig._replace(state=state)
            else:
                self.db.update_proposal(proposal_id, state=state)
                proposal = self.db.get_proposal(
                    None, proposal_id, with_members=True, with_reviewers=True)

            with self._as_person(person_id, is_admin):
                self.assertEqual(
                    set(auth.can_add_review_roles(
                        type_class, role_class, self.db, proposal,
                        auth_cache=auth_cache)),
                    expect, 'add review case {} state {}'.format(
                        case_number, state_name))

    def _expect_code(self, case_type, case_number, code, rating=False):
        expect = None
        view_rating = False

        if code == 'e':
            expect = auth.yes
        elif code == 'E':
            expect = auth.yes
            view_rating = True
        elif code == 'v':
            expect = auth.view_only
        elif code == 'V':
            expect = auth.view_only
            view_rating = True
        elif code == 'o':
            expect = auth.no
        elif code == 'w':
            expect = auth.edit_only

        if expect is None:
            self.fail('invalid code for {} case {}'.format(
                case_type, case_number))

        if rating:
            expect = auth.AuthorizationWithRating(*expect,
                                                  view_rating=view_rating)

        return expect

    @contextmanager
    def _as_person(
            self, person_id, is_admin=False, user_id=None, ctx_kwargs={}):
        """
        Simulate logging in as the given person.

        Sets session user and person values based on the given `person_id`.

        If `person_id` is `None` then sets just the user value based on the
        `user_id` argument.

        A Flask request context is established using its `test_request_context`
        method.  Arguments for this method can be supplied, for example to set
        the path for this request to "/generic/", to allow routines which
        can only be run in the context of a facility blueprint to be tested.
        """

        if person_id is not None:
            person = self.db.search_person(person_id=person_id).get_single()

        with self.app.test_request_context(**ctx_kwargs):
            if person_id is None:
                _update_session_user(user_id)
            else:
                _update_session_user(person.user_id)
                _update_session_person(person)

            if is_admin:
                session['is_admin'] = True

            yield

            session.clear()

    def _set_state(self, proposal_ids, state):
        """
        Set the state of multiple proposals.
        """

        for proposal_id in proposal_ids:
            self.db.update_proposal(proposal_id, state=state)
