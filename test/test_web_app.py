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

from datetime import datetime, timedelta

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

    def test_session_expiry(self):
        dt_curr = datetime.utcnow()

        # At first, should be no 'date_set' in the session.
        with self.client.session_transaction() as sess:
            self.assertNotIn('date_set', sess)
            self.assertNotIn('user_id', sess)

        self.db.add_user('user1', 'pass1')
        self.log_in('user1', 'pass1')

        with self.client.session_transaction() as sess:
            # Should now have a 'date_set' value.
            self.assertIn('date_set', sess)
            self.assertIn('user_id', sess)

            # Should get a time close to the current time.
            self.assertIsInstance(sess['date_set'], datetime)
            self.assertLess(
                abs((sess['date_set'] - dt_curr).total_seconds()), 5)

            # Set date back 5 minutes - should be kept.
            sess['date_set'] = dt_curr - timedelta(seconds=300)

        self.client.get('/')

        with self.client.session_transaction() as sess:
            self.assertIn('date_set', sess)
            self.assertIn('user_id', sess)

            # Should get a time close to the 5 minutes before the current time.
            self.assertLess(
                abs(abs((sess['date_set'] - dt_curr).total_seconds()) - 300),
                5)

            # Set date back 20 minutes - should reset.
            sess['date_set'] = dt_curr - timedelta(seconds=1200)

        self.client.get('/')

        with self.client.session_transaction() as sess:
            self.assertIn('date_set', sess)
            self.assertIn('user_id', sess)

            # The session should have been updated to now have a time
            # close to the current time.
            self.assertLess(
                abs((sess['date_set'] - dt_curr).total_seconds()), 5)

            # Set date back 10 hours - should cause session expiry.
            sess['date_set'] = dt_curr - timedelta(seconds=36000)

        self.client.get('/')

        with self.client.session_transaction() as sess:
            # Session should have expired.
            self.assertNotIn('date_set', sess)
            self.assertNotIn('user_id', sess)
