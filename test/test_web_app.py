# Copyright (C) 2016-2023 East Asian Observatory
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

from hedwig.db.compat import select
from hedwig.db.meta import auth_token

from .base_app import WebAppTestCase


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
            self.assertNotIn('token', sess)

        self.db.add_user('user1', 'pass1')

        rv = self.log_in('user1', 'pass1')
        self.assertInEncoded(
            '<li>You have been logged in.</li>',
            rv.data)

        with self.client.session_transaction() as sess:
            self.assertIn('token', sess)

        rv = self.log_out()
        self.assertInEncoded(
            '<li>You have been logged out.</li>',
            rv.data)

        with self.client.session_transaction() as sess:
            self.assertNotIn('token', sess)

    def test_session_expiry(self):
        dt_curr = datetime.utcnow()
        dt_expect = dt_curr + timedelta(hours=24)

        # At first, should be no 'token' in the session.
        with self.client.session_transaction() as sess:
            self.assertNotIn('token', sess)

        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        self.log_in('user1', 'pass1')

        def _get_expiry():
            with self.db._transaction() as conn:
                return conn.execute(select([
                    auth_token.c.expiry,
                ]).where(auth_token.c.user_id == user_id)).scalar()

        def _set_expiry(expiry):
            with self.db._transaction() as conn:
                conn.execute(auth_token.update().where(
                    auth_token.c.user_id == user_id
                ).values({
                    auth_token.c.expiry: expiry,
                }))

        with self.client.session_transaction() as sess:
            # Should now have a 'token' value.
            self.assertIn('token', sess)

            # Should get a time close to the current time plus 24 hours.
            expiry = _get_expiry()
            self.assertIsInstance(expiry, datetime)
            self.assertLess(
                abs((expiry - dt_expect).total_seconds()), 5)

            # Set date back 5 minutes - should be kept.
            _set_expiry(expiry - timedelta(seconds=300))

        self.client.get('/')

        with self.client.session_transaction() as sess:
            self.assertIn('token', sess)

            # Should get a time close to the 5 minutes before original expiry.
            expiry = _get_expiry()
            self.assertLess(
                abs(abs((expiry - dt_expect).total_seconds()) - 300), 5)

            # Set date back 20 minutes - should reset.
            _set_expiry(expiry - timedelta(seconds=1200))

        self.client.get('/')

        with self.client.session_transaction() as sess:
            self.assertIn('token', sess)

            # The token should have been updated to now have an expiry
            # close to the current time + 24 hours.
            expiry = _get_expiry()
            self.assertLess(
                abs((expiry - dt_expect).total_seconds()), 5)

            # Set date back 1 hour from now - should cause session expiry.
            _set_expiry(dt_curr - timedelta(seconds=3600))

        self.client.get('/')

        with self.client.session_transaction() as sess:
            # Session should have expired.
            self.assertNotIn('token', sess)

        # Database entry for token should have been cleared.
        expiry = _get_expiry()
        self.assertIsNone(expiry)
