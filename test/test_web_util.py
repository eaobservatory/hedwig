# Copyright (C) 2016-2019 East Asian Observatory
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

from hedwig.error import UserError
from hedwig.type.simple import DateAndTime
from hedwig.web.util import \
    ascii_safe, format_datetime, parse_datetime, \
    url_add_args, url_relative

from .compat import TestCase


class WebUtilTestCase(TestCase):
    def test_ascii_safe(self):
        self.assertEqual(ascii_safe('abcdef.pdf'), 'abcdef.pdf')
        self.assertEqual(ascii_safe(
            'cr\xe8me br\xfbl\xe9e.pdf'), 'cr_me br_l_e.pdf')

    def test_format_datetime(self):
        dt = datetime(2016, 4, 1, 15, 0, 0)

        d_and_t = format_datetime(None)

        self.assertIsInstance(d_and_t, DateAndTime)
        self.assertEqual(d_and_t.date, '')
        self.assertEqual(d_and_t.time, '')

        d_and_t = format_datetime(dt)

        self.assertIsInstance(d_and_t, DateAndTime)
        self.assertEqual(d_and_t.date, '2016-04-01')
        self.assertEqual(d_and_t.time, '15:00')

    def test_parse_datetime(self):
        with self.assertRaisesRegex(UserError, '^Could not parse'):
            parse_datetime(DateAndTime('2000-01-01', 'XX:YY'))

        dt = parse_datetime(DateAndTime('2020-05-04', '17:55'))
        self.assertIsInstance(dt, datetime)
        self.assertEqual(dt.year, 2020)
        self.assertEqual(dt.month, 5)
        self.assertEqual(dt.day, 4)
        self.assertEqual(dt.hour, 17)
        self.assertEqual(dt.minute, 55)

    def test_url_manipulation(self):
        base_url = 'https://proposals.obs/facil/page?aaa=xxx'

        self.assertEqual(url_relative(base_url),
                         '/facil/page?aaa=xxx')

        self.assertEqual(url_add_args(base_url, bbb='yyy'),
                         'https://proposals.obs/facil/page?aaa=xxx&bbb=yyy')
