# Copyright (C) 2015-2016 East Asian Observatory
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
from random import randint

from sqlalchemy.sql import insert
from sqlalchemy.pool import StaticPool

from hedwig import auth
from hedwig.config import _get_db_class
from hedwig.db.meta import metadata
from hedwig.db.engine import get_engine
from hedwig.type.enum import BaseCallType, FormatType

from .dummy_config import DummyConfigTestCase


def get_dummy_database(randomize_ids=True, allow_multi_threaded=False,
                       facility_spec=None):
    """
    Create in-memory SQL database for testing.

    If the randomize_ids argument is true, then the "sqlite_sequence" table
    will be manipulated to give each table a starting auto-increment value
    in the range 1-1000000.  This is to try to prevent accidental matches
    between id columns in different tables which would stop the test suite
    detecting the usage of incorrect id numbers.
    """

    # Do this first to load the facility metadata.
    CombinedDatabase = _get_db_class(facility_spec)

    connect_options = {}

    if allow_multi_threaded:
        connect_options['connect_args'] = {'check_same_thread': False}
        connect_options['poolclass'] = StaticPool

    engine = get_engine('sqlite:///:memory:', **connect_options)

    metadata.create_all(engine)

    if randomize_ids:
        with engine.begin() as conn:
            for table in metadata.tables.keys():
                conn.execute('INSERT INTO sqlite_sequence (name, seq)'
                             'VALUES ("{}", {})'.format(table,
                                                        randint(1, 1000000)))

    return CombinedDatabase(engine)


class DBTestCase(DummyConfigTestCase):
    facility_spec = 'Generic'

    def setUp(self):
        super(DBTestCase, self).setUp()

        self.db = get_dummy_database(facility_spec=self.facility_spec)

        self.orig_auth_rounds = auth._rounds
        self.orig_hash_delay = auth.password_hash_delay

        auth._rounds = 10
        auth.password_hash_delay = 0

    def tearDown(self):
        super(DBTestCase, self).tearDown()

        del self.db

        auth._rounds = self.orig_auth_rounds
        auth.password_hash_delay = self.orig_hash_delay

    def _create_test_proposal(self,
                              facility_id=None, facility_code='test facility'):
        if facility_id is None:
            facility_id = self.db.ensure_facility(facility_code)

        semester_id = self.db.add_semester(
            facility_id, 'test', 'test',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        queue_id = self.db.add_queue(facility_id, 'test', 'test')
        call_id = self.db.add_call(
            BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
            FormatType.PLAIN)
        affiliation_id = self.db.add_affiliation(queue_id, 'test')
        person_id = self.db.add_person('Test Person')

        return self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Test Title')
