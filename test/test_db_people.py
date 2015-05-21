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

from datetime import datetime, timedelta

from insertnamehere.db.meta import invitation, reset_token
from insertnamehere.error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord, UserError
from insertnamehere.type import Email, EmailCollection, \
    Institution, InstitutionInfo, Person, ResultCollection
from .dummy_db import DBTestCase


class DBPeopleTest(DBTestCase):
    def test_user(self):
        # Check that we can create a user and get an integer user_id.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        user_name = self.db.get_user_name(user_id)
        self.assertEqual(user_name, 'user1')

        with self.assertRaises(NoSuchRecord):
            self.db.get_user_name(999)

        user_id_fetched = self.db.get_user_id('user1')
        self.assertEqual(user_id_fetched, user_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_user_id('no-user')

        # Attempting to re-create the same user is an error.
        with self.assertRaises(UserError):
            self.db.add_user('user1', 'pass1')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_user('user1', 'pass1', _test_skip_check=True)

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

        # Test changing a password.
        self.assertEqual(self.db.authenticate_user('user3', 'pass3'), user_id)
        self.db.update_user_password(user_id, '3ssap')
        self.assertIsNone(self.db.authenticate_user('user3', 'pass3'))
        self.assertEqual(self.db.authenticate_user('user3', '3ssap'), user_id)

        # Test changing a user name
        self.db.update_user_name(user_id, '3resu')
        self.assertEqual(self.db.get_user_name(user_id), '3resu')
        with self.assertRaisesRegexp(ConsistencyError, '^user does not exist'):
            self.db.update_user_name(999, 'newname')
        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            self.db.update_user_name(999, 'newname', _test_skip_check=True)
        with self.assertRaisesRegexp(UserError, 'already exists\.$'):
            self.db.update_user_name(user_id, 'user1')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.update_user_name(user_id, 'user1', _test_skip_check=True)
        with self.assertRaisesRegexp(UserError, 'blank'):
            self.db.update_user_name(user_id, '')

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

        # Try getting a person by user_id.
        result = self.db.get_person(person_id=None, user_id=user_id)
        self.assertIsInstance(result, Person)
        self.assertEqual(result.id, person_id)

        # And make sure get_person requires at least one non-None parameter.
        with self.assertRaisesRegexp(Error, 'specified'):
            self.db.get_person(person_id=None, user_id=None)

    def test_email(self):
        # Check that we can add an email address.
        person_id = self.db.add_person('User One')
        email_id = self.db.add_email(person_id, 'one@users.net')

        self.assertIsInstance(email_id, int)

        # Test person_id existance checking.
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^person does not exist'):
            email_id = self.db.add_email(999, 'zero@users.net')

        # Test that the database check for the same thing works.
        with self.assertRaises(DatabaseIntegrityError):
            email_id = self.db.add_email(999, 'zero@users.net',
                                         _test_skip_check=True)

        # Test that the database prevents duplicates for the same person.
        with self.assertRaises(DatabaseIntegrityError):
            email_id = self.db.add_email(person_id, 'one@users.net')

        # But we can have the same address for multiple person records.
        person_id = self.db.add_person('User One Duplicate')
        email_id = self.db.add_email(person_id, 'one@users.net')
        self.assertIsInstance(email_id, int)

        # Add a second address and try a search.
        email_id2 = self.db.add_email(person_id, 'one@another.name')
        result = self.db.search_email(person_id=person_id)

        self.assertIsInstance(result, EmailCollection)
        self.assertEqual(len(result), 2)

        for ((result_id, email), address, expected_id) in zip(
                result.items(),
                ['one@users.net', 'one@another.name'],
                [email_id, email_id2]):
            self.assertIsInstance(email, Email)
            self.assertEqual(email.id, result_id)
            self.assertEqual(email.id, expected_id)
            self.assertEqual(email.person_id, person_id)
            self.assertEqual(email.address, address)
            self.assertIs(email.primary, False)
            self.assertIs(email.verified, False)
            self.assertIs(email.public, False)

        # Try searching for people by email address.
        # TODO: check these results more thoroughly.
        result = self.db.search_person(email_address='one@users.net')
        self.assertEqual(len(result), 2)
        result = self.db.search_person(email_address='one@another.name')
        self.assertEqual(len(result), 1)
        result = self.db.search_person(email_address='one@another.name',
                                       registered=True)
        self.assertEqual(len(result), 0)

    def test_sync_person_email(self):
        # Set up email addresses.
        person_1 = self.db.add_person('Person One')
        person_2 = self.db.add_person('Person Two')

        email_1a = self.db.add_email(person_1, '1a@e', True, False, False)
        email_1b = self.db.add_email(person_1, '1b@e', False, False, False)
        email_1c = self.db.add_email(person_1, '1c@e', False, False, False)
        email_2a = self.db.add_email(person_2, '2a@e', True, False, False)
        email_2b = self.db.add_email(person_2, '2b@e', False, False, False)

        values_1 = EmailCollection()
        values_1[1] = Email(email_1a, None, '1a@e', True, False, False)
        values_1[2] = Email(email_1b, None, '1b@e', False, False, False)
        values_1[3] = Email(email_1c, None, '1c@e', False, False, False)
        values_2 = EmailCollection()
        values_2[1] = Email(email_2a, None, '2a@e', True, False, False)
        values_2[2] = Email(email_2b, None, '2b@e', False, False, False)

        # Check the values match to start with.
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Updating with these same values should do nothing.
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (0, 0, 0))
        self.assertEqual(
            self.db.sync_person_email(person_2, values_2), (0, 0, 0))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Updating a value.
        values_1[2] = values_1[2]._replace(address='2b@eeeee', public=True)
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (0, 1, 0))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)

        # Insert a value.
        values_1[4] = Email(
            email_2b + 1, person_1, '1d@e', False, False, False)
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (1, 0, 0))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)

        # Delete a value.
        del values_1[3]
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (0, 0, 1))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)

        # Check Person Two's email records weren't modified in the process.
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Do multiple update for Person Two.
        values_2[1] = Email(email_2a, None, '2a@e', True, False, True)
        values_2[2] = Email(email_2b + 2, None, '2c@e', False, False, False)
        self.assertEqual(
            self.db.sync_person_email(person_2, values_2), (1, 1, 1))
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Finally check the validation of the record collection.
        values_2[2] = values_2[2]._replace(primary=True)
        with self.assertRaisesRegexp(UserError, 'more than one primary'):
            self.db.sync_person_email(person_2, values_2)

    def _compare_email_records(self, got, expect):
        self.assertEqual(len(got), len(expect))
        for record in expect.values():
            self.assertIn(record.id, got)

            got_record = got[record.id]

            self.assertEqual(got_record.address, record.address)
            self.assertEqual(got_record.primary, record.primary)
            self.assertEqual(got_record.verified, record.verified)
            self.assertEqual(got_record.public, record.public)

    def test_search_person(self):
        # Set up some test records.
        user_1 = self.db.add_user('user1', 'pass1')
        user_2 = self.db.add_user('user2', 'pass2')
        user_3 = self.db.add_user('user3', 'pass3')

        person_1 = self.db.add_person('person1', user_id=user_1)
        person_2 = self.db.add_person('person2', user_id=user_2)
        person_3 = self.db.add_person('person3', user_id=user_3)

        email_1a = self.db.add_email(person_1, '1@email.a')
        email_2a = self.db.add_email(person_2, '2@email.a')
        email_2b = self.db.add_email(person_2, '2@email.b')
        email_2c = self.db.add_email(person_2, 'shared@email')
        email_3a = self.db.add_email(person_3, '3@email.a')
        email_3b = self.db.add_email(person_3, 'shared@email')

        # Check all the records were created successfully.
        for id_ in (user_1, user_2, person_1, person_2, person_3,
                    email_1a, email_2a, email_2b, email_2c,
                    email_3a, email_3b):
            self.assertIsInstance(id_, int)

        # Try searching by user ID.
        result = self.db.search_person(user_id=user_1).keys()
        self.assertEqual(set(result), set((person_1,)))

        result = self.db.search_person(user_id=user_2).keys()
        self.assertEqual(set(result), set((person_2,)))

        result = self.db.search_person(user_id=999).keys()
        self.assertFalse(result)

        # Try searching by email address.
        result = self.db.search_person(email_address='1@email.a').keys()
        self.assertEqual(set(result), set((person_1,)))

        result = self.db.search_person(email_address='2@email.a').keys()
        self.assertEqual(set(result), set((person_2,)))

        result = self.db.search_person(email_address='2@email.b').keys()
        self.assertEqual(set(result), set((person_2,)))

        result = self.db.search_person(email_address='shared@email').keys()
        self.assertEqual(set(result), set((person_2, person_3)))

        result = self.db.search_person(email_address='no@email').keys()
        self.assertFalse(result)

        # Try constraining both user name and user_id.
        result = self.db.search_person(
            user_id=user_2, email_address='shared@email').keys()
        self.assertEqual(set(result), set((person_2,)))
        result = self.db.search_person(
            user_id=user_3, email_address='shared@email').keys()
        self.assertEqual(set(result), set((person_3,)))
        result = self.db.search_person(
            user_id=999, email_address='shared@email').keys()
        self.assertFalse(result)
        result = self.db.search_person(
            user_id=user_3, email_address='no@email').keys()
        self.assertFalse(result)

    def test_institution(self):
        # Try getting a non-existent institution record.
        with self.assertRaisesRegexp(NoSuchRecord,
                                     '^institution does not exist'):
            institution = self.db.get_institution(999)

        # Check that we can add an institution.
        institution_id = self.db.add_institution('Institution One')

        self.assertIsInstance(institution_id, int)

        # Try retrieving the institution.
        institution = self.db.get_institution(institution_id)
        self.assertIsInstance(institution, Institution)

        # Get a list of institutions.
        institution_id2 = self.db.add_institution('Institution Two')
        result = self.db.list_institution()
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 2)

        for ((row_id, institution), name, expected_id) in zip(
                result.items(),
                ['Institution One', 'Institution Two'],
                [institution_id, institution_id2]):
            self.assertIsInstance(institution, InstitutionInfo)
            self.assertEqual(institution.id, row_id)
            self.assertEqual(institution.id, expected_id)
            self.assertEqual(institution.name, name)

        # Try updating an institution.
        with self.assertRaisesRegexp(Error,
                                     '^no institution updates specified'):
            self.db.update_institution(institution_id)
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^institution does not exist'):
            self.db.update_institution(999, '...')
        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            self.db.update_institution(999, '...', _test_skip_check=True)

        self.db.update_institution(institution_id, 'Renamed Institution One')
        institution = self.db.get_institution(institution_id)
        self.assertIsInstance(institution, Institution)
        self.assertEqual(institution.name, 'Renamed Institution One')

    def test_person(self):
        # Try getting a non-existent person record.
        with self.assertRaisesRegexp(NoSuchRecord, '^person does not exist'):
            person = self.db.get_person(999)

        # Create a test person record.
        person_id = self.db.add_person('Person One')
        self.assertIsInstance(person_id, int)

        # Check starting state of the record.
        person = self.db.get_person(person_id)
        self.assertIsInstance(person, Person)
        self.assertIsNone(person.institution_id)

        # Create a test institution record.
        institution_id = self.db.add_institution('Institution One')
        self.assertIsInstance(institution_id, int)

        # Update the person to reference the new institution.
        self.db.update_person(person_id, institution_id=institution_id)

        # Get and inspect the updated record.
        person = self.db.get_person(person_id)
        self.assertIsInstance(person, Person)
        self.assertEqual(person.institution_id, institution_id)

        # Check that errors are trapped.
        with self.assertRaisesRegexp(Error, '^no person updates specified'):
            self.db.update_person(person_id)
        with self.assertRaisesRegexp(ConsistencyError, '^person does not'):
            self.db.update_person(999, institution_id=institution_id)
        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            self.db.update_person(999, institution_id=institution_id,
                                  _test_skip_check=True)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.update_person(person_id, institution_id=999)

    def test_password_reset_token(self):
        # Create a user record.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        # Try making a reset token.
        token = self.db.get_password_reset_token(user_id)
        self.assertIsInstance(token, str)
        self.assertRegexpMatches(token, '^[0-9a-f]{32}$')

        # Using a bad token should do nothing.
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(b'not a valid token')

        # Using the token should return this user id.
        token_user_id = self.db.use_password_reset_token(token)
        self.assertEqual(token_user_id, user_id)

        # Using the token again should return None because the
        # token should have been deleted.
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(token)

        # Issue two more tokens: the older should be removed automatically.
        token1 = self.db.get_password_reset_token(user_id)
        token2 = self.db.get_password_reset_token(user_id)
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(token1)
        token_user_id = self.db.use_password_reset_token(token2)
        self.assertEqual(token_user_id, user_id)

        # Create a token and artificially age it by putting the expiry
        # date in the past.  It should then not work.
        token = self.db.get_password_reset_token(user_id)
        with self.db._transaction() as conn:
            result = conn.execute(reset_token.update().where(
                reset_token.c.token == token
            ).values({
                reset_token.c.expiry: datetime.utcnow() - timedelta(hours=1),
            }))

            self.assertEqual(result.rowcount, 1)
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(token)

    def test_invitation_new_user(self):
        # Create a person record.
        person_id = self.db.add_person('Person One')
        self.assertIsInstance(person_id, int)

        # Check we can generate a token of the expected format.
        token = self.db.add_invitation(person_id)
        self.assertIsInstance(token, str)
        self.assertRegexpMatches(token, '^[0-9a-f]{32}$')

        user_id = self.db.add_user('user1', 'pass1')
        with self.assertRaisesRegexp(NoSuchRecord, 'expired or non-existant'):
            self.db.use_invitation(b'not a valid token', user_id=user_id)

        # Try check that the user exists.
        with self.assertRaisesRegexp(ConsistencyError,
                                     'user does not exist'):
            self.db.use_invitation(token, user_id=999)

        # Try using the token: user_id is None before but set afterwards.
        person = self.db.get_person(person_id=person_id)
        self.assertIsNone(person.user_id)
        self.db.use_invitation(token, user_id=user_id)
        person = self.db.get_person(person_id=person_id)
        self.assertEqual(person.user_id, user_id)

        # The token should no longer exist.
        with self.assertRaisesRegexp(NoSuchRecord, 'expired or non-existant'):
            self.db.use_invitation(token, user_id=user_id)

        # Check error trapping.
        with self.assertRaisesRegexp(ConsistencyError,
                                     'person does not exist'):
            self.db.add_invitation(999)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_invitation(999, _test_skip_check=True)
        with self.assertRaisesRegexp(ConsistencyError,
                                     'person is already registered'):
            self.db.add_invitation(person_id)

        # Try artificially aging a token.
        person_id = self.db.add_person('Person Two')
        token = self.db.add_invitation(person_id)
        with self.db._transaction() as conn:
            result = conn.execute(invitation.update().where(
                invitation.c.token == token
            ).values({
                invitation.c.expiry: datetime.utcnow() - timedelta(hours=1),
            }))
            self.assertEqual(result.rowcount, 1)
        with self.assertRaises(NoSuchRecord):
            self.db.use_invitation(token, user_id=user_id)

        # Try using for a person who subsequently somehow became registered.
        token = self.db.add_invitation(person_id)
        user_id_2 = self.db.add_user('user2', 'pass2')
        user_id_3 = self.db.add_user('user3', 'pass3', person_id=person_id)
        with self.assertRaisesRegexp(ConsistencyError,
                                     'no rows matched setting new user_id'):
            self.db.use_invitation(token, user_id=user_id_2)

    def test_invitation_user_admin(self):
        # Create an administrative person record.
        person_id = self.db.add_person('Administrator')
        self.assertIsInstance(person_id, int)
        self.db.update_person(person_id, admin=True, _test_skip_check=True)

        # Try to create an invitation to register as that person: should
        # fail unless the check is disabled.
        with self.assertRaisesRegexp(UserError, 'administrative privileges'):
            self.db.add_invitation(person_id)
        token = self.db.add_invitation(person_id, _test_skip_check=True)

        # Try to accept the invitation to register as that person.
        user_id = self.db.add_user('user1', 'pass1')
        with self.assertRaisesRegexp(ConsistencyError, 'no rows matched'):
            self.db.use_invitation(token, user_id=user_id)
        person = self.db.get_person(person_id=person_id)
        self.assertIsNone(person.user_id)

    def test_invitation_replace_person(self):
        # Create test person records.
        person_id_1 = self.db.add_person('Person 1')
        self.db.add_email(person_id_1, '1@email')

        person_id_2 = self.db.add_person('Person 2')
        self.db.add_email(person_id_2, '2@email')

        person_id_new = self.db.add_person('Person New')
        self.db.add_email(person_id_new, 'new@email')

        # Create a proposal with 2 members.
        facility_id = self.db.ensure_facility('test')
        semester_id = self.db.add_semester(facility_id, 'test')
        queue_id = self.db.add_queue(facility_id, 'test')
        call_id = self.db.add_call(semester_id, queue_id)
        proposal_id = self.db.add_proposal(call_id, person_id_1, 'Proposal 1')
        self.db.add_member(proposal_id, person_id_2)

        # Issue invitation token for one of the members.
        token = self.db.add_invitation(person_id_2)
        self.assertIsInstance(token, str)
        self.assertRegexpMatches(token, '^[0-9a-f]{32}$')

        # Try check that the person exists.
        with self.assertRaisesRegexp(ConsistencyError,
                                     'person does not exist'):
            self.db.use_invitation(token, new_person_id=999)

        # Accept the invitation with the existing new person record.
        self.db.use_invitation(token, new_person_id=person_id_new)

        # The "temporary" person record should have gone.
        with self.assertRaises(NoSuchRecord):
            self.db.get_person(person_id=person_id_2)

        # The proposal members should by the original author and new person.
        proposal = self.db.get_proposal(proposal_id, with_members=True)
        self.assertEqual(map(lambda x: x.person_id, proposal.members.values()),
                         [person_id_1, person_id_new])

        # The invitation should have been removed.
        person_id_new_2 = self.db.add_person('Person New 2')
        with self.assertRaisesRegexp(NoSuchRecord, 'expired or non-existant'):
            self.db.use_invitation(token, new_person_id=person_id_new_2)
