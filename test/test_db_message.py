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

from datetime import datetime

from hedwig.error import ConsistencyError, DatabaseIntegrityError
from hedwig.type import Message, MessageRecipient, ResultCollection
from .dummy_db import DBTestCase


class DBMessageTest(DBTestCase):
    def test_basic_message(self):
        # Check null results.
        self.assertIsNone(self.db.get_unsent_message())
        messages = self.db.search_message()
        self.assertFalse(messages)

        # Create test message.
        person_1 = self.db.add_person('Person One')
        self.db.add_email(person_1, '1@a', primary=True, public=True)

        with self.assertRaisesRegexp(ConsistencyError, '^duplicate person_id'):
            message_id = self.db.add_message('test', 'test message',
                                             [person_1, person_1])

        with self.assertRaises(DatabaseIntegrityError):
            message_id = self.db.add_message('test', 'test message',
                                             [person_1, person_1],
                                             _test_skip_check=True)

        with self.assertRaises(DatabaseIntegrityError):
            message_id = self.db.add_message('test', 'test message',
                                             [1999999])

        message_id = self.db.add_message('test', 'test message', [person_1])
        self.assertIsInstance(message_id, int)

        # Test "search_message" method.
        messages = self.db.search_message()
        self.assertIsInstance(messages, ResultCollection)
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertIsInstance(message, Message)

        self.assertEqual(message.id, message_id)
        self.assertEqual(message.subject, 'test')
        self.assertIsNone(message.body)
        self.assertIsNone(message.timestamp_send)
        self.assertIsNone(message.timestamp_sent)
        self.assertIsNone(message.identifier)
        self.assertIsNone(message.recipients)

        # Test "get_unsent_message" method.
        message = self.db.get_unsent_message(mark_sending=True)
        self.assertIsInstance(message, Message)
        self.assertEqual(message.id, message_id)
        self.assertEqual(message.subject, 'test')
        self.assertEqual(message.body, 'test message')
        self.assertIsNone(message.timestamp_send)
        self.assertIsNone(message.timestamp_sent)
        self.assertIsNone(message.identifier)
        self.assertIsNotNone(message.recipients)
        self.assertEqual(len(message.recipients), 1)
        recipient = message.recipients[0]
        self.assertIsInstance(recipient, MessageRecipient)
        self.assertEqual(recipient.name, 'Person One')
        self.assertEqual(recipient.address, '1@a')
        self.assertTrue(recipient.public)

        self.assertIsNotNone(
            self.db.search_message()[message_id].timestamp_send)

        self.assertIsNone(self.db.get_unsent_message())

        # Test "mark_message_sent" method.
        self.db.mark_message_sent(message_id, '<1@localhost>')

        self.assertIsNone(self.db.get_unsent_message())

        messages = self.db.search_message()
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertEqual(message.id, message_id)
        self.assertEqual(message.subject, 'test')
        self.assertIsNone(message.body)
        self.assertIsInstance(message.timestamp_send, datetime)
        self.assertIsInstance(message.timestamp_sent, datetime)
        self.assertEqual(message.identifier, '<1@localhost>')
        self.assertIsNone(message.recipients)

        with self.assertRaisesRegexp(ConsistencyError, '^message does not ex'):
            self.db.mark_message_sent(1999999, '<2@localhost>')

        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            self.db.mark_message_sent(1999999, '<2@localhost>',
                                      _test_skip_check=True)

    def test_multiple_message(self):
        # Create some person records with multiple email addresses.
        person_1 = self.db.add_person('Person One')
        self.db.add_email(person_1, '1@a', primary=False, public=True)
        self.db.add_email(person_1, '1@b', primary=True, public=True)
        self.db.add_email(person_1, '1@c', primary=False, public=True)

        person_2 = self.db.add_person('Person Two')
        self.db.add_email(person_2, '2@a', primary=True, public=False)
        self.db.add_email(person_2, '2@b', primary=False, public=True)
        self.db.add_email(person_2, '2@c', primary=False, public=True)

        person_3 = self.db.add_person('Person Three')
        self.db.add_email(person_3, '3@a', primary=False, public=False)
        self.db.add_email(person_3, '3@b', primary=False, public=True)
        self.db.add_email(person_3, '3@c', primary=True, public=True)

        person_4 = self.db.add_person('Person Four')
        self.db.add_email(person_4, '4@a', primary=False, public=False)
        self.db.add_email(person_4, '4@b', primary=True, public=False)
        self.db.add_email(person_4, '4@c', primary=False, public=True)

        # Create two test messages.
        message_12 = self.db.add_message('test', 'test message',
                                         [person_1, person_2])
        message_34 = self.db.add_message('test', 'test message',
                                         [person_3, person_4])

        self.assertIsInstance(message_12, int)
        self.assertIsInstance(message_34, int)
        self.assertNotEqual(message_12, message_34)

        # Check that each message has the correct set of recipients.
        message = self.db.get_unsent_message(mark_sending=True)
        self.assertEqual(message.id, message_12)
        self.assertEqual(set(message.recipients), set((
            MessageRecipient(person_1, 'Person One', '1@b', True),
            MessageRecipient(person_2, 'Person Two', '2@a', False),
        )))

        message = self.db.get_unsent_message(mark_sending=True)
        self.assertEqual(message.id, message_34)
        self.assertEqual(set(message.recipients), set((
            MessageRecipient(person_3, 'Person Three', '3@c', True),
            MessageRecipient(person_4, 'Person Four', '4@b', False),
        )))

    def test_explicit_email(self):
        # Create some person records with multiple email addresses.
        person_1 = self.db.add_person('Person One')
        self.db.add_email(person_1, '1@a', primary=False, public=True)
        self.db.add_email(person_1, '1@b', primary=True, public=True)
        self.db.add_email(person_1, '1@c', primary=False, public=True)

        person_2 = self.db.add_person('Person Two')
        self.db.add_email(person_2, '2@a', primary=True, public=False)
        self.db.add_email(person_2, '2@b', primary=False, public=True)
        self.db.add_email(person_2, '2@c', primary=False, public=True)

        person_3 = self.db.add_person('Person Three')
        self.db.add_email(person_3, '3@a', primary=True, public=False)
        self.db.add_email(person_3, '3@b', primary=False, public=True)
        self.db.add_email(person_3, '3@c', primary=False, public=False)

        # Create test message, giving specific email addresses.
        message_id = self.db.add_message('test', 'test message',
                                         [person_1, person_2, person_3],
                                         ['1@c', '2@b', '3@c'])

        self.assertIsInstance(message_id, int)

        # Check that the message has the correct set of addresses.
        message = self.db.get_unsent_message(mark_sending=True)
        self.assertEqual(message.id, message_id)
        self.assertEqual(set(message.recipients), set((
            MessageRecipient(person_1, 'Person One', '1@c', True),
            MessageRecipient(person_2, 'Person Two', '2@b', True),
            MessageRecipient(person_3, 'Person Three', '3@c', False),
        )))

        # Check handling of an email address which isn't in the email table.
        # (This can happen if an address is changed after an email is already
        # inserted into the database with an explicit address.)
        message_id = self.db.add_message('test', 'test message',
                                         [person_1], ['1@d'])
        message = self.db.get_unsent_message(mark_sending=True)
        self.assertEqual(message.id, message_id)
        self.assertEqual(message.recipients, [
            MessageRecipient(person_1, 'Person One', '1@d', False),
        ])
