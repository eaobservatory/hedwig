# Copyright (C) 2015 East Asian Observatory
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

from insertnamehere.error import ConsistencyError, DatabaseIntegrityError, \
    NoSuchRecord
from insertnamehere.type import Calculation, ResultCollection

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
        (facility_id, proposal_id) = self._create_test_proposal()
        calculator_id = self.db.ensure_calculator(facility_id, 'testcalc')

        calculation_id = self.db.add_calculation(
            proposal_id, calculator_id, 1, 10, {'a': 10, 'b': 20}, {'c': 30})

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
        self.assertIsInstance(calc.date_run, datetime)

        self.db.update_calculation(
            calculation_id=calculation_id,
            mode=2, version=20, input_={'a': 11, 'b': 22}, output={'c': 33})

        result = self.db.search_calculation()
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 1)
        self.assertIn(calculation_id, result)
        calc = result[calculation_id]
        self.assertIsInstance(calc, Calculation)
        self.assertEqual(calc.mode, 2)
        self.assertEqual(calc.version, 20)
        self.assertEqual(calc.input, {'a': 11, 'b': 22})
        self.assertEqual(calc.output, {'c': 33})

    def _create_test_proposal(self):
        facility_id = self.db.ensure_facility('f')
        semester_id = self.db.add_semester(
            facility_id, 's', 's',
            datetime(2000, 1, 1), datetime(2000, 12, 31))
        queue_id = self.db.add_queue(facility_id, 'q', 'q')
        call_id = self.db.add_call(
            semester_id, queue_id,
            datetime(1999, 4, 1), datetime(1999, 4, 2),
            100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '')
        affiliation_id = self.db.add_affiliation(queue_id, 'a')
        person_id = self.db.add_person('per')
        proposal_id = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'prop')
        self.assertIsInstance(proposal_id, int)
        return (facility_id, proposal_id)
