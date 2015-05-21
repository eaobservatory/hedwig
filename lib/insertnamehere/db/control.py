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

from contextlib import contextmanager
from threading import Lock

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import select
from sqlalchemy.sql.functions import count

from ..error import ConsistencyError, DatabaseError, DatabaseIntegrityError
from ..type import ResultCollection
from .part.people import PeoplePart
from .part.proposal import ProposalPart


class Database(PeoplePart, ProposalPart):
    def __init__(self, engine):
        """
        Create database controller object.
        """

        self._engine = engine
        self._lock = Lock()

    @contextmanager
    def _transaction(self):
        """
        Private context manager method for handling database transactions.

        Obtains a lock and then yields a connection object.  SQLAlchemy
        errors are trapped and re-raised as our DatabaseError, other than
        for IntegrityError which is re-raised as DatabaseIntegrityError.
        """

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

    def _sync_records(self, conn, table, key_column, key_value,
                      records, update_columns=None, verified_columns=()):
        """
        Update a set of database records to match the given set of records.

        Queries the given table for rows where the value of the specified
        key column matches the specified key value.  Then compares the
        result to the specified collection of values and performs
        a series of inserts, updates and deletes to bring the database
        to a state matching the specified values.  Records are matched
        by their "id" values, but the dictionary keys of "records"
        don't matter.

        If update columns are specified, then only those columns are
        considered, both for comparison and updating.

        key_column and update_columns should be a column object and a list
        of column objects respectively.

        If a column is being updated which is listed in "verified columns"
        then a column called "verified" is set to False.  (If verified
        columns exist, then update_columns should probably be set to prevent
        the "verified" column being edited!)
        """

        # Initialize debugging counters.
        n_insert = n_update = n_delete = 0

        # Where update columns specified?  If not, assume everything should
        # be updated except for the key.
        if update_columns is None:
            # WARNING: Python-2 only.
            update_columns = filter(
                (lambda x: x is not key_column and x is not table.c.id),
                table.c)

        # Fetch the current set of records.
        existing = ResultCollection()
        for row in conn.execute(table.select().where(key_column == key_value)):
            existing[row['id']] = row

        # Keep track of identifiers in case the input "records" list tries
        # mentioning the same record twice.
        considered = set()

        # For each given value, check whether or not it already existed.
        for value in records.values():
            id_ = value.id

            # Have we seen this identifier before?
            if id_ in considered:
                raise ConsistencyError(
                    'the identifier {0} appears more than once', id_)

            considered.add(id_)
            previous = existing.pop(id_, None)

            if previous is None:
                # Insert the new value.
                values = {key_column: key_value}
                for column in update_columns:
                    values[column] = getattr(value, column.key)
                conn.execute(table.insert().values(values))
                n_insert += 1

            else:
                # Check if update is necessary, and if necessary, do it.
                values = {}
                for column in update_columns:
                    col_val = getattr(value, column.key)
                    if previous[column] != col_val:
                        values[column] = col_val
                        if column in verified_columns:
                            values[table.c.verified] = False

                if values:
                    conn.execute(table.update().where(
                        table.c.id == id_
                    ).values(values))
                    n_update += 1

        # Delete remaining un-matched entries.
        for id_ in existing:
            conn.execute(table.delete().where(table.c.id == id_))
            n_delete += 1

        return (n_insert, n_update, n_delete)
