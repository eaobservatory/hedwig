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

from hedwig.error import NoSuchRecord, ParseError

from .base_facility import FacilityTestCase


class UKIRTFacilityTestCase(FacilityTestCase):
    facility_spec = 'UKIRT'

    def test_basic_info(self):
        self._test_basic_info(expect_code='ukirt')

    def test_proposal_code(self):
        types = self.view.get_call_types()

        proposal_1 = self._create_test_proposal('20A', 'P', types.STANDARD)
        proposal_2 = self._create_test_proposal('20A', 'P', types.STANDARD)
        proposal_3 = self._create_test_proposal('20B', 'P', types.STANDARD)
        proposal_4 = self._create_test_proposal('20B', 'L', types.STANDARD)
        proposal_5 = self._create_test_proposal('20A', 'P', types.IMMEDIATE)

        def check_code(proposal_id, proposal_code):
            self.assertEqual(self.view.make_proposal_code(
                self.db, self.db.get_proposal(self.facility_id, proposal_id)),
                proposal_code)

            self.assertEqual(
                self.view.parse_proposal_code(self.db, proposal_code),
                proposal_id)

        check_code(proposal_1, 'U/20A/P001')
        check_code(proposal_2, 'U/20A/P002')
        check_code(proposal_3, 'U/20B/P001')
        check_code(proposal_4, 'U/20B/L001')
        check_code(proposal_5, 'U/SERV/20A/P001')

        with self.assertRaisesRegex(
                ParseError, "^Proposal code did not match expected pattern"):
            self.view.parse_proposal_code(self.db, 'ABCDEF')

        with self.assertRaisesRegex(
                ParseError, "^Did not recognise call type code"):
            self.view.parse_proposal_code(self.db, 'U/XXX/11A/P111')

        with self.assertRaises(NoSuchRecord):
            self.view.parse_proposal_code(self.db, 'U/20A/P999')
