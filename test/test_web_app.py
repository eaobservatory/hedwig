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

from .dummy_app import WebAppTestCase


class BasicWebAppTestCase(WebAppTestCase):
    def test_home_page(self):
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'text/html')
        self.assertInEncoded(
            '<h1>' + self.config.get('application', 'name') + '</h1>',
            rv.data)

    def test_log_in(self):
        rv = self.log_in('user1', 'pass1')
        self.assertInEncoded(
            'User name or password not recognised.',
            rv.data)

        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

        self.db.add_user('user1', 'pass1')

        rv = self.log_in('user1', 'pass1')
        self.assertInEncoded(
            '<li>You have been logged in.</li>',
            rv.data)

        with self.client.session_transaction() as sess:
            self.assertIn('user_id', sess)

        rv = self.log_out()
        self.assertInEncoded(
            '<li>You have been logged out.</li>',
            rv.data)

        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
