# Copyright (C) 2019-2021 East Asian Observatory
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

from hedwig.compat import first_value
from hedwig.facility.example.calculator_example import ExampleCalculator
from hedwig.type.collection import CalculationCollection, \
    PrevProposalCollection, \
    ProposalCategoryCollection, ProposalTextCollection, \
    ResultCollection, TargetCollection
from hedwig.type.enum import BaseTextRole, FigureType, FormatType
from hedwig.type.misc import SectionedList
from hedwig.type.simple import CalculatorInfo, Category, \
    PrevProposal, ProposalCategory, Target
from hedwig.type.util import null_tuple
from hedwig.view.people import _update_session_person
from hedwig.web.util import session

from .base_app import WebAppTestCase


class GenericFacilityWebAppTestCase(WebAppTestCase):
    def test_copy_proposal(self):
        view = self._get_facility_view('generic')

        (call_id, affiliation_id) = self._create_test_call(
            facility_id=view.id_)
        self.assertIsInstance(call_id, int)
        self.assertIsInstance(affiliation_id, int)

        # Create a proposal to copy ...
        user_id_1 = self.db.add_user('user1', 'pass')
        person_id_1 = self.db.add_person('Person 1', user_id=user_id_1)
        proposal_id = self.db.add_proposal(
            call_id, person_id_1, affiliation_id, 'Original')
        self.assertIsInstance(proposal_id, int)

        # ... members.
        user_id_2 = self.db.add_user('user2', 'pass')
        person_id_2 = self.db.add_person('Person 2', user_id=user_id_2)
        member_id_2 = self.db.add_member(
            proposal_id, person_id_2, affiliation_id, False, False, False)

        user_id_3 = self.db.add_user('user3', 'pass')
        person_id_3 = self.db.add_person('Person 3', user_id=user_id_3)
        member_id_3 = self.db.add_member(
            proposal_id, person_id_3, affiliation_id, False, False, False)

        user_id_4 = self.db.add_user('user4', 'pass')
        person_id_4 = self.db.add_person('Person 4', user_id=user_id_4)
        member_id_4 = self.db.add_member(
            proposal_id, person_id_4, affiliation_id, False, False, True)

        user_id_5 = self.db.add_user('user5', 'pass')
        person_id_5 = self.db.add_person('Person 5', user_id=user_id_5)
        member_id_5 = self.db.add_member(
            proposal_id, person_id_5, affiliation_id, False, True, False)

        user_id_6 = self.db.add_user('user6', 'pass')
        person_id_6 = self.db.add_person('Person 6', user_id=user_id_6)
        member_id_6 = self.db.add_member(
            proposal_id, person_id_6, affiliation_id, False, True, True)

        members = self.db.search_member(proposal_id=proposal_id)
        members[member_id_3] = members[member_id_3]._replace(student=True)
        self.db.sync_proposal_member_student(proposal_id, members)

        # ... targets.
        self.db.sync_proposal_target(proposal_id, TargetCollection([
            (1, Target(1, proposal_id, 1, 'T1', None, None, None, None, None, None)),
            (2, Target(2, proposal_id, 2, 'T2', None, None, None, None, None, None)),
            (3, Target(3, proposal_id, 3, 'T3', None, None, None, None, None, None)),
        ]))

        # ... calculations.
        calculator_id = self.db.ensure_calculator(
            view.id_, ExampleCalculator.get_code())
        calculator = ExampleCalculator(view.id_, calculator_id)
        view.calculators[calculator_id] = CalculatorInfo(
            calculator_id, calculator.get_code(), calculator.get_name(),
            calculator, calculator.modes, {})

        calculation_id = self.db.add_calculation(
            proposal_id, calculator_id,
            calculator.ADDITION, calculator.version,
            {'a': 3, 'b': 4}, {'sum': 1234},
            calculator.get_calc_version(), 'an example')

        # ... previous proposals.
        self.db.sync_proposal_prev_proposal(
            proposal_id, PrevProposalCollection([
                (1, PrevProposal(1, proposal_id, None, 'OLDPROP', False, [])),
            ]))

        # ... PDF file.
        (pdf_link_id, pdf_id) = self.db.set_proposal_pdf(
            BaseTextRole, proposal_id, BaseTextRole.TECHNICAL_CASE,
            b'dummy PDF', 1, 'science.pdf', person_id_1)
        self.assertIsInstance(pdf_link_id, int)
        self.assertIsInstance(pdf_id, int)

        # ... text.
        (text_link_id, text_id) = self.db.set_proposal_text(
            BaseTextRole, proposal_id, BaseTextRole.SCIENCE_CASE,
            'technical text', FormatType.PLAIN, 2, person_id_1)

        (abst_text_link_id, abst_text_id) = self.db.set_proposal_text(
            BaseTextRole, proposal_id, BaseTextRole.ABSTRACT,
            'abstract text', FormatType.PLAIN, 2, person_id_1)

        # ... figures.
        (fig_link_id_1, fig_id_1) = self.db.add_proposal_figure(
            BaseTextRole, proposal_id, BaseTextRole.SCIENCE_CASE,
            FigureType.PNG, b'dummy1', 'Fig 1', 'fig1.png', person_id_1)
        (fig_link_id_2, fig_id_2) = self.db.add_proposal_figure(
            BaseTextRole, proposal_id, BaseTextRole.SCIENCE_CASE,
            FigureType.PNG, b'dummy2', 'Fig 2', 'fig2.png', person_id_1)

        # ... categories.
        n = self.db.sync_facility_category(view.id_, ResultCollection((
            (0, Category(None, view.id_, 'Cat 1', False)),
            (1, Category(None, view.id_, 'Cat 2', False)),
        )))
        self.assertEqual(n, (2, 0, 0))
        category = first_value(self.db.search_category(
            facility_id=view.id_))
        self.db.sync_proposal_category(
            proposal_id, ProposalCategoryCollection((
                (1, ProposalCategory(1, proposal_id, category.id, None)),
            )))

        # Copy the proposal.
        proposal = self.db.get_proposal(None, proposal_id, with_members=True)

        person_2 = self.db.search_person(person_id=person_id_2).get_single()
        copy_id = self.db.add_proposal(
            call_id, person_2.id, affiliation_id, 'Copy')
        self.assertIsInstance(copy_id, int)
        self.assertNotEqual(copy_id, proposal_id)

        copy = self.db.get_proposal(
            None, copy_id, with_members=True)
        self.assertEqual(copy.id, copy_id)

        with self.app.test_request_context(path='/generic/'):
            _update_session_person(person_2)
            atn = view._copy_proposal(
                self.db, proposal, copy, copy_members=True)
            session.clear()

        self.assertIsInstance(atn, dict)
        self.assertEqual(atn['copier_person_id'], person_id_2)
        self.assertEqual(atn['old_proposal_id'], proposal_id)
        self.assertIsInstance(atn['notes'], SectionedList)

        for entry in atn['notes']:
            self.assertNotEqual(entry['item'], 'Error')

        # Remove some entries from the old proposal to ensure values
        # come from the copy.
        self.db.sync_proposal_target(
            proposal_id, TargetCollection())
        self.db.sync_proposal_calculation(
            proposal_id, CalculationCollection())
        self.db.sync_proposal_prev_proposal(
            proposal_id, PrevProposalCollection())
        self.db.delete_proposal_pdf(
            proposal_id, BaseTextRole.TECHNICAL_CASE)
        self.db.delete_proposal_text(
            proposal_id, BaseTextRole.SCIENCE_CASE)
        self.db.delete_proposal_figure(
            proposal_id, BaseTextRole.SCIENCE_CASE, None, _allow_any=True)

        # Compare the copy to the original ...
        copy = self.db.get_proposal(None, copy_id, with_members=True)
        self.assertEqual(copy.id, copy_id)

        # ... members.
        self.assertEqual(len(copy.members), 6)
        for (member, expect) in zip(copy.members.values(), [
                ('Person 2', True, True, False, False),
                ('Person 1', False, True, False, False),
                ('Person 3', False, False, False, True),
                ('Person 4', False, False, True, False),
                ('Person 5', False, True, False, False),
                ('Person 6', False, True, True, False)]):
            (name, pi, editor, observer, student) = expect
            self.assertEqual(member.person_name, name)
            self.assertEqual(member.pi, pi)
            self.assertEqual(member.editor, editor)
            self.assertEqual(member.observer, observer)
            self.assertEqual(member.student, student)

        # ... targets.
        records = self.db.search_target(proposal_id=copy_id)
        self.assertEqual(len(records), 3)
        for (record, expect) in zip(records.values(), [
                ('T1', 1),
                ('T2', 2),
                ('T3', 3)]):
            (name, sort_order) = expect
            self.assertEqual(record.name, name)
            self.assertEqual(record.sort_order, sort_order)

        # ... calculations.
        records = self.db.search_calculation(proposal_id=copy_id)
        self.assertEqual(len(records), 1)
        for (record, expect) in zip(records.values(), [
                ('an example', {'a': 3, 'b': 4}, {'sum': 7000})]):
            (title, input_, output) = expect
            self.assertEqual(record.title, title)
            self.assertEqual(record.input, input_)
            self.assertEqual(record.output, output)

        # ... previous proposals.
        records = self.db.search_prev_proposal(proposal_id=copy_id)
        self.assertEqual(len(records), 1)
        for (record, expect) in zip(records.values(), [
                ('OLDPROP', False)]):
            (code, continuation) = expect
            self.assertEqual(record.proposal_code, code)
            self.assertEqual(record.continuation, continuation)

        # ... PDF file.
        records = self.db.search_proposal_pdf(proposal_id=copy_id)
        self.assertEqual(len(records), 1)
        record = first_value(records)
        self.assertNotEqual(record.id, pdf_link_id)
        self.assertEqual(record.pdf_id, pdf_id)
        self.assertEqual(record.role, BaseTextRole.TECHNICAL_CASE)
        self.assertEqual(record.pages, 1)
        self.assertEqual(record.filename, 'science.pdf')

        # ... text.
        records = self.db.search_proposal_text(proposal_id=copy_id)
        self.assertEqual(len(records), 2)
        record = records.get_role(BaseTextRole.SCIENCE_CASE)
        self.assertNotEqual(record.id, text_link_id)
        self.assertEqual(record.text_id, text_id)
        self.assertEqual(record.role, BaseTextRole.SCIENCE_CASE)
        self.assertEqual(record.words, 2)
        record = records.get_role(BaseTextRole.ABSTRACT)
        self.assertNotEqual(record.id, abst_text_link_id)
        self.assertEqual(record.text_id, abst_text_id)
        self.assertEqual(record.role, BaseTextRole.ABSTRACT)
        self.assertEqual(record.words, 2)

        # ... figures.
        records = self.db.search_proposal_figure(
            proposal_id=copy_id, with_caption=True)
        self.assertEqual(len(records), 2)
        for (record, expect) in zip(records.values(), [
                ('Fig 1', 'fig1.png', fig_link_id_1, fig_id_1),
                ('Fig 2', 'fig2.png', fig_link_id_2, fig_id_2)]):
            (caption, filename, link_id, fig_id) = expect
            self.assertNotEqual(record.id, link_id)
            self.assertEqual(record.fig_id, fig_id)
            self.assertEqual(record.caption, caption)
            self.assertEqual(record.filename, filename)

        # ... categories.
        proposal_categories = self.db.search_proposal_category(
            proposal_id=copy_id)
        self.assertEqual(len(proposal_categories), 1)
        self.assertEqual(
            first_value(proposal_categories).category_id, category.id)
