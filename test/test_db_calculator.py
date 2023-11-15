# Copyright (C) 2015-2023 East Asian Observatory
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

from contextlib import closing
from datetime import datetime

from pymoc import MOC

from hedwig.error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord
from hedwig.file.moc import read_moc, write_moc
from hedwig.type.collection import CalculationCollection, ResultCollection
from hedwig.type.enum import AttachmentState, FormatType
from hedwig.type.simple import Calculation, MOCInfo, ReviewCalculation

from .dummy_db import DBTestCase


class DBCalculatorTest(DBTestCase):
    def test_calculator(self):
        with self.assertRaises(DatabaseIntegrityError):
            self.db.ensure_calculator(1999999, 'testcalc')

        facility_id = self.db.ensure_facility('my_tel')

        with self.assertRaises(ConsistencyError):
            self.db.ensure_calculator(facility_id, '')

        calc_id = self.db.ensure_calculator(facility_id, 'testcalc')
        self.assertIsInstance(calc_id, int)

        calc_id_rep = self.db.ensure_calculator(facility_id, 'testcalc')
        self.assertIsInstance(calc_id_rep, int)
        self.assertEqual(calc_id_rep, calc_id)

        calc_id_diff = self.db.ensure_calculator(facility_id, 'testcalc2')
        self.assertIsInstance(calc_id_diff, int)
        self.assertNotEqual(calc_id_diff, calc_id)

    def test_calculation(self):
        facility_id = self.db.ensure_facility('my_tel')
        proposal_id = self._create_test_proposal(facility_id=facility_id)
        calculator_id = self.db.ensure_calculator(facility_id, 'testcalc')

        calculation_id = self.db.add_calculation(
            proposal_id, calculator_id, 1, 10, {'a': 10, 'b': 20}, {'c': 30},
            '0.0.0', 'test calculation')

        self.assertIsInstance(calculation_id, int)

        calc = self.db.get_calculation(calculation_id)
        self.assertIsInstance(calc, Calculation)
        self.assertEqual(calc.id, calculation_id)
        self.assertEqual(calc.proposal_id, proposal_id)
        self.assertEqual(calc.calculator_id, calculator_id)
        self.assertEqual(calc.mode, 1)
        self.assertEqual(calc.version, 10)
        self.assertEqual(calc.input, {'a': 10, 'b': 20})
        self.assertEqual(calc.output, {'c': 30})
        self.assertEqual(calc.calc_version, '0.0.0')
        self.assertEqual(calc.title, 'test calculation')
        self.assertIsInstance(calc.date_run, datetime)

        self.db.update_calculation(
            calculation_id=calculation_id,
            mode=2, version=20, input_={'a': 11, 'b': 22}, output={'c': 33},
            calc_version='0.0.1', title='altered calculation')

        result = self.db.search_calculation()
        self.assertIsInstance(result, CalculationCollection)
        self.assertEqual(len(result), 1)
        self.assertIn(calculation_id, result)
        calc = result[calculation_id]
        self.assertIsInstance(calc, Calculation)
        self.assertEqual(calc.mode, 2)
        self.assertEqual(calc.version, 20)
        self.assertEqual(calc.input, {'a': 11, 'b': 22})
        self.assertEqual(calc.output, {'c': 33})
        self.assertEqual(calc.calc_version, '0.0.1')
        self.assertEqual(calc.title, 'altered calculation')

    def test_review_calculation(self):
        facility_id = self.db.ensure_facility('my_tel')
        proposal_id = self._create_test_proposal(facility_id=facility_id)
        calculator_id = self.db.ensure_calculator(facility_id, 'testcalc')
        reviewer_id = self._create_test_reviewer(proposal_id)

        result = self.db.search_review_calculation(reviewer_id=reviewer_id)
        self.assertFalse(result)

        review_calculation_id = self.db.add_review_calculation(
            reviewer_id, calculator_id, 2, 4, {'x': 3, 'y': 4}, {'z': 5},
            '0.0.0', 'test review calculation')

        result = self.db.search_review_calculation(reviewer_id=reviewer_id)
        self.assertIsInstance(result, CalculationCollection)
        self.assertEqual(list(result.keys()), [review_calculation_id])

        calc = result[review_calculation_id]
        self.assertIsInstance(calc, ReviewCalculation)
        self.assertEqual(calc.id, review_calculation_id)
        self.assertEqual(calc.reviewer_id, reviewer_id)
        self.assertEqual(calc.calculator_id, calculator_id)
        self.assertEqual(calc.mode, 2)
        self.assertEqual(calc.version, 4)
        self.assertEqual(calc.input, {'x': 3, 'y': 4})
        self.assertEqual(calc.output, {'z': 5})
        self.assertEqual(calc.calc_version, '0.0.0')
        self.assertEqual(calc.title, 'test review calculation')
        self.assertIsInstance(calc.date_run, datetime)

        self.db.update_review_calculation(
            review_calculation_id=review_calculation_id,
            mode=3, version=5, input_={'x': 30, 'y': 40}, output={'z': 50},
            calc_version='0.0.1', title='altered review calculation')

        calc = self.db.get_review_calculation(review_calculation_id)
        self.assertIsInstance(calc, ReviewCalculation)
        self.assertEqual(calc.id, review_calculation_id)
        self.assertEqual(calc.reviewer_id, reviewer_id)
        self.assertEqual(calc.calculator_id, calculator_id)
        self.assertEqual(calc.mode, 3)
        self.assertEqual(calc.version, 5)
        self.assertEqual(calc.input, {'x': 30, 'y': 40})
        self.assertEqual(calc.output, {'z': 50})
        self.assertEqual(calc.calc_version, '0.0.1')
        self.assertEqual(calc.title, 'altered review calculation')
        self.assertIsInstance(calc.date_run, datetime)

        self.assertEqual(
            self.db.sync_review_calculation(
                reviewer_id, CalculationCollection()),
            (0, 0, 1))

        with self.assertRaises(NoSuchRecord):
            self.db.get_review_calculation(review_calculation_id)

    def test_moc(self):
        facility_id = self.db.ensure_facility('moc testing facility')

        moc_a = MOC(order=1, cells=(4, 7))

        moc_id = self.db.add_moc(facility_id, 'test',
                                 'A Test MOC', FormatType.PLAIN,
                                 True, moc_a)
        self.assertIsInstance(moc_id, int)

        with self.assertRaises(NoSuchRecord):
            self.db.get_moc_fits(moc_id + 1)

        moc_a_fits_fetched = self.db.get_moc_fits(moc_id)
        moc_a_fetched = read_moc(buff=moc_a_fits_fetched)
        self.assertEqual(moc_a_fetched, moc_a)

        mocs = self.db.search_moc(facility_id, None, with_description=True)
        self.assertIsInstance(mocs, ResultCollection)
        self.assertIn(moc_id, mocs)
        moc_info = mocs[moc_id]
        self.assertIsInstance(moc_info, MOCInfo)
        self.assertEqual(moc_info.id, moc_id)
        self.assertEqual(moc_info.name, 'test')
        self.assertEqual(moc_info.description, 'A Test MOC')
        self.assertEqual(moc_info.public, True)
        self.assertIsInstance(moc_info.uploaded, datetime)
        self.assertEqual(moc_info.num_cells, 2)
        self.assertAlmostEqual(moc_info.area, 1718.873, places=3)
        self.assertEqual(moc_info.state, AttachmentState.NEW)

        # Update the moc_cell table (emulating poll process).
        update = self.db.update_moc_cell(moc_id, moc_a, block_pause=0)
        self.assertEqual(update, {1: 'insert'})

        result = self.db.search_moc_cell(facility_id, None, 2, 16)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 1)
        self.assertIn(moc_id, result)
        moc_info = result[moc_id]
        self.assertIsInstance(moc_info, MOCInfo)
        self.assertEqual(moc_info.id, moc_id)
        self.assertEqual(moc_info.name, 'test')
        self.assertIsNone(moc_info.description)
        self.assertIsNone(moc_info.num_cells)
        self.assertIsNone(moc_info.area)

        result = self.db.search_moc_cell(facility_id, None, 2, 32)
        self.assertEqual(len(result), 0)

        result = self.db.search_moc_cell(facility_id, None, 2, 20)
        self.assertEqual(len(result), 0)

        moc_b = MOC(order=1, cells=(5, 6))

        self.db.update_moc(moc_id, 'test2',
                           'Another Test MOC', FormatType.PLAIN,
                           False, moc_b)

        moc_b_fits_fetched = self.db.get_moc_fits(moc_id)
        moc_b_fetched = read_moc(buff=moc_b_fits_fetched)
        self.assertEqual(moc_b_fetched, moc_b)

        # Update the moc_cell table (emulating poll process).
        update = self.db.update_moc_cell(moc_id, moc_b, block_pause=0)
        self.assertEqual(update, {1: 'bulk'})

        cell_query = self.db._search_moc_cell_query(2, 20)
        self.assertEqual(cell_query, [
            (2, 20, False),
            (1, 5, False),
            (0, 1, False),
        ])

        result = self.db.search_moc_cell(facility_id, None, 2, 20)
        self.assertEqual(len(result), 1)

        # Multi-cell search with 1 match.
        cell_set = set((80, 81, 84, 88))
        cell_query = self.db._search_moc_cell_query(3, cell_set)
        self.assertEqual(cell_query, [
            (3, set((80, 81, 84, 88)), True),
            (2, set((20, 21, 22)), True),
            (1, 5, False),
            (0, 1, False),
        ])

        result = self.db.search_moc_cell(facility_id, None, 3, cell_set)
        self.assertEqual(len(result), 1)

        # Multi-cell search with 2 matches.
        cell_set = set((80, 100, 120))
        cell_query = self.db._search_moc_cell_query(3, cell_set)
        self.assertEqual(cell_query, [
            (3, set((80, 100, 120)), True),
            (2, set((20, 25, 30)), True),
            (1, set((5, 6, 7)), True),
            (0, 1, False),
        ])

        result = self.db.search_moc_cell(facility_id, None, 3, cell_set)
        self.assertEqual(len(result), 1)

        # Multi-cell search with no matches.
        cell_set = set((3, 4, 5, 160, 161, 162, 163, 164))
        cell_query = self.db._search_moc_cell_query(3, cell_set)
        self.assertEqual(cell_query, [
            (3, set((3, 4, 5, 160, 161, 162, 163, 164)), True),
            (2, set((0, 1, 40, 41)), True),
            (1, set((0, 10)), True),
            (0, set((0, 2)), True),
        ])

        result = self.db.search_moc_cell(facility_id, None, 3, cell_set)
        self.assertEqual(len(result), 0)

        # Multi-cell style search with only one cell.
        cell_set = set((80,))
        cell_query = self.db._search_moc_cell_query(3, cell_set)
        self.assertEqual(cell_query, [
            (3, 80, False),
            (2, 20, False),
            (1, 5, False),
            (0, 1, False),
        ])

        result = self.db.search_moc_cell(facility_id, None, 3, cell_set)
        self.assertEqual(len(result), 1)

        with self.assertRaises(ConsistencyError):
            self.db.update_moc(moc_id, state=AttachmentState.ERROR,
                               state_prev=AttachmentState.PROCESSING,
                               state_is_system=True)

        with self.assertRaisesRegex(Error, 'Invalid state'):
            self.db.update_moc(moc_id, state=999,
                               state_prev=AttachmentState.PROCESSING,
                               state_is_system=True)

        with self.assertRaisesRegex(Error, 'Invalid previous state'):
            self.db.update_moc(moc_id, state=AttachmentState.ERROR,
                               state_prev=999,
                               state_is_system=True)

        self.db.update_moc(moc_id, state=AttachmentState.ERROR,
                           state_prev=AttachmentState.NEW,
                           state_is_system=True)

        moc_info = self.db.search_moc(facility_id, None, moc_id=moc_id,
                                      with_description=True).get_single()
        self.assertIsInstance(moc_info, MOCInfo)
        self.assertEqual(moc_info.id, moc_id)
        self.assertEqual(moc_info.name, 'test2')
        self.assertEqual(moc_info.description, 'Another Test MOC')
        self.assertEqual(moc_info.public, False)
        self.assertIsInstance(moc_info.uploaded, datetime)
        self.assertEqual(moc_info.num_cells, 2)
        self.assertAlmostEqual(moc_info.area, 1718.873, places=3)
        self.assertEqual(moc_info.state, AttachmentState.ERROR)

        self.db.delete_moc(facility_id, moc_id)
        mocs = self.db.search_moc(facility_id=None, public=None)
        self.assertEqual(len(mocs), 0)

    def test_moc_update(self):
        facility_id = self.db.ensure_facility('moc testing facility')

        moc = MOC(order=5, cells=(1, 2, 3))

        moc_id = self.db.add_moc(facility_id, 'test', 'test', FormatType.PLAIN,
                                 True, moc)
        self.assertIsInstance(moc_id, int)

        self.assertEqual(self.db.update_moc_cell(moc_id, moc, block_pause=0), {
            5: 'insert'})
        self.assertEqual(self.db._get_moc_from_cell(moc_id), moc)

        moc.add(7, (1001, 1002, 1003))

        self.assertEqual(self.db.update_moc_cell(moc_id, moc, block_pause=0), {
            5: 'unchanged',
            7: 'insert'})
        self.assertEqual(self.db._get_moc_from_cell(moc_id), moc)

        moc.add(5, (11, 12, 13))
        moc.remove(7, (1001, 1002, 1003))
        self.assertEqual(self.db.update_moc_cell(moc_id, moc, block_pause=0), {
            5: 'individual',
            7: 'delete'})
        self.assertEqual(self.db._get_moc_from_cell(moc_id), moc)

        moc.add(5, (21, 22, 23))
        self.assertEqual(self.db.update_moc_cell(moc_id, moc, block_pause=0), {
            5: 'individual'})
        self.assertEqual(self.db._get_moc_from_cell(moc_id), moc)

        moc.add(5, (31, 32, 33))
        moc.remove(5, (1, 2, 3, 11, 12, 13))
        self.assertEqual(self.db.update_moc_cell(moc_id, moc, block_pause=0), {
            5: 'bulk'})
        self.assertEqual(self.db._get_moc_from_cell(moc_id), moc)

        # Check the MOC really ended up as expected.
        self.assertEqual(list(moc), [(5, frozenset((21, 22, 23, 31, 32, 33)))])
