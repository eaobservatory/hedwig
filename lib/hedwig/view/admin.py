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

from ..error import NoSuchRecord
from ..web.util import HTTPNotFound
from ..type import MessageState
from .util import with_verified_admin


class AdminView(object):
    def home(self, facilities):
        return {
            'title': 'Site Administration',
            'facilities': facilities.values(),
        }

    @with_verified_admin
    def message_list(self, db, args):
        states = MessageState.get_options()
        messages = db.search_message()

        return {
            'title': 'Message List',
            'messages': [x._replace(state=states[x.state])
                         for x in messages.values()],
        }

    @with_verified_admin
    def message_view(self, db, message_id):
        try:
            message = db.get_message(message_id)
        except NoSuchRecord:
            raise HTTPNotFound('Message not found')

        return {
            'title': 'Message: {}'.format(message.subject),
            'message': message,
        }
