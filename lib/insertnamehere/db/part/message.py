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

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_

from ...error import ConsistencyError
from ...type import Message, MessageRecipient, ResultCollection
from ..meta import email, message, message_recipient, person


class MessagePart(object):
    def add_message(self, subject, body, person_ids, _test_skip_check=False):
        if not _test_skip_check:
            if ((not isinstance(person_ids, set)) and
                    (len(person_ids) != len(set(person_ids)))):
                raise ConsistencyError('duplicate person_id for new message')

        with self._transaction() as conn:
            result = conn.execute(message.insert().values({
                message.c.date: datetime.utcnow(),
                message.c.subject: subject,
                message.c.body: body,
            }))

            message_id = result.inserted_primary_key[0]

            for person_id in person_ids:
                conn.execute(message_recipient.insert().values({
                    message_recipient.c.message_id: message_id,
                    message_recipient.c.person_id: person_id,
                }))

        return message_id

    def get_unsent_message(self, mark_sending=False):
        """
        Return the first unsent message, if there is one, or None otherwise.

        Optionally, mark the message as being sent by writing the current
        timestamp into its "timestamp_send" column.  This raises
        ConsistencyError if the column become non-null in the meantime.
        """

        with self._transaction() as conn:
            result = conn.execute(message.select().where(and_(
                message.c.timestamp_send.is_(None),
                message.c.timestamp_sent.is_(None)
            )).order_by(
                message.c.id.asc()
            ).limit(1)).first()

            if result is None:
                return None

            message_id = result['id']

            recipients = []

            for row in conn.execute(select([
                    person.c.name, email.c.address, email.c.public
                    ]).select_from(
                        message_recipient.join(person).join(email)
                    ).where(and_(
                        message_recipient.c.message_id == message_id,
                        email.c.primary))):
                recipients.append(MessageRecipient(**row))

            if mark_sending:
                mark_result = conn.execute(message.update().where(and_(
                    message.c.id == message_id,
                    message.c.timestamp_send.is_(None),
                )).values({
                    message.c.timestamp_send: datetime.utcnow(),
                }))

                if mark_result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched marking message as sending')

        return Message(recipients=recipients, **result)

    def mark_message_sent(self, message_id, identifier,
                          _test_skip_check=False):
        """
        Marks the given message as sent.

        The "identifier" should be the email's "Message-ID" header.
        """

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, message, message_id):
                raise ConsistencyError(
                    'message does not exist with id={0}', message_id)

            result = conn.execute(message.update().where(and_(
                message.c.id == message_id,
                message.c.timestamp_sent.is_(None)
            )).values({
                message.c.timestamp_sent: datetime.utcnow(),
                message.c.identifier: identifier,
            }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched marking message as sent')

    def search_message(self):
        """
        Searches for messages.

        Currently this method is just for testing, but is expected to
        be extended to provide for an administrative interface.
        """

        stmt = select([
            message.c.id,
            message.c.date,
            message.c.subject,
            message.c.timestamp_send,
            message.c.timestamp_sent,
            message.c.identifier,
        ])

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(message.c.id.asc())):
                ans[row['id']] = Message(body=None, recipients=None, **row)

        return ans
