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

from datetime import datetime
import json

from flask import Markup

from hedwig.type import AttachmentState
from hedwig.web.template_util import Counter

from .dummy_app import WebAppTestCase


class TemplateUtilTestCase(WebAppTestCase):
    def test_global_counter(self):
        cc = self.app.jinja_env.globals['create_counter']

        c = cc(10)
        self.assertIsInstance(c, Counter)
        self.assertEqual(c.value, 10)

        self.assertEqual(c(), 10)
        self.assertEqual(c(), 11)
        self.assertEqual(c(), 12)

        self.assertEqual(c.value, 13)

    def test_filter_count_true(self):
        f = self.app.jinja_env.filters['count_true']

        self.assertEqual(f([]), 0)
        self.assertEqual(f([False, False, False, False]), 0)
        self.assertEqual(f([False, True,  False, False]), 1)
        self.assertEqual(f([False, True,  False, True]),  2)
        self.assertEqual(f([True,  True,  False, True]),  3)
        self.assertEqual(f([True,  True,  True,  True]),  4)

    def test_filter_fmt(self):
        f = self.app.jinja_env.filters['fmt']

        self.assertEqual(f(None, '<{}>'), '')
        self.assertEqual(f(40, '<{}>'), '<40>')
        self.assertEqual(f((30, 40), '<{}, {}>'), '<30, 40>')

    def test_filter_format_datetime(self):
        fd = self.app.jinja_env.filters['format_date']
        ft = self.app.jinja_env.filters['format_time']

        dt = datetime(2016, 4, 1, 15, 0, 0)

        self.assertEqual(fd(dt), '2016-04-01')
        self.assertEqual(ft(dt), '15:00')

    def test_filter_format_hours_hms(self):
        f = self.app.jinja_env.filters['format_hours_hms']

        self.assertEqual(f(0.5), '0:30:00')

        self.assertEqual(f(3.755), '3:45:18')

    def test_filter_json(self):
        f = self.app.jinja_env.filters['json']

        d = {'a': 'b'}
        j = f(d)
        self.assertIsInstance(j, str)
        self.assertEqual(json.loads(j), d)

        # Test usage of "extend" parameter".
        self.assertEqual(json.loads(f({'c': 'd'}, Markup(j))),
                         {'a': 'b', 'c': 'd'})

    def test_filter_abbr(self):
        f = self.app.jinja_env.filters['abbr']

        self.assertEqual(f(None), '')

        self.assertEqual(f('1234567890', 20), '1234567890')

        self.assertEqual(f('1234567890', 5),
                         '<abbr title="1234567890">12345&hellip;</abbr>')

    def test_test_attachment(self):
        t = self.app.jinja_env.tests['attachment_new']
        self.assertTrue(t(AttachmentState.NEW))
        self.assertFalse(t(AttachmentState.ERROR))
        self.assertFalse(t(AttachmentState.READY))

        t = self.app.jinja_env.tests['attachment_ready']
        self.assertFalse(t(AttachmentState.NEW))
        self.assertFalse(t(AttachmentState.ERROR))
        self.assertTrue(t(AttachmentState.READY))

        t = self.app.jinja_env.tests['attachment_error']
        self.assertFalse(t(AttachmentState.NEW))
        self.assertTrue(t(AttachmentState.ERROR))
        self.assertFalse(t(AttachmentState.READY))

    def test_filter_format_text(self):
        f = self.app.jinja_env.filters['format_text']

        self.assertEqual(f('Hello'), '<p>Hello</p>')
