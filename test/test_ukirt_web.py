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

from hedwig.facility.ukirt.type import \
    UKIRTBrightness, UKIRTInstrument, \
    UKIRTRequest, UKIRTRequestCollection
from hedwig.type.misc import SectionedList
from hedwig.view.people import _update_session_person
from hedwig.web.util import session

from .base_app import WebAppTestCase


class UKIRTWebAppTestCase(WebAppTestCase):
    facility_spec = 'UKIRT'

    def test_copy_proposal(self):
        view = self._get_facility_view('ukirt')

        (call_id, affiliation_id) = self._create_test_call()
        self.assertIsInstance(call_id, int)
        self.assertIsInstance(affiliation_id, int)

        # Create a proposal to copy ...
        user_id_1 = self.db.add_user('user1', 'pass')
        person_id_1 = self.db.add_person('Person 1', user_id=user_id_1)
        proposal_id = self.db.add_proposal(
            call_id, person_id_1, affiliation_id, 'Original')
        self.assertIsInstance(proposal_id, int)

        # ... request.
        self.db.sync_ukirt_proposal_request(
            proposal_id, UKIRTRequestCollection([
                (1, UKIRTRequest(None, None, UKIRTInstrument.WFCAM,
                                 UKIRTBrightness.BRIGHT, 8.0)),
                (2, UKIRTRequest(None, None, UKIRTInstrument.UFTI,
                                 UKIRTBrightness.DARK, 55.0)),
            ]))

        # Copy the proposal.
        proposal = self.db.get_proposal(None, proposal_id, with_members=True)

        person = self.db.search_person(person_id=person_id_1).get_single()
        copy_id = self.db.add_proposal(
            call_id, person.id, affiliation_id, 'Copy')
        self.assertIsInstance(copy_id, int)
        self.assertNotEqual(copy_id, proposal_id)

        copy = self.db.get_proposal(
            None, copy_id, with_members=True)
        self.assertEqual(copy.id, copy_id)

        with self.app.test_request_context(path='/ukirt/'):
            _update_session_person(person)
            atn = view._copy_proposal(
                self.db, proposal, copy, copy_members=True)
            session.clear()

        self.assertIsInstance(atn, dict)
        self.assertEqual(atn['copier_person_id'], person_id_1)
        self.assertEqual(atn['old_proposal_id'], proposal_id)
        self.assertIsInstance(atn['notes'], SectionedList)

        for entry in atn['notes']:
            self.assertNotEqual(entry['item'], 'Error')

        # Remove some entries from the old proposal to ensure values
        # come from the copy.
        self.db.sync_ukirt_proposal_request(
            proposal_id, UKIRTRequestCollection())

        # Compare the copy to the original ...
        copy = self.db.get_proposal(None, copy_id, with_members=True)
        self.assertEqual(copy.id, copy_id)

        # ... members.
        self.assertEqual(len(copy.members), 1)
        for (member, expect) in zip(copy.members.values(), [
                ('Person 1', True, True, False, False)]):
            (name, pi, editor, observer, student) = expect
            self.assertEqual(member.person_name, name)
            self.assertEqual(member.pi, pi)
            self.assertEqual(member.editor, editor)
            self.assertEqual(member.observer, observer)
            self.assertEqual(member.student, student)

        # ... request.
        records = self.db.search_ukirt_request(copy_id)
        self.assertEqual(len(records), 2)
        for (record, expect) in zip(records.values(), [
                (UKIRTInstrument.WFCAM, UKIRTBrightness.BRIGHT, 8.0),
                (UKIRTInstrument.UFTI, UKIRTBrightness.DARK, 55.0)]):
            (instrument, brightness, time) = expect
            self.assertEqual(record.instrument, instrument)
            self.assertEqual(record.brightness, brightness)
            self.assertEqual(record.time, time)
