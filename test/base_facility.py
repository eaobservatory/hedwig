# Copyright (C) 2016-2024 East Asian Observatory
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

from hedwig.compat import first_value, string_type
from hedwig.config import get_facilities
from hedwig.type.enum import BaseAffiliationType, FormatType, ProposalType
from hedwig.type.simple import Call

from .dummy_db import DBTestCase


class FacilityTestCase(DBTestCase):
    """
    Base class for test cases for the utility methods of a facility
    view class.
    """

    facility_spec = 'Generic'

    def setUp(self):
        super(FacilityTestCase, self).setUp()

        self.id_cache = {}

        facilities = get_facilities(
            db=self.db, facility_spec=self.facility_spec)
        assert len(facilities) == 1
        facility = first_value(facilities)

        self.facility_id = facility.id
        self.view = facility.view

    def tearDown(self):
        del self.facility_id
        del self.view

        super(FacilityTestCase, self).tearDown()

    def _test_basic_info(self, expect_code):
        """
        A test of the facility's basic informational methods.

        .. note:: this is a private method which subclasses should
            call as a workaround for the problem that if this was a
            "normal" test method, `unittest` would execute it twice
            for each subclass.  This also gives us the opportunity
            to specify what the expected facility is so that can be
            tested.
        """

        # Check the code and make sure it's what we expect, i.e. that we're
        # testing the correct facility.
        code = self.view.get_code()
        self.assertIsInstance(code, string_type)
        self.assertEqual(code, expect_code)

        # Test some basic informational methods.
        self.assertIsInstance(self.view.get_name(), string_type)
        self.assertIsInstance(self.view.get_definite_name(), string_type)
        self.assertIsInstance(self.view.get_calculator_classes(), tuple)
        self.assertIsInstance(self.view.get_moc_order(), int)
        self.assertIsInstance(self.view.get_target_tool_classes(), tuple)

        order_expected = [
            'proposal_abstract',
            'proposal_calculations',
            'proposal_members',
            'proposal_previous',
            'proposal_request',
            'proposal_summary',
            'proposal_targets',
            'science_case',
            'technical_case',
        ]

        # Proposal order should contain all section if type unspecified,
        # and currently contains all sections if standard.
        for proposal_type in (None, ProposalType.STANDARD):
            proposal_order = self.view.get_proposal_order(type_=proposal_type)
            self.assertIsInstance(proposal_order, list)
            self.assertEqual(sorted(proposal_order), order_expected)

        # Ordering for other proposal types should contain a selection of the
        # full list of sections.
        for proposal_type in (ProposalType.CONTINUATION,):
            proposal_order = self.view.get_proposal_order(type_=proposal_type)
            self.assertIsInstance(proposal_order, list)
            for order_entry in proposal_order:
                self.assertIn(order_entry, order_expected)

        # Test custom type methods.
        type_class = self.view.get_call_types()
        self.assertIsInstance(type_class, type)
        self.assertTrue(hasattr(type_class, 'STANDARD'))

        role_class = self.view.get_text_roles()
        self.assertIsInstance(role_class, type)
        self.assertTrue(hasattr(role_class, 'ABSTRACT'))

        role_class = self.view.get_reviewer_roles()
        self.assertIsInstance(role_class, type)
        self.assertTrue(hasattr(role_class, 'FEEDBACK'))

        # Test custom web interface methods.
        self.assertIsInstance(self.view.get_custom_filters(), list)
        self.assertIsInstance(self.view.get_custom_routes(), list)

        # Test defaults methods.
        self.assertIsInstance(
            self.view.get_new_call_default(type_class.STANDARD), Call)

    def _create_test_proposal(
            self, semester_code, queue_code, call_type, pi_affiliation='Test',
            pi_name='Test Person', title='Test Proposal'):
        key = (semester_code,)
        semester_id = self.id_cache.get(key)
        if semester_id is None:
            semester_id = self.id_cache[key] = self.db.add_semester(
                self.facility_id, semester_code, semester_code,
                datetime(2020, 1, 1), datetime(2020, 6, 30))

        key = (queue_code,)
        queue_id = self.id_cache.get(key)
        if queue_id is None:
            queue_id = self.id_cache[key] = self.db.add_queue(
                self.facility_id, queue_code, queue_code)

        key = (semester_code, queue_id, call_type)
        call_id = self.id_cache.get(key)
        if call_id is None:
            call_id = self.id_cache[key] = self.db.add_call(
                self.view.get_call_types(), semester_id, queue_id, call_type,
                datetime(2019, 8, 1), datetime(2019, 9, 1),
                100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
                FormatType.PLAIN, False, False, None, None, False, False)

        key = (queue_code, pi_affiliation)
        affiliation_id = self.id_cache.get(key)
        if affiliation_id is None:
            affiliation_id = self.id_cache[key] = self.db.add_affiliation(
                BaseAffiliationType, queue_id, pi_affiliation)

        key = (pi_name,)
        person_id = self.id_cache.get(key)
        if person_id is None:
            person_id = self.id_cache[key] = self.db.add_person(pi_name)

        return self.db.add_proposal(
            call_id, person_id, affiliation_id, title)
