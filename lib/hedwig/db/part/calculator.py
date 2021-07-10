# Copyright (C) 2015-2018 East Asian Observatory
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
from time import sleep

from pymoc import MOC
from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, exists, not_, or_
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql.functions import max as max_

from ...error import ConsistencyError, Error, FormattedError, UserError
from ...file.moc import write_moc
from ...type.collection import CalculationCollection, ResultCollection
from ...type.enum import AttachmentState, FormatType
from ...type.simple import Calculation, MOCInfo, ReviewCalculation
from ...util import is_list_like, list_in_blocks, list_in_ranges
from ..meta import calculator, calculation, facility, \
    moc, moc_cell, moc_fits, review_calculation
from ..util import require_not_none


class CalculatorPart(object):
    def add_calculation(
            self, proposal_id,
            calculator_id, mode, version, input_, output, calc_version, title):
        return self._add_calculation(
            calculation, calculation.c.proposal_id, proposal_id,
            calculator_id, mode, version, input_, output, calc_version, title)

    def _add_calculation(
            self, table, key_column, key_value,
            calculator_id, mode, version, input_, output, calc_version, title):
        with self._transaction() as conn:
            table_alias = table.alias()
            key_column_alias = table_alias.columns[key_column.name]

            result = conn.execute(table.insert().values({
                key_column: key_value,
                table.c.sort_order: select(
                    [coalesce(max_(table_alias.c.sort_order), 0) + 1]
                    ).where(key_column_alias == key_value),
                table.c.calculator_id: calculator_id,
                table.c.mode: mode,
                table.c.version: version,
                table.c.input: input_,
                table.c.output: output,
                table.c.date_run: datetime.utcnow(),
                table.c.calc_version: calc_version,
                table.c.title: title,
            }))

            return result.inserted_primary_key[0]

    def add_moc(self, facility_id, name, description, description_format,
                public, moc_object):
        if not FormatType.is_valid(description_format, is_system=True):
            raise UserError('Text format not recognised.')

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
                moc.c.state: AttachmentState.NEW,
            }))

            moc_id = result.inserted_primary_key[0]

            conn.execute(moc_fits.insert().values({
                moc_fits.c.moc_id: moc_id,
                moc_fits.c.fits: write_moc(moc_object),
            }))

        return moc_id

    def add_review_calculation(
            self, reviewer_id,
            calculator_id, mode, version, input_, output, calc_version, title):
        return self._add_calculation(
            review_calculation, review_calculation.c.reviewer_id, reviewer_id,
            calculator_id, mode, version, input_, output, calc_version, title)

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

    def ensure_calculator(self, facility_id, code, _read_only=False):
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

            if _read_only:
                raise FormattedError(
                    'read-only option: can not create calculator \'{}\'', code)

            result = conn.execute(calculator.insert().values({
                calculator.c.facility_id: facility_id,
                calculator.c.code: code,
            }))

            return result.inserted_primary_key[0]

    def get_calculation(self, id_):
        return self.search_calculation(calculation_id=id_).get_single()

    @require_not_none
    def get_moc_fits(self, moc_id):
        with self._transaction() as conn:
            return conn.execute(select([moc_fits.c.fits]).where(
                moc_fits.c.moc_id == moc_id)).scalar()

    def get_review_calculation(self, id_):
        return self.search_review_calculation(
            review_calculation_id=id_).get_single()

    def search_calculation(self, calculation_id=None, proposal_id=None):
        return self._search_calculation(
            calculation, calculation.c.proposal_id, proposal_id,
            id_=calculation_id, result_class=Calculation)

    def _search_calculation(
            self, table, key_column, key_value, id_,
            result_class):
        stmt = table.select()

        if id_ is not None:
            stmt = stmt.where(table.c.id == id_)

        if key_value is not None:
            stmt = stmt.where(key_column == key_value)

        ans = CalculationCollection()

        with self._transaction() as conn:
            for row in conn.execute(
                    stmt.order_by(table.c.sort_order.asc())):
                ans[row['id']] = result_class(**row)

        return ans

    def search_moc(self, facility_id, public, moc_id=None, state=None,
                   with_description=False, order_by_date=False):
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
            moc.c.state,
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
            if public:
                stmt = stmt.where(moc.c.public)
            else:
                stmt = stmt.where(not_(moc.c.public))

        if moc_id is not None:
            stmt = stmt.where(moc.c.id == moc_id)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(moc.c.state.in_(state))
            else:
                stmt = stmt.where(moc.c.state == state)

        if order_by_date:
            stmt = stmt.order_by(moc.c.uploaded.desc())
        else:
            stmt = stmt.order_by(moc.c.name.asc())

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = MOCInfo(**values)

        return ans

    def search_moc_cell(self, facility_id, public, order, cell):
        """
        Search for a MOC containing the given cell, or a cell
        at a lower order containing this cell.

        Multiple cells can be specified to allow a certain region
        to be searched.  The number of cells given should be reasonable
        since this function assembles a single SQL query for all cells
        at all levels being searched.
        """

        options = []
        for (cell_order, cell_query, multiple_cells) in \
                self._search_moc_cell_query(order, cell):
            if multiple_cells:
                conditions = []
                (cell_ranges, cell_individual) = list_in_ranges(cell_query)

                for (cell_min, cell_max) in cell_ranges:
                    conditions.append(moc_cell.c.cell.between(cell_min,
                                                              cell_max))
                if cell_individual:
                    conditions.append(moc_cell.c.cell.in_(cell_individual))

                condition = or_(*conditions)

            else:
                condition = (moc_cell.c.cell == cell_query)

            options.append(and_(moc_cell.c.order == cell_order, condition))

        stmt = select([
            moc.c.id,
            moc.c.facility_id,
            moc.c.name,
            moc.c.public,
        ]).select_from(moc).where(
            exists().select_from(moc_cell).where(and_(
                moc_cell.c.moc_id == moc.c.id,
                or_(*options))))

        if facility_id is not None:
            stmt = stmt.where(moc.c.facility_id == facility_id)

        if public is not None:
            if public:
                stmt = stmt.where(moc.c.public)
            else:
                stmt = stmt.where(not_(moc.c.public))

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                ans[row['id']] = MOCInfo(description=None,
                                         description_format=None,
                                         uploaded=None,
                                         num_cells=None, area=None, state=None,
                                         **row)

        return ans

    def _search_moc_cell_query(self, order, cell):
        """
        Generate list of orders and cells to use in a MOC cell search.
        """

        orders = []

        multiple_cells = is_list_like(cell)

        for cell_order in range(order, -1, -1):
            # If the list-like object only has one entry, extract it.
            if multiple_cells and len(cell) == 1:
                cell = next(iter(cell))
                multiple_cells = False

            orders.append((cell_order, cell, multiple_cells))

            if multiple_cells:
                cell = set(x // 4 for x in cell)
            else:
                cell //= 4

        return orders

    def search_review_calculation(
            self, review_calculation_id=None, reviewer_id=None):
        return self._search_calculation(
            review_calculation, review_calculation.c.reviewer_id, reviewer_id,
            id_=review_calculation_id, result_class=ReviewCalculation)

    def sync_proposal_calculation(self, proposal_id, records):
        """
        Update the calculations for a proposal.

        Currently only deleting calculations and updating the sort order
        is supported.
        """

        with self._transaction() as conn:
            return self._sync_records(
                conn, calculation, calculation.c.proposal_id, proposal_id,
                records, update_columns=(
                    calculation.c.sort_order,
                ), forbid_add=True)

    def sync_review_calculation(self, reviewer_id, records):
        """
        Update the calculations for a reviewer.

        Currently only deleting calculations and updating the sort order
        is supported.
        """

        with self._transaction() as conn:
            return self._sync_records(
                conn, review_calculation,
                review_calculation.c.reviewer_id, reviewer_id,
                records, update_columns=(
                    review_calculation.c.sort_order,
                ), forbid_add=True)

    def update_calculation(
            self, calculation_id,
            mode, version, input_, output, calc_version, title):
        return self._update_calculation(
            calculation, calculation_id,
            mode, version, input_, output, calc_version, title)

    def _update_calculation(
            self, table, id_,
            mode, version, input_, output, calc_version, title):
        values = {
            table.c.mode: mode,
            table.c.version: version,
            table.c.input: input_,
            table.c.output: output,
            table.c.date_run: datetime.utcnow(),
            table.c.calc_version: calc_version,
            table.c.title: title,
        }

        with self._transaction() as conn:
            result = conn.execute(table.update().where(
                table.c.id == id_
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating table {} entry with id={}',
                    table.name, id_)

    def update_moc(self, moc_id, name=None,
                   description=None, description_format=None, public=None,
                   moc_object=None, state=None, state_prev=None):
        values = {}

        stmt = moc.update().where(moc.c.id == moc_id)

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

        if moc_object is not None:
            values[moc.c.uploaded] = datetime.utcnow()
            values[moc.c.num_cells] = moc_object.cells
            values[moc.c.area] = moc_object.area_sq_deg
            values[moc.c.state] = AttachmentState.NEW

        elif state is not None:
            if not AttachmentState.is_valid(state):
                raise Error('Invalid state.')

            values[moc.c.state] = state

        if state_prev is not None:
            if not AttachmentState.is_valid(state_prev):
                raise Error('Invalid previous state.')
            stmt = stmt.where(moc.c.state == state_prev)

        if not values:
            raise Error('No moc updates specified')

        with self._transaction() as conn:
            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating moc with id={}', moc_id)

            if moc_object is not None:
                conn.execute(moc_fits.update().where(
                    moc_fits.c.moc_id == moc_id
                ).values({moc_fits.c.fits: write_moc(moc_object)}))

    def update_moc_cell(self, moc_id, moc_object,
                        block_size=1000, block_pause=1):
        """
        Update the moc_cell database table.

        The entries for the MOC identified by moc_id are updated so that
        they match the entries of the MOC provided as moc_object.

        This method works in an order-by-order manner and attempts
        to determine the most efficient update method for each order.
        If the number of original cells is greater than the number of
        unchanged cells, then all exising entries are deleted and the new
        cells inserted.  Otherwise removed cells are deleted individually
        and newly added cells inserted.

        For debugging purposes, this method returns a dictionary indicating
        the action taken for each order.
        """

        debug_info = {}

        moc_existing = self._get_moc_from_cell(moc_id)

        for order in range(0, max(moc_existing.order, moc_object.order) + 1):
            # MOC object gives us a frozenset object of cells for the order.
            # We want to work in terms of these sets in order to have the
            # database updated to exactly the same representation.  If we
            # tried taking the intersection of MOCs directly, for example,
            # then the MOC object may alter the representation, such as by
            # split cells.
            existing = moc_existing[order]
            replacement = moc_object[order]

            bulk_delete = False
            delete = None
            insert = None

            # Determine what to do: simpler cases first.
            if not replacement:
                if not existing:
                    # No cells in either MOC: nothing to do.
                    pass

                else:
                    # No cells in the replacement moc: delete existing cells.
                    debug_info[order] = 'delete'
                    bulk_delete = True

            elif not existing:
                # No exising cells present: just insert everything.
                debug_info[order] = 'insert'
                insert = replacement

            else:
                # There are existing and replacement cells: determine best
                # strategy.
                intersection = existing.intersection(replacement)

                if len(existing) > len(intersection):
                    # Bulk deletion seems most efficient.
                    debug_info[order] = 'bulk'
                    bulk_delete = True
                    insert = replacement
                else:
                    # Compute sets of individual deletions and replacements.
                    delete = existing.difference(intersection)
                    insert = replacement.difference(intersection)

                    if (not delete) and (not insert):
                        # No cells changed: nothing to do.
                        debug_info[order] = 'unchanged'
                        continue

                    debug_info[order] = 'individual'

            # Now go ahead and perform update actions.
            if bulk_delete:
                with self._transaction() as conn:
                    conn.execute(moc_cell.delete().where(and_(
                        moc_cell.c.moc_id == moc_id,
                        moc_cell.c.order == order)))

            if delete is not None:
                for delete_block in list_in_blocks(delete, block_size):
                    sleep(block_pause)
                    with self._transaction() as conn:
                        for cell in delete_block:
                            conn.execute(moc_cell.delete().where(and_(
                                moc_cell.c.moc_id == moc_id,
                                moc_cell.c.order == order,
                                moc_cell.c.cell == cell)))

            if insert is not None:
                for insert_block in list_in_blocks(insert, block_size):
                    sleep(block_pause)
                    with self._transaction() as conn:
                        for cell in insert_block:
                            conn.execute(moc_cell.insert().values({
                                moc_cell.c.moc_id: moc_id,
                                moc_cell.c.order: order,
                                moc_cell.c.cell: cell,
                            }))

        return debug_info

    def _get_moc_from_cell(self, moc_id, _conn=None):
        """
        Retrieve a MOC object from the moc_cell database table.

        This routine should not generally be used to retrieve a MOC: instead
        use get_moc_fits, or search the moc using search_moc_cell.  This
        method is intended to be used only to optimize update operations
        (and for use by the test suite).
        """

        moc_object = MOC()

        with self._transaction(_conn=_conn) as conn:
            for (order, cell) in conn.execute(select([
                    moc_cell.c.order, moc_cell.c.cell,
                    ]).where(moc_cell.c.moc_id == moc_id)):
                moc_object.add(order, (cell,))

        return moc_object

    def update_review_calculation(
            self, review_calculation_id,
            mode, version, input_, output, calc_version, title):
        return self._update_calculation(
            review_calculation, review_calculation_id,
            mode, version, input_, output, calc_version, title)
