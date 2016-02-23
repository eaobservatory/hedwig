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
from ..type import GroupType, ProposalState, ReviewerRole
from ..web.util import session, HTTPForbidden

Authorization = namedtuple('Authorization', ('view', 'edit'))

no = Authorization(False, False)
yes = Authorization(True, True)
view_only = Authorization(view=True, edit=False)


def for_call_review(db, call):
    """
    Determine the current user's authorization regarding the general
    review of proposals for a given call.

    (Authorization to view the proposals and the individual reviews
    is controlled by the more specific for_proposal and for_review
    methods below.)
    """

    if 'user_id' not in session or 'person' not in session:
        return no
    elif session.get('is_admin', False) and can_be_admin(db):
        return yes

    person_id = session['person']['id']

    # Give full access to review coordinators and
    # view access to committee members.
    group_members = db.search_group_member(
        queue_id=call.queue_id, person_id=person_id)

    for group_type in GroupType.review_coord_groups():
        if group_members.values_by_group_type(group_type):
            return yes

    if group_members.values_by_group_type(GroupType.CTTEE):
        return view_only

    return no


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
                return yes
            else:
                auth = auth._replace(view=True)

        # Look for reviews for which this person is the reviewer and allow
        # access to review coordinators.
        queue_ids = set()
        for group_member in db.search_group_member(
                person_id=session['person']['id'],
                group_type=GroupType.COORD).values():
            queue_ids.add(group_member.queue_id)

        if db.search_reviewer(person_id=person.id, queue_id=list(queue_ids)):
            return yes

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

    auth = view_only

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
    if db.search_group_member(
            person_id=session['person']['id'],
            group_type=GroupType.private_moc_groups(),
            facility_id=facility_id).values():
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
        pass

    if ((proposal.reviewers is not None) and
            (proposal.state == ProposalState.REVIEW)):
        # Give access to people assigned as reviewers of the proposal.
        try:
            proposal.reviewers.get_person(session['person']['id'])
            return auth._replace(view=True)
        except KeyError:
            pass

    if ProposalState.is_submitted(proposal.state):
        # Give access to review groups with access to view all proposals.
        if db.search_group_member(
                queue_id=proposal.queue_id,
                group_type=GroupType.view_all_groups(),
                person_id=session['person']['id']):
            return auth._replace(view=True)

    return auth


def for_review(db, reviewer, proposal):
    """
    Determine the current user's authorization regarding this review.

    "reviewer" can be set to "None" to skip reviewer-specific authorization.
    (Access will then be granted based only on proposal membership,
    administrative access and committee membership.)
    """

    if 'user_id' not in session or 'person' not in session:
        return no

    person_id = session['person']['id']
    is_under_review = (proposal.state == ProposalState.REVIEW)

    # Forbid access if the person is a member of the proposal.
    try:
        proposal.members.get_person(person_id)
        return no
    except KeyError:
        pass

    # Allow full access to the reviewer if the proposal is still under review.
    # (But skip this test if doing a non-reviewer-specific check.)
    if reviewer is not None:
        if ((person_id == reviewer.person_id) and is_under_review):
            return yes

    # Allow administrators to view, with edit too if still under review.
    # (This is to allow the administrator to adjust review ratings during
    # the committee meeting.)
    if session.get('is_admin', False) and can_be_admin(db):
        return Authorization(view=True, edit=is_under_review)

    # Give view access to committee members.
    if db.search_group_member(
            queue_id=proposal.queue_id,
            group_type=GroupType.CTTEE,
            person_id=person_id):
        return view_only

    return no


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


def can_add_review_roles(db, proposal):
    """
    Determine for which reviewer roles a person can add a review to
    a proposal.

    If the proposal's state is not REVIEW then an empty list is returned.
    """

    if proposal.state != ProposalState.REVIEW:
        return []

    person_id = session['person']['id']

    # If the person is a member of the proposal, they can't add any reviews.
    try:
        proposal.members.get_person(person_id=person_id)
        return []
    except KeyError:
        pass

    roles = []

    # Determine whether the user can add a committee "other" review -- they
    # should be a committee member who doesn't already have a committee
    # review.
    try:
        proposal.reviewers.get_person(person_id=person_id,
                                      roles=ReviewerRole.get_cttee_roles())
    except KeyError:
        if db.search_group_member(
                queue_id=proposal.queue_id,
                group_type=GroupType.CTTEE,
                person_id=person_id):
            roles.append(ReviewerRole.CTTEE_OTHER)

    # Determine whether the user can add a "feedback" review -- they should be
    # the committee primary reviewer (or have administrative privileges) but
    # there should not already be a review of this role.
    if not proposal.reviewers.person_id_by_role(ReviewerRole.FEEDBACK):
        try:
            if not (session.get('is_admin', False) and can_be_admin(db)):
                proposal.reviewers.get_person(
                    person_id=person_id, roles=(ReviewerRole.CTTEE_PRIMARY,))
            roles.append(ReviewerRole.FEEDBACK)
        except KeyError:
            pass

    return roles
