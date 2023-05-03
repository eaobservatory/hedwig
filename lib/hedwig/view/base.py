# Copyright (C) 2015-2023 East Asian Observatory
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

from ..error import UserError
from ..type.misc import ErrorCatcher
from ..web.util import ErrorPage
from .util import int_or_none


class ViewMember(object):
    """
    Mix-in for view classes dealing with membership.
    """

    def _read_member_form(self, form):
        """
        Read member information from the given form, returning
        a dictionary.
        """

        info = ErrorCatcher(dict(
            person_id=None, name='', title=None, email='', is_link=None))

        with info.catch_() as member:
            if form is not None:
                if 'person_id' in form:
                    member['person_id'] = int_or_none(form['person_id'])
                if 'person_title' in form:
                    member['title'] = int_or_none(form['person_title'])
                member['name'] = form.get('name', '').strip()
                member['email'] = form.get('email', '').strip()

                if 'submit_link' in form:
                    member['is_link'] = True

                    if member['person_id'] is None:
                        raise UserError(
                            'No-one was selected from the directory.')

                elif 'submit_invite' in form:
                    member['is_link'] = False

                    if not member['name']:
                        raise UserError('Please enter the person\'s name.')
                    if not member['email']:
                        raise UserError('Please enter an email address.')

                else:
                    raise ErrorPage('Unknown action.')

        return info
