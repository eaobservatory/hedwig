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

from contextlib import closing
from cStringIO import StringIO
from datetime import datetime

from pymoc import MOC
from pymoc.io.fits import read_moc_fits
from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, or_
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql.functions import max as max_

from ...error import ConsistencyError, Error, UserError
from ...type import Calculation, FormatType, MOCInfo, \
    OrderedResultCollection, ResultCollection
from ..meta import calculator, calculation, facility, moc, moc_cell, moc_fits


class CalculatorPart(object):
    def add_calculation(self, proposal_id, calculator_id,
                        mode, version, input_, output, calc_version, title):
        with self._transaction() as conn:
            calculation_alias = calculation.alias()

            result = conn.execute(calculation.insert().values({
                calculation.c.proposal_id: proposal_id,
                calculation.c.sort_order: select(
                    [coalesce(max_(calculation_alias.c.sort_order), 0) + 1]
                    ).where(calculation_alias.c.proposal_id == proposal_id),
                calculation.c.calculator_id: calculator_id,
                calculation.c.mode: mode,
                calculation.c.version: version,
                calculation.c.input: input_,
                calculation.c.output: output,
                calculation.c.date_run: datetime.utcnow(),
                calculation.c.calc_version: calc_version,
                calculation.c.title: title,
            }))

            return result.inserted_primary_key[0]

    def add_moc(self, facility_id, name, description, description_format,
                public, moc_order, moc_file):
        if not FormatType.is_valid(description_format, is_system=True):
            raise UserError('Text format not recognised.')

        moc_object = MOC()
        with closing(StringIO(moc_file)) as f:
            read_moc_fits(moc_object, f)

        moc_object.normalize(max_order=moc_order)

        with self._transaction() as conn:
            result = conn.execute(moc.insert().values({
                moc.c.facility_id: facility_id,
                moc.c.name: name,
                moc.c.description: description,
                moc.c.description_format: description_format,
                moc.c.public: public,
                moc.c.uploaded: datetime.utcnow(),
                moc.c.num_cells: moc_object.cells,
                moc.c.area: moc_object.area_sq_deg,
            }))

            moc_id = result.inserted_primary_key[0]

            conn.execute(moc_fits.insert().values({
                moc_fits.c.moc_id: moc_id,
                moc_fits.c.fits: moc_file,
            }))

            self._update_moc_cells(conn, moc_id, moc_object, no_delete=True)

        return moc_id

    def delete_moc(self, facility_id, moc_id):
        """
        Delete a MOC from the database.
        """

        with self._transaction() as conn:
            result = conn.execute(moc.delete().where(and_(
                moc.c.facility_id == facility_id,
                moc.c.id == moc_id)))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched deleting moc with id={}', moc_id)

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

        ans = OrderedResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(
                    stmt.order_by(calculation.c.sort_order.asc())):
                ans[row['id']] = Calculation(**row)

        return ans

    def search_moc(self, facility_id, public, moc_id=None,
                   with_description=False):
        """
        Search for MOC records for a facility.
        """

        select_cols = [
            moc.c.id,
            moc.c.facility_id,
            moc.c.name,
            moc.c.public,
            moc.c.uploaded,
            moc.c.num_cells,
            moc.c.area,
        ]

        if with_description:
            select_cols.append(moc.c.description)
            select_cols.append(moc.c.description_format)
            default = {}
        else:
            default = {'description': None, 'description_format': None}

        stmt = select(select_cols)

        if facility_id is not None:
            stmt = stmt.where(moc.c.facility_id == facility_id)

        if public is not None:
            stmt = stmt.where(moc.c.public == public)

        if moc_id is not None:
            stmt = stmt.where(moc.c.id == moc_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(moc.c.id.asc())):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = MOCInfo(**values)

        return ans

    def search_moc_cell(self, facility_id, public, order, cell):
        """
        Search for a MOC containing the given cell, or a cell
        at a lower order containing this cell.
        """

        options = []
        for cell_order in range(order, -1, -1):
            options.append(and_(moc_cell.c.order == cell_order,
                                moc_cell.c.cell == cell))
            cell //= 4

        stmt = select([
            moc.c.id,
            moc.c.facility_id,
            moc.c.name,
            moc.c.public,
        ]).select_from(moc.join(moc_cell)).where(
            moc.c.facility_id == facility_id).where(or_(*options))

        if public is not None:
            stmt = stmt.where(moc.c.public == public)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                ans[row['id']] = MOCInfo(description=None,
                                         description_format=None,
                                         uploaded=None,
                                         num_cells=None, area=None, **row)

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
                           mode, version, input_, output, calc_version, title):
        values = {
            calculation.c.mode: mode,
            calculation.c.version: version,
            calculation.c.input: input_,
            calculation.c.output: output,
            calculation.c.date_run: datetime.utcnow(),
            calculation.c.calc_version: calc_version,
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

    def update_moc(self, moc_id, name=None,
                   description=None, description_format=None, public=None,
                   moc_order=None, moc_file=None):
        values = {}

        if name is not None:
            values[moc.c.name] = name

        if description is not None:
            values[moc.c.description] = description

        if description_format is not None:
            if not FormatType.is_valid(description_format, is_system=True):
                raise UserError('Text format not recognised.')
            values[moc.c.description_format] = description_format

        if public is not None:
            values[moc.c.public] = public

        moc_object = None
        if moc_file is not None:
            if moc_order is None:
                raise Error('MOC order not specified with updated MOC')

            moc_object = MOC()
            with closing(StringIO(moc_file)) as f:
                read_moc_fits(moc_object, f)

            moc_object.normalize(max_order=moc_order)

            values[moc.c.uploaded] = datetime.utcnow()
            values[moc.c.num_cells] = moc_object.cells
            values[moc.c.area] = moc_object.area_sq_deg

        if not values:
            raise Error('No moc updates specified')

        with self._transaction() as conn:
            result = conn.execute(moc.update().where(
                moc.c.id == moc_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating moc with id={}', moc_id)

            if moc_object is not None:
                conn.execute(moc_fits.update().where(
                    moc_fits.c.moc_id == moc_id
                ).values({moc_fits.c.fits: moc_file}))

                self._update_moc_cells(conn, moc_id, moc_object)

    def _update_moc_cells(self, conn, moc_id, moc_object, no_delete=False):
        if not no_delete:
            conn.execute(moc_cell.delete().where(
                moc_cell.c.moc_id == moc_id
            ))

        for (order, cells) in moc_object:
            for cell in cells:
                conn.execute(moc_cell.insert().values({
                    moc_cell.c.moc_id: moc_id,
                    moc_cell.c.order: order,
                    moc_cell.c.cell: cell,
                }))
