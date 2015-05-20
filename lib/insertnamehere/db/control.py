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

from ..error import DatabaseError, DatabaseIntegrityError
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
