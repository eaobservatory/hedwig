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

from hedwig.error import NoSuchRecord

from .dummy_facility import FacilityTestCase


class GenericFacilityTestCase(FacilityTestCase):
    def test_basic_info(self):
        self._test_basic_info(expect_code='generic')

    def test_proposal_code(self):
        types = self.view.get_call_types()

        proposal_1 = self._create_test_proposal('20A', 'X', types.STANDARD)
        proposal_2 = self._create_test_proposal('20A', 'X', types.STANDARD)
        proposal_3 = self._create_test_proposal('20B', 'X', types.STANDARD)
        proposal_4 = self._create_test_proposal('20B', 'Y', types.STANDARD)
        proposal_5 = self._create_test_proposal('20A', 'X', types.IMMEDIATE)

        def check_code(proposal_id, proposal_code):
            self.assertEqual(self.view.make_proposal_code(
                self.db, self.db.get_proposal(self.facility_id, proposal_id)),
                proposal_code)

            self.assertEqual(
                self.view.parse_proposal_code(self.db, proposal_code),
                proposal_id)

        check_code(proposal_1, '20A-X-1')
        check_code(proposal_2, '20A-X-2')
        check_code(proposal_3, '20B-X-1')
        check_code(proposal_4, '20B-Y-1')
        check_code(proposal_5, '20A-X-1-I')

        with self.assertRaisesRegexp(NoSuchRecord, "^Insufficient"):
            self.view.parse_proposal_code(self.db, '20A-1')

        with self.assertRaisesRegexp(NoSuchRecord, "^Excess"):
            self.view.parse_proposal_code(self.db, '20A-X-1-W-W')

        with self.assertRaisesRegexp(NoSuchRecord, "^Could not parse"):
            self.view.parse_proposal_code(self.db, '20A-X-Y')

        with self.assertRaisesRegexp(NoSuchRecord, "^Did not recognise"):
            self.view.parse_proposal_code(self.db, '20A-X-1-X')
