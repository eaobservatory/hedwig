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

from ..error import NoSuchRecord
from ..type import GroupType, ProposalState
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

    if person.user_id is not None:
        # This is a registered user: allow access based on the "public"
        # flag and only allow them to edit their profile.

        is_user = person.user_id == session['user_id']

        return Authorization(view=is_user or person.public, edit=is_user)

    else:
        # Look for proposals of which this person is a member and allow
        # access based on the proposal settings.
        auth = no

        for member in db.search_member(person_id=session['person']['id'],
                                       co_member_person_id=person.id).values():
            if member.editor:
                auth = auth._replace(view=True, edit=True)
            else:
                auth = auth._replace(view=True)

        return auth


def for_institution(db, institution):
    """
    Determine the current user's authorization regarding this
    institution.
    """

    if 'user_id' not in session:
        return no
    elif session.get('is_admin', False) and can_be_admin(db):
        return yes

    auth = Authorization(view=True, edit=False)

    if 'person' not in session:
        return auth

    if institution.id == session['person']['institution_id']:
        # If this is the person's institution, allow them to edit it.

        auth = auth._replace(edit=True)

    else:
        # Is the person an editor for a proposal with a representative of this
        # institution?  In that case allow them to edit it unless it has
        # registered representatives.

        if (db.search_member(person_id=session['person']['id'],
                             editor=True,
                             co_member_institution_id=institution.id) and
                not db.search_person(registered=True,
                                     institution_id=institution.id)):
            auth = auth._replace(edit=True)

    return auth


def for_private_moc(db, facility_id):
    """
    Determine whether the current user can view/search private MOCs.
    """

    if 'user_id' not in session or 'person' not in session:
        return False

    # If user is an administrator, allow access.
    # Probably not worthwhile to re-validate administrative access here.
    if session.get('is_admin', False):
        return True

    # Otherwise check groups for the given facility.
    # TODO: consider caching this information in the session object?
    for group_member in db.search_group_member(
            person_id=session['person']['id'],
            facility_id=facility_id).values():
        if GroupType.get_info(group_member.group_type).private_moc:
            return True

    return False


def for_proposal(db, proposal):
    """
    Determine the current user's authorization regarding this proposal.
    """

    if 'user_id' not in session or 'person' not in session:
        return no

    auth = no

    if session.get('is_admin', False) and can_be_admin(db):
        auth = auth._replace(view=True)

    try:
        member = proposal.members.get_person(session['person']['id'])
        return Authorization(
            view=True,
            edit=(member.editor and ProposalState.can_edit(proposal.state)))
    except KeyError:
        return auth


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
