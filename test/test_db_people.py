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

from insertnamehere import auth
from insertnamehere.error import ConsistencyError, DatabaseIntegrityError, \
    UserError
from .dummy_db import DBTestCase


class DBUserTest(DBTestCase):
    def setUp(self):
        DBTestCase.setUp(self)
        auth._rounds = 10

    def test_user(self):
        # Check that we can create a user and get an integer user_id.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        # Attempting to re-create the same user is an error.
        with self.assertRaises(UserError):
            self.db.add_user('user1', 'pass1')

        # Ensure that, even if we don't check for duplicate users,
        # the database traps the error.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_user('user1', 'pass1', _test_skip_check=True)

        # Test successful authentication.
        self.assertEqual(self.db.authenticate_user('user1', 'pass1'), user_id)

        # Test unsuccessful authentication.
        self.assertIsNone(self.db.authenticate_user('user1', 'wrongpass'))
        self.assertIsNone(self.db.authenticate_user('user2', 'pass1'))

        # Test creation with reference to an existing person.
        person_id = self.db.add_person('User Three')
        user_id = self.db.add_user('user3', 'pass3', person_id=person_id)
        self.assertIsInstance(user_id, int)

        # Attempting to reference a non-existant person is an error.
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^person does not exist'):
            user_id = self.db.add_user('user4', 'pass4', person_id=999)

        # Check that we also detects this error via.
        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            user_id = self.db.add_user('user4', 'pass4', person_id=999,
                                       _test_skip_check=True)

    def test_user_person(self):
        # Check that we can create a person and get an integer person_id.
        person_id = self.db.add_person('User Zero')
        self.assertIsInstance(person_id, int)

        # Attempting to reference a non-existant user_id is an error.
        with self.assertRaisesRegexp(ConsistencyError, '^user does not exist'):
            self.db.add_person('User One', user_id=999)

        # Check that the database also traps this error.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_person('User One', user_id=999,
                               _test_skip_check=True)

        # Create a person which references a valid user_id.
        user_id = self.db.add_user('user1', 'pass1')
        person_id = self.db.add_person('User One', user_id=user_id)
        self.assertIsInstance(person_id, int)

        # Check that we can't have two person records referencing the same
        # user.
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^person already exists with user_id'):
            person_id = self.db.add_person('User Two', user_id=user_id)

        # Check that the database also recognises this error.
        with self.assertRaises(DatabaseIntegrityError):
            person_id = self.db.add_person('User Two', user_id=user_id,
                                           _test_skip_check=True)
