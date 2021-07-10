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

from hedwig.compat import first_value, make_type
from hedwig.type.collection import ResultCollection
from hedwig.type.simple import Person, Proposal, Member, Reviewer
from hedwig.type.util import null_tuple
from hedwig.view.people import PeopleView

from .base_app import WebAppTestCase


class PeopleViewTestCase(WebAppTestCase):
    def test_invitee_target(self):
        view = PeopleView()

        dummy_db = make_type('Dummy', (), {
            'get_proposal': (lambda *_: null_tuple(Proposal)._replace(
                facility_id=first_value(self.facilities).id)),
        })()

        def make_record(n_proposals, n_reviews):
            return null_tuple(Person)._replace(
                proposals=ResultCollection((
                    (x, null_tuple(Member)._replace(proposal_id=x))
                    for x in range(n_proposals))),
                reviews=ResultCollection((
                    (x, null_tuple(Reviewer)._replace(id=x))
                    for x in range(n_reviews))))

        with self.app.test_request_context(path='/invitation'):
            self.assertIsNone(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(0, 0)))

            self.assertEqual(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(1, 0)),
                '/generic/proposal/0')

            self.assertEqual(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(2, 0)),
                '/proposals')

            self.assertEqual(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(0, 1)),
                '/generic/review/0/information')

            self.assertEqual(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(0, 2)),
                '/reviews')

            self.assertIsNone(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(1, 1)))

            self.assertIsNone(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(1, 2)))

            self.assertIsNone(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(2, 1)))

            self.assertIsNone(
                view._determine_invitee_target(
                    dummy_db, self.facilities, make_record(2, 2)))
