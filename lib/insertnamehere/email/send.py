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
from cStringIO import StringIO
from email.generator import Generator
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
import logging
import socket
from smtplib import SMTP, SMTPException
from time import mktime

from ..config import get_config

logger = logging.getLogger(__name__)


@contextmanager
def quitting(smtp):
    try:
        yield smtp
    finally:
        smtp.quit()


def send_email_message(message):
    """
    Send an email message.

    On success, returns the message identifier.  Returns None on failure.
    """

    config = get_config()
    server = config.get('email', 'server')
    from_ = config.get('email', 'from')

    # Sort recipients into public ("to") and private ("bcc") lists,
    # unless there is only one recipient, in which case there's no
    # need to hide the address.
    recipients_public = []
    recipients_private = []
    single_recipient = len(message.recipients) == 1
    for recipient in message.recipients:
        if single_recipient or recipient.public:
            recipients_public.append(formataddr((recipient.name,
                                                 recipient.address)))
        else:
            recipients_private.append(formataddr((recipient.name,
                                                  recipient.address)))

    identifier = make_msgid('{0}'.format(message.id))

    msg = MIMEText(message.body, 'plain', 'utf-8')

    msg['Subject'] = Header(message.subject)
    msg['Date'] = formatdate(mktime(message.date.timetuple()))
    msg['From'] = Header(from_)
    msg['To'] = Header(', '.join(recipients_public))
    msg['Message-ID'] = identifier

    f = StringIO()
    Generator(f, mangle_from_=False).flatten(msg)

    try:
        with quitting(SMTP(server)) as smtp:
            refusal = smtp.sendmail(
                from_, recipients_public + recipients_private, f.getvalue())

            for (recipient, problem) in refusal.items():
                logger.error('Email message %i refused for %s: %s: %s',
                             message.id, recipient, problem[0], problem[1])

            return identifier

    except SMTPException:
        logger.exception('Email message %i refused for all recipients',
                         message.id)
    except socket.error:
        logger.exception('Email message %i not sent due to failure '
                         'to connect to email server', message.id)

    return None
