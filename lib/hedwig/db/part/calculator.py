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

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_

from ...error import ConsistencyError
from ...type import Calculation, ResultCollection
from ..meta import calculator, calculation, facility


class CalculatorPart(object):
    def add_calculation(self, proposal_id, calculator_id,
                        mode, version, input_, output, title):
        with self._transaction() as conn:
            result = conn.execute(calculation.insert().values({
                calculation.c.proposal_id: proposal_id,
                calculation.c.calculator_id: calculator_id,
                calculation.c.mode: mode,
                calculation.c.version: version,
                calculation.c.input: input_,
                calculation.c.output: output,
                calculation.c.date_run: datetime.utcnow(),
                calculation.c.title: title,
            }))

            return result.inserted_primary_key[0]

    def ensure_calculator(self, facility_id, code):
        """
        Ensure that a calculator exists in the database.

        If the calculator exists, its identifier is returned.  Otherwise
        it is added and the new identifier is returned.
        """

        if not code:
            raise ConsistencyError('The calculator code can not be blank.')

        with self._transaction() as conn:
            result = conn.execute(calculator.select().where(and_(
                calculator.c.facility_id == facility_id,
                calculator.c.code == code))).first()

            if result is not None:
                return result['id']

            result = conn.execute(calculator.insert().values({
                calculator.c.facility_id: facility_id,
                calculator.c.code: code,
            }))

            return result.inserted_primary_key[0]

    def get_calculation(self, id_):
        return self.search_calculation(calculation_id=id_).get_single()

    def search_calculation(self, calculation_id=None, proposal_id=None):
        stmt = calculation.select()

        if calculation_id is not None:
            stmt = stmt.where(calculation.c.id == calculation_id)

        if proposal_id is not None:
            stmt = stmt.where(calculation.c.proposal_id == proposal_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(calculation.c.id)):
                ans[row['id']] = Calculation(**row)

        return ans

    def sync_proposal_calculation(self, proposal_id, records):
        """
        Update the calculations for a proposal.

        Currently only deleting figures is supported.
        """

        with self._transaction() as conn:
            return self._sync_records(
                conn, calculation, calculation.c.proposal_id, proposal_id,
                records, update_columns=(), forbid_add=True)

    def update_calculation(self, calculation_id,
                           mode, version, input_, output, title):
        values = {
            calculation.c.mode: mode,
            calculation.c.version: version,
            calculation.c.input: input_,
            calculation.c.output: output,
            calculation.c.date_run: datetime.utcnow(),
            calculation.c.title: title,
        }

        with self._transaction() as conn:
            result = conn.execute(calculation.update().where(
                calculation.c.id == calculation_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating calculation with id={}',
                    calculation_id)
