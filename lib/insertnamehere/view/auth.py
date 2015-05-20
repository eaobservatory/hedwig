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

from collections import namedtuple

from ..web.util import session, HTTPForbidden

Authorization = namedtuple('Authorization', ('view', 'edit'))

no = Authorization(False, False)
yes = Authorization(True, True)


def for_person(db, person):
    """
    Determine the current user's authorization regarding this
    profile.
    """

    if 'user_id' not in session:
        return no
    elif session.get('is_admin', False) and can_be_admin(db):
        return yes

    is_user = person.user_id == session['user_id']

    return Authorization(view=is_user or person.public, edit=is_user)


def for_institution(db, institution):
    """
    Determine the current user's authorization regarding this
    institution.
    """

    if 'user_id' not in session:
        return no
    elif session.get('is_admin', False) and can_be_admin(db):
        return yes

    if 'person' in session:
        user_institution_id = session['person']['institution_id']
    else:
        user_institution_id = None

    return Authorization(view=True, edit=(user_institution_id is not None and
                         user_institution_id == institution.id))


def can_be_admin(db):
    """
    Check whether the user is permitted to take administrative
    privileges.
    """

    try:
        person = db.get_person(person_id=None, user_id=session['user_id'])
        return person.admin
    except NoSuchRecord:
        raise HTTPForbidden('Could not verify administrative access.')
