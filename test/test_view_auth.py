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

from hedwig.type.enum import BaseReviewerRole, FormatType, GroupType
from hedwig.view import auth
from hedwig.view.people import _update_session_user, _update_session_person
from hedwig.web.util import session

from .dummy_app import WebAppTestCase


class WebAppAuthTestCase(WebAppTestCase):
    def test_view_auth(self):
        # Display default assert method failure messages as well as our
        # identifiers.
        self.longMessage = True

        # Use basic reviewer role class.
        role_class = BaseReviewerRole

        # Set up test database entries.
        facility_id = self.db.ensure_facility('test')
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

        user_admin = self.db.add_user('admin', 'pass')
        person_admin = self.db.add_person('Admin', user_id=user_admin)
        self.db.update_person(person_admin, admin=True)

        # Create proposals and member profiles.
        # Naming convention: <queue><proposal><info>
        # Where <info> is: Editor / Member / Unregistered / Public
        user_a1e = self.db.add_user('a1e', 'pass')
        person_a1e = self.db.add_person('Person A 1 E', user_id=user_a1e)

        user_a2e = self.db.add_user('a2e', 'pass')
        person_a2e = self.db.add_person('Person A 2 E', user_id=user_a2e)

        user_a2m = self.db.add_user('a2r', 'pass')
        person_a2m = self.db.add_person('Person A 2 R', user_id=user_a2m)

        person_a2u = self.db.add_person('Person A 2 U', user_id=None)

        user_a2p = self.db.add_user('a2p', 'pass')
        person_a2p = self.db.add_person('Person A 2 P', user_id=user_a2p)
        self.db.update_person(person_a2p, public=True)

        user_b1e = self.db.add_user('b1e', 'pass')
        person_b1e = self.db.add_person('Person B 1 E', user_id=user_b1e)

        user_b2e = self.db.add_user('b2e', 'pass')
        person_b2e = self.db.add_person('Person B 2 E', user_id=user_b2e)

        proposal_a1 = self.db.add_proposal(
            call_a, person_a1e, affiliation_a, 'Test proposal A 1')

        proposal_a2 = self.db.add_proposal(
            call_a, person_a2e, affiliation_a, 'Test proposal A 2')
        self.db.add_member(proposal_a2, person_a2m, affiliation_a)
        self.db.add_member(proposal_a2, person_a2u, affiliation_a)
        self.db.add_member(proposal_a2, person_a2p, affiliation_a)

        proposal_b1 = self.db.add_proposal(
            call_b, person_b1e, affiliation_b, 'Test proposal B 1')

        proposal_b2 = self.db.add_proposal(
            call_b, person_b2e, affiliation_b, 'Test proposal B 2')

        # Create review coordinator profiles.
        user_a_rc = self.db.add_user('arc', 'pass')
        person_a_rc = self.db.add_person('Person A RC', user_id=user_a_rc)
        self.db.add_group_member(queue_a, GroupType.COORD, person_a_rc)

        user_b_rc = self.db.add_user('brc', 'pass')
        person_b_rc = self.db.add_person('Person B RC', user_id=user_b_rc)
        self.db.add_group_member(queue_b, GroupType.COORD, person_b_rc)

        # Create reviews and reviewer profiles.
        # Naming convention: <info> = r<type><options>
        # Where <type> is: External
        # And <options> are: Unregistered
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

    def _test_auth_person(self, case_number, person_id, is_admin,
                          for_person_id, expect):
        with self._as_person(person_id, is_admin):
            self.assertEqual(
                auth.for_person(self.db, self.db.get_person(for_person_id)),
                expect, 'auth person case {}'.format(case_number))

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
