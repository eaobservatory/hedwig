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
from ..type import MessageState
from ..web.util import ErrorPage, HTTPNotFound, url_for
from .util import with_verified_admin


class AdminView(object):
    def home(self, facilities):
        return {
            'title': 'Site Administration',
            'facilities': facilities.values(),
        }

    @with_verified_admin
    def message_list(self, db, args):
        num_per_page = 100
        url_params = {}
        kwargs = {'limit': num_per_page}

        person = None
        person_id = args.get('person_id')
        if person_id is not None:
            person_id = int(person_id)
            kwargs['person_id'] = person_id
            url_params['person_id'] = person_id
            try:
                person = db.get_person(person_id)
            except:
                raise ErrorPage(
                    'Message list requested for non-existent person.')

        state = args.get('state')
        if not state:
            state = None
        if state is not None:
            state = int(state)
            kwargs['state'] = state
            url_params['state'] = state

        id_lt = args.get('id_lt')
        if id_lt is not None:
            id_lt = int(id_lt)
            kwargs['message_id_lt'] = id_lt

        states = MessageState.get_options()
        messages = db.search_message(**kwargs)

        # Prepare pagination URLs.  Give only "first" and "next" links as
        # we can generate these with simple SQL constructs (id < x, limit).
        target_first = None
        target_next = None

        if id_lt is not None:
            target_first = url_for('.message_list', **url_params)

        # Guess that there are more messages if we have as many as the limit
        # specified.  (Might not be true if the number of messages is divisible
        # by the number per page.)
        if len(messages) >= num_per_page:
            target_next = url_for('.message_list', id_lt=min(messages.keys()),
                                  **url_params)

        return {
            'title': ('Message List' if person is None
                      else '{}: Messages'.format(person.name)),
            'messages': [x._replace(state=states[x.state])
                         for x in messages.values()],
            'target_first': target_first,
            'target_next': target_next,
            'form_params': {k: v for (k, v) in url_params.items()
                            if k != 'state'},
            'current_state': state,
            'states': states,
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
