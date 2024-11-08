# Copyright (C) 2016-2024 East Asian Observatory
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

from codecs import ascii_decode
from datetime import datetime
import re

from hedwig.compat import byte_type, python_version
from hedwig.email.send import quitting, _prepare_email_message, \
    unwrap_email_text
from hedwig.type.enum import MessageThreadType
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

        if not python_version < 3:
            self.skipTest('test only for Python 2')

        from hedwig.email.send import MIMETextMaybeFlowed, MIMETextFlowed

        msg = MIMETextFlowed('test message')
        self.assertEqual(sorted(msg['Content-type'].split('; ')),
                         ['charset="utf-8"', 'format="flowed"', 'text/plain'])

        msg = MIMETextMaybeFlowed('test message')
        self.assertEqual(sorted(msg['Content-type'].split('; ')),
                         ['charset="utf-8"', 'text/plain'])

    def test_text_unwrap(self):
        """Test the `unwrap_email_text` function."""

        self.assertEqual(
            unwrap_email_text('a \na \na\nb \nb \nb'),
            'a a a\nb b b')

        self.assertEqual(
            unwrap_email_text('a \na\nb \nb\nc \nc\nd \nd\n'),
            'a a\nb b\nc c\nd d')

        self.assertEqual(
            unwrap_email_text('a\nb \nb \nb \nb \nb \nb \nb\nc'),
            'a\nb b b b b b b\nc')

    def test_address_header(self):
        """Test the `_prepare_address_header` function."""

        if not python_version < 3:
            self.skipTest('test only for Python 2')

        from hedwig.email.send import _prepare_address_header

        printable = re.compile(r'^[ !-~]*$')

        def _header_valid(header):
            self.assertIsInstance(header, byte_type)
            # Should raise UnicodeDecodeError if header is not ASCII:
            decoded = ascii_decode(header)[0]
            self.assertTrue(
                printable.match(decoded),
                'header \'{}\' is printable'.format(decoded))

        header = _prepare_address_header((('name', 'email@address'),))
        _header_valid(header)
        self.assertEqual(header, b'"name" <email@address>')

        header = _prepare_address_header((('N \\ " E', 'email@address'),))
        _header_valid(header)
        self.assertEqual(header, b'"N \\\\ \\" E" <email@address>')

        header = _prepare_address_header((('n\u00e1zev', 'email@address'),))
        _header_valid(header)
        self.assertEqual(header, b'=?utf-8?q?n=C3=A1zev?= <email@address>')

        header = _prepare_address_header((
            ('1', 'a@b'), ('2', 'c@d'), ('3', 'e@f'),
        ))
        _header_valid(header)
        self.assertEqual(header, b'"1" <a@b>, "2" <c@d>, "3" <e@f>')

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
                thread_identifiers=['test-ref-1', 'test-ref-2'],
                thread_type=MessageThreadType.PROPOSAL_STATUS,
                thread_id=5678),
            from_='Hedwig Pr\u00fcfung <hedwig@test>',
            identifier='test-msg-1')

        self.assertEqual(id_, 'test-msg-1')

        self.assertIsInstance(recipients, list)
        self.assertEqual(recipients, ['one@test', 'two@test'])

        self.assertIsInstance(msg, byte_type)
        msg_lines = msg.split(b'\n')

        # Remove trailing blank line (if present) to aid comparison.
        if msg_lines[-1] == b'':
            msg_lines.pop()

        # Define expected email message, but with alternatives for
        # several lines where they can be encoded differently.
        msg_expect = [
            (b'Content-Type: text/plain; charset="utf-8"; format="flowed"',
             b'Content-Type: text/plain; format="flowed"; charset="utf-8"',
             b'Content-Type: text/plain; charset="utf-8"'),
            b'MIME-Version: 1.0',
            (b'Content-Transfer-Encoding: base64',
             b'Content-Transfer-Encoding: quoted-printable'),
            (b'Subject: =?utf-8?q?Message_exp=C3=A9rimental?=',
             b'Subject: Message =?utf-8?q?exp=C3=A9rimental?='),
            b'Date: Wed, 01 Apr 2015 00:00:00 +0000',
            (b'From: =?utf-8?q?Hedwig_Pr=C3=BCfung?= <hedwig@test>',
             b'From: Hedwig =?utf-8?q?Pr=C3=BCfung?= <hedwig@test>'),
            (b'To: =?utf-8?q?Persoon_=C3=A9=C3=A9n?= <one@test>',
             b'To: Persoon =?utf-8?b?w6nDqW4=?= <one@test>',
             b'To: =?utf-8?b?UGVyc29vbiDDqcOpbg==?= <one@test>'),
            b'Message-ID: test-msg-1',
            b'In-Reply-To: test-ref-2',
            b'References: test-ref-1 test-ref-2',
            b'X-Hedwig-ID: 1234',
            b'X-Hedwig-Thread: prop_stat 5678',
            b'',
            (b'Qydlc3QgdW4gbWVzc2FnZSBleHDDqXJpbWVudGFsLg==',
             b'Qydlc3QgdW4gbWVzc2FnZSBleHDDqXJpbWVudGFsLgo=',
             b'C\'est un message exp=C3=A9rimental.'),
        ]

        # Python 3 seems to put Content-Transfer-Encoding first.
        if not python_version < 3:
            if msg_lines[0].startswith(b'Content-Transfer-Encoding'):
                msg_expect.insert(0, msg_expect.pop(2))
            else:
                msg_expect.insert(1, msg_expect.pop(2))

        self.assertEqual(len(msg_lines), len(msg_expect))

        for (line, expect) in zip(msg_lines, msg_expect):
            if isinstance(expect, tuple):
                self.assertIn(line, expect)
            else:
                self.assertEqual(line, expect)
