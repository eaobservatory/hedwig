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
from itertools import izip_longest

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, case, column
from sqlalchemy.sql.functions import coalesce

from ...error import ConsistencyError, FormattedError, \
    NoSuchRecord, MultipleRecords
from ...type.collection import ResultCollection
from ...type.enum import MessageState
from ...type.simple import Message, MessageRecipient
from ..meta import email, message, message_recipient, person


class MessagePart(object):
    def add_message(self, subject, body, person_ids, email_addresses=[],
                    _test_skip_check=False):
        """
        Add a message to the database.

        "email_addresses" can normally be left empty, but if it is necessary to
        send to a particular address (rather than the person's primary address)
        then it can be a list with email addresses in the same order as the
        person_ids list.
        """

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

            for (person_id, email_address) in izip_longest(person_ids,
                                                           email_addresses):
                conn.execute(message_recipient.insert().values({
                    message_recipient.c.message_id: message_id,
                    message_recipient.c.person_id: person_id,
                    message_recipient.c.email_address: email_address,
                }))

        return message_id

    def get_message(self, message_id):
        """
        Retrieve a message from the database.
        """

        with self._transaction() as conn:
            recipients = []

            for row in conn.execute(select([
                    message_recipient.c.person_id,
                    person.c.name,
                    message_recipient.c.email_address.label('address'),
                    ]).select_from(message_recipient.join(person)).where(
                        message_recipient.c.message_id == message_id)):
                recipients.append(MessageRecipient(public=None, **row))

            row = conn.execute(message.select().where(
                message.c.id == message_id).limit(1)).first()

            if row is None:
                raise NoSuchRecord('message not found with id {}', message_id)

            ans = Message(recipients=recipients, state=None, **row)

        return ans

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

            # Find the recipients of the message: perform an outer join
            # with the email table in case the address is not there -- in that
            # case assume the address is not public.
            for row in conn.execute(select([
                    message_recipient.c.person_id,
                    person.c.name,
                    coalesce(message_recipient.c.email_address,
                             email.c.address).label('address'),
                    coalesce(email.c.public, False).label('public'),
                    ]).select_from(
                        message_recipient.join(person).outerjoin(
                            email,
                            and_(person.c.id == email.c.person_id, case([(
                                message_recipient.c.email_address.isnot(None),
                                message_recipient.c.email_address ==
                                email.c.address)],
                                else_=email.c.primary)
                            ))
                    ).where(
                        message_recipient.c.message_id == message_id)):
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

        return Message(recipients=recipients, state=None, **result)

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
                    'message does not exist with id={}', message_id)

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

    def search_message(self, person_id=None, state=None, message_id_lt=None,
                       limit=None):
        """
        Searches for messages.

        The selection of messages to be returned can be controlled with the
        optional keyword arguments.
        """

        stmt = select([
            message.c.id,
            message.c.date,
            message.c.subject,
            message.c.timestamp_send,
            message.c.timestamp_sent,
            message.c.identifier,
            case([
                (and_(message.c.timestamp_send.is_(None),
                      message.c.timestamp_sent.is_(None)),
                 MessageState.UNSENT),
                (message.c.timestamp_sent.is_(None),
                 MessageState.SENDING),
            ], else_=MessageState.SENT).label('state'),
        ])

        if person_id is not None:
            stmt = stmt.select_from(message.join(message_recipient)).where(
                message_recipient.c.person_id == person_id)

        if state is not None:
            stmt = stmt.where(column('state') == state)

        if message_id_lt is not None:
            stmt = stmt.where(message.c.id < message_id_lt)

        if limit is not None:
            stmt = stmt.limit(limit)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(message.c.id.desc())):
                ans[row['id']] = Message(body=None, recipients=None, **row)

        return ans
