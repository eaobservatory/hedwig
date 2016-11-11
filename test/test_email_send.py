# Copyright (C) 2016 East Asian Observatory
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

from hedwig.email.send import MIMETextFlowed, quitting

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
