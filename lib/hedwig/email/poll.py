# Copyright (C) 2015-2017 East Asian Observatory
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

from ..error import ConsistencyError
from ..type.enum import MessageState
from ..util import get_logger
from .send import send_email_message

logger = get_logger(__name__)


def send_queued_messages(db, dry_run=False):
    """
    Attempts to send any unsent email messages.

    Queries the database for an unsent message.  If messages
    is found, they are sent and then marked as sent in the database.

    Returns the number of messages sent.
    """

    n_sent = 0
    message_ids = set()

    for message in db.search_message(
            state=MessageState.UNSENT,
            oldest_first=True,
            with_thread_identifiers=True,
            with_recipients=True,
            with_recipients_resolved=True,
            with_body=True).values():
        # Double-check we don't get the same message to send twice in one go.
        if message.id in message_ids:
            logger.warning(
                'message with id={} seen more than once', message.id)
            continue
        message_ids.add(message.id)

        logger.debug('Sending message {}', message.id)

        try:
            if not dry_run:
                db.update_message(
                    message.id,
                    state_prev=MessageState.UNSENT,
                    state=MessageState.SENDING,
                    state_is_system=True,
                    timestamp_send=datetime.utcnow())

        except ConsistencyError:
            continue

        try:
            identifier = send_email_message(message, dry_run=dry_run)

            logger.debug('Message {} sent with identifier {}',
                         message.id, identifier)

            try:
                if not dry_run:
                    db.update_message(
                        message.id,
                        state_prev=MessageState.SENDING,
                        state=MessageState.SENT,
                        state_is_system=True,
                        timestamp_sent=datetime.utcnow(),
                        identifier=identifier)

                n_sent += 1

            except ConsistencyError:
                continue

        except:
            logger.exception('Error sending message {}', message.id)

            if not dry_run:
                db.update_message(
                    message.id,
                    state=MessageState.ERROR,
                    state_is_system=True)

    return n_sent
