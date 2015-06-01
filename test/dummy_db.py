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

from random import randint
from unittest import TestCase

from sqlalchemy.sql import insert

from insertnamehere import auth
from insertnamehere.db.control import Database
from insertnamehere.db.meta import metadata
from insertnamehere.db.engine import get_engine


def get_dummy_database(randomize_ids=True):
    """
    Create in-memory SQL database for testing.

    If the randomize_ids argument is true, then the "sqlite_sequence" table
    will be manipulated to give each table a starting auto-increment value
    in the range 1-1000000.  This is to try to prevent accidental matches
    between id columns in different tables which would stop the test suite
    detecting the usage of incorrect id numbers.
    """

    engine = get_engine('sqlite:///:memory:')

    metadata.create_all(engine)

    if randomize_ids:
        with engine.begin() as conn:
            for table in metadata.tables.keys():
                conn.execute('INSERT INTO sqlite_sequence (name, seq)'
                             'VALUES ("{0}", {1})'.format(table,
                                                          randint(1, 1000000)))

    return Database(engine)


class DBTestCase(TestCase):
    def setUp(self):
        self.db = get_dummy_database()
        auth._rounds = 10

    def tearDown(self):
        del self.db
