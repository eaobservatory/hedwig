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

from hedwig.admin.poll import close_completed_call, send_proposal_feedback

from .dummy_db import DBTestCase


class AdminPollTestCase(DBTestCase):
    def test_close_call(self):
        # Initially there should be no calls to close.
        self.assertEqual(close_completed_call(self.db), 0)

    def test_proposal_feedback(self):
        # Initially there should be no feedback to send.
        self.assertEqual(send_proposal_feedback(self.db), 0)
