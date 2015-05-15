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

from unittest import TestCase

from insertnamehere.db.control import Database
from insertnamehere.db.meta import metadata
from insertnamehere.db.engine import get_engine


def get_dummy_database():
    """
    Create in-memory SQL database for testing.
    """

    engine = get_engine('sqlite:///:memory:')

    metadata.create_all(engine)

    return Database(engine)


class DBTestCase(TestCase):
    def setUp(self):
        self.db = get_dummy_database()

    def tearDown(self):
        del self.db
