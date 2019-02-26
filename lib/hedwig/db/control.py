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

from collections import deque, namedtuple
from contextlib import contextmanager
from threading import Lock

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_
from sqlalchemy.sql.functions import count

from ..error import ConsistencyError, Error, \
    DatabaseError, DatabaseIntegrityError, UserError
from ..type.collection import ResultCollection
from ..util import is_list_like, list_in_blocks
from .part.calculator import CalculatorPart
from .part.message import MessagePart
from .part.people import PeoplePart
from .part.proposal import ProposalPart
from .part.review import ReviewPart


RecordUpdate = namedtuple(
    'RecordUpdate',
    ('id', 'value', 'updates', 'value_unique_key', 'previous_unique_key',
     'deferred'))


class Database(CalculatorPart, MessagePart, PeoplePart, ProposalPart,
               ReviewPart):
    def __init__(self, engine, query_block_size=50):
        """
        Create database controller object.
        """

        self._engine = engine
        self._lock = Lock()

        self.query_block_size = query_block_size

    @contextmanager
    def _transaction(self, _conn=None):
        """
        Private context manager method for handling database transactions.

        Obtains a lock and then yields a connection object.  SQLAlchemy
        errors are trapped and re-raised as our DatabaseError, other than
        for IntegrityError which is re-raised as DatabaseIntegrityError.

        If "_conn" is not None, however, simply yields its value.  This is
        so that methods can optionally take a transaction argument for when
        they are called from within an existing transaction.
        """

        if _conn is not None:
            yield _conn
            return

        try:
            with self._lock:
                with self._engine.begin() as conn:
                    yield conn
        except IntegrityError as e:
            raise DatabaseIntegrityError(e)
        except SQLAlchemyError as e:
            raise DatabaseError(e)

    def _exists_id(self, conn, table, id_):
        """
        Test whether an identifier exists in the given table.
        """

        return 0 < conn.execute(select([count(table.c.id)]).where(
            table.c.id == id_,
        )).scalar()

    def _iter_stmt(self, stmt, iter_field, iter_list):
        """
        Generate sequence of query statements.

        This method takes an SQLAlchemy statement and yields a number
        of statements with an additional where clause.  This clause
        requires the field `iter_field` to have a value in `iter_list`.
        When `iter_list` is larger than the object's `query_block_size`
        attribute then multiple statements will be returned, where the
        list is broken into blocks of this size.

        If `iter_field` is `None` then the given `stmt` is yielded as-is.

        :param stmt: statement to be modified.
        :param iter_field: field being searched.
        :param iter_list: list (or other iterable) or search values.
        """

        if iter_field is None:
            yield stmt

        else:
            for iter_block in list_in_blocks(iter_list, self.query_block_size):
                yield stmt.where(iter_field.in_(iter_block))

    def _sync_records(self, conn, table, key_column, key_value, records,
                      update_columns=None, verified_columns=(),
                      forbid_add=False, forbid_delete=False,
                      record_match_column=None,
                      unique_columns=None, forbid_circular_reinsert=False):
        """
        Update a set of database records to match the given set of records.

        Queries the given table for rows where the value of the specified
        key column matches the specified key value.  Then compares the
        result to the specified collection of values and performs
        a series of inserts, updates and deletes to bring the database
        to a state matching the specified values.  Records are matched
        by their "id" values, but the dictionary keys of "records"
        don't matter.  New records can be given with an "id" of None,
        or an "id" which doesn't match an existing record.

        If update columns are specified, then only those columns are
        considered, both for comparison and updating.

        key_column and update_columns should be a column object and a list
        of column objects respectively.  key_column and key_value can
        alternatively be tuples/lists (of equal length) for cases where
        multiple columns are needed to determine membership of the set of rows
        being updated.

        If a column is being updated which is listed in "verified columns"
        then a column called "verified" is set to False.  (If verified
        columns exist, then update_columns should probably be set to prevent
        the "verified" column being edited!)

        If "record_match_column" is specified then it will determine the
        column to use to match existing records to those given.  If not
        specified then the table's "id" column will be used.  Note this
        only applies to the existing database records -- we still expect
        to use the "id" field of the given records.

        The "unique_columns" argument should be used to indicate which
        columns being updated have unique constraints in the database.
        If a set of circular updates involving the unique columns is
        detected, then the loop will be broken by deleting and re-inserting
        one of the records, unless the "forbid_circular_reinsert" argument
        is given, in which case an error is raised.  Be aware that
        re-insertion currently only retains the columns being updated!
        If a syncing operation is added for which this is a problem,
        the insertions should be split into new records and re-insertions
        so that they can be handled separately.
        """

        # Initialize debugging counters.
        n_insert = n_update = n_delete = 0

        # Determine if key_column and key_value are plain strings.
        if is_list_like(key_column):
            if len(key_column) != len(key_value):
                raise Error('key_column and key_value differ in length')
            condition = and_(*(k == v for k, v in zip(key_column, key_value)))
        else:
            condition = key_column == key_value
            key_column = (key_column,)
            key_value = (key_value,)

        # Were update columns specified?  If not, assume everything should
        # be updated except for the key.
        if update_columns is None:
            update_columns = [x for x in table.c
                              if x is not table.c.id and x not in key_column]

        # Is the record matching column specified?  If not use the "id" column.
        if record_match_column is None:
            record_match_column_name = table.c.id.name
        else:
            record_match_column_name = record_match_column.name

        # Fetch the current set of records.
        existing = ResultCollection()
        for row in conn.execute(table.select().where(condition)):
            existing[row[record_match_column_name]] = row

        # Keep track of identifiers in case the input "records" list tries
        # mentioning the same record twice.
        considered = set()

        # Queues of entries to be updated and entries to be inserted.
        # Each entry of the update queue is a RecordUpdate namedtuple.
        record_updates = deque()
        record_inserts = deque()

        # Prepare set to contain the tuples of the unique columns (where
        # specified) for each input record processed.
        seen_unique_key = set()

        # For each given value, check whether or not it already existed.
        for value in records.values():
            id_ = value.id

            if unique_columns is None:
                value_unique_key = None
            else:
                value_unique_key = \
                    tuple((getattr(value, x.name) for x in unique_columns))

                if value_unique_key in seen_unique_key:
                    raise UserError(
                        'There appear to be duplicate values amongst the '
                        'entries which you have entered.')

                seen_unique_key.add(value_unique_key)

            if id_ is None:
                # Allow completely new records to be given with id=None.
                previous = None

            else:
                # Have we seen this identifier before?
                if id_ in considered:
                    raise ConsistencyError(
                        'the identifier {} appears more than once', id_)

                considered.add(id_)
                previous = existing.pop(id_, None)

            if previous is None:
                if forbid_add:
                    raise UserError('New entries can not be added here.')

                record_inserts.append(value)
                n_insert += 1

            else:
                # Check if update is necessary.
                values = {}
                for column in update_columns:
                    col_val = getattr(value, column.name)
                    if previous[column] != col_val:
                        values[column] = col_val
                        if column in verified_columns:
                            values[table.c.verified] = False

                if values:
                    if unique_columns is None:
                        previous_unique_key = None
                    else:
                        previous_unique_key = \
                            tuple((previous[x] for x in unique_columns))

                    record_updates.append(RecordUpdate(
                        previous['id'], value, values,
                        value_unique_key, previous_unique_key, None))

        # Delete remaining un-matched entries.
        for existing_record in existing.values():
            if forbid_delete:
                raise UserError('Entries can not be deleted here.')

            conn.execute(
                table.delete().where(table.c.id == existing_record['id']))
            n_delete += 1

        # Iterate over record updates and apply as required.
        while record_updates:
            i = record_updates.popleft()

            # Check whether applying the update would cause a unique
            # constraint violation.
            if unique_columns is not None:
                # Use "any" rather than another loop because we wouldn't
                # be able to "continue" from the inner loop.
                if any((i.value_unique_key == j.previous_unique_key
                        for j in record_updates)):
                    # Check we didn't already defer this update without making
                    # more updates since.
                    if i.deferred == n_update:
                        if forbid_circular_reinsert:
                            raise UserError(
                                'Circular updates are not permitted here.')

                        # Delete this record and schedule it for re-insertion
                        # later.  Count this as an "update".
                        conn.execute(table.delete().where(table.c.id == i.id))
                        record_inserts.appendleft(i.value)
                        n_update += 1
                        continue

                    # Defer the conflicting update until later.  Record the
                    # current number of updates in the "deferred" entry so that
                    # we can detect if we return to this entry again without
                    # successfully having made any more updates.
                    record_updates.append(i._replace(deferred=n_update))
                    continue

            # Apply the update.
            conn.execute(table.update().where(
                table.c.id == i.id
            ).values(i.updates))
            n_update += 1

        # Iterate over record inserts and insert the new values.
        for value in record_inserts:
            values = dict(zip(key_column, key_value))

            for column in update_columns:
                values[column] = getattr(value, column.name)
            if record_match_column is not None:
                values[record_match_column] = value.id

            conn.execute(table.insert().values(values))

        return (n_insert, n_update, n_delete)

    def _remove_orphan_records(self, conn, table, column_link):
        """
        Remove entries from `table` which do not have a reference in
        `column_link` to their `id` field.

        :return: the number of rows deleted
        """

        result = conn.execute(table.delete().where(
            table.c.id.notin_(select([column_link]))))

        return result.rowcount
