# Copyright (C) 2016-2017 East Asian Observatory
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

from hedwig.compat import byte_type
from hedwig.email.send import MIMETextFlowed, quitting, _prepare_email_message
from hedwig.type.collection import MessageRecipientCollection
from hedwig.type.simple import Message, MessageRecipient
from hedwig.type.util import null_tuple

from .dummy_config import DummyConfigTestCase


class DummyQuittable(object):
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


class EmailSendTestCase(DummyConfigTestCase):
    def test_quitting(self):
        """Test the `quitting` context manager."""

        quittable = DummyQuittable()
        self.assertFalse(quittable.quit_called)

        with quitting(quittable):
            self.assertFalse(quittable.quit_called)

        self.assertTrue(quittable.quit_called)

    def test_text_flowed(self):
        """Test the `MIMETextFlowed` class."""

        msg = MIMETextFlowed('test message')
        self.assertEqual(sorted(msg['Content-type'].split('; ')),
                         ['charset="utf-8"', 'format="flowed"', 'text/plain'])

    def test_prepare_message(self):
        """Test the `_prepare_email_message` function."""

        (id_, msg, recipients) = _prepare_email_message(
            message=null_tuple(Message)._replace(
                id=1234,
                date=datetime(2015, 4, 1, 0, 0, 0),
                subject='Message exp\u00e9rimental',
                body='C\'est un message exp\u00e9rimental.',
                recipients=MessageRecipientCollection((
                    (1, MessageRecipient(
                        None, 101, 'one@test', 'Persoon \u00e9\u00e9n', True)),
                    (2, MessageRecipient(
                        None, 102, 'two@test', 'Persoon twee', False)),
                )),
                thread_identifiers=['test-ref-1', 'test-ref-2'])
            from_='Hedwig Pr\u00fcfung <hedwig@test>',
            identifier='test-msg-1')

        self.assertEqual(id_, 'test-msg-1')

        self.assertIsInstance(recipients, list)
        self.assertEqual(recipients, ['one@test', 'two@test'])

        self.assertIsInstance(msg, byte_type)
        msg_lines = msg.split(b'\n')

        # Define expected email message, but with alternatives for
        # several lines where they can be encoded differently.
        msg_expect = [
            (b'Content-Type: text/plain; charset="utf-8"; format="flowed"',
             b'Content-Type: text/plain; format="flowed"; charset="utf-8"'),
            b'MIME-Version: 1.0',
            b'Content-Transfer-Encoding: base64',
            b'Subject: =?utf-8?q?Message_exp=C3=A9rimental?=',
            b'Date: Wed, 01 Apr 2015 00:00:00 +0000',
            b'From: =?utf-8?q?Hedwig_Pr=C3=BCfung_=3Chedwig=40test=3E?=',
            (b'To: =?utf-8?b?UGVyc29vbiDDqcOpbiA8b25lQHRlc3Q+?=',
             b'To: =?utf-8?b?UGVyc29vbiDDqcOpbg==?= <one@test>'),
            b'Message-ID: test-msg-1',
            b'In-Reply-To: test-ref-2',
            b'References: test-ref-1 test-ref-2',
            b'',
            b'Qydlc3QgdW4gbWVzc2FnZSBleHDDqXJpbWVudGFsLg==',
            b'']

        self.assertEqual(len(msg_lines), len(msg_expect))

        for (line, expect) in zip(msg_lines, msg_expect):
            if isinstance(expect, tuple):
                self.assertIn(line, expect)
            else:
                self.assertEqual(line, expect)
