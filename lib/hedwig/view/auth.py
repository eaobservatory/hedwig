# Copyright (C) 2015-2016 East Asian Observatory
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

from ..db.util import memoized
from ..error import NoSuchRecord
from ..type.enum import GroupType, ProposalState
from ..web.util import session, HTTPForbidden

Authorization = namedtuple('Authorization', ('view', 'edit'))

no = Authorization(False, False)
yes = Authorization(True, True)
view_only = Authorization(view=True, edit=False)

AuthorizationWithRating = namedtuple(
    'AuthorizationWithRating', Authorization._fields + ('view_rating',))


def for_call_review(db, call, auth_cache=None):
    """
    Determine the current user's authorization regarding the general
    review of proposals for a given call.

    (Authorization to view the proposals and the individual reviews
    is controlled by the more specific for_proposal and for_review
    methods below.)

    When making multiple calls to this function, an auth_cache dictionary
    can be provided.  This function can then use this to cache some
    information which it fetches from the database.
    """

    if 'user_id' not in session or 'person' not in session:
        return no
    elif session.get('is_admin', False) and can_be_admin(db):
        return yes

    person_id = session['person']['id']

    # Give full access to review coordinators and
    # view access to committee members.
    group_members = _get_group_membership(
        auth_cache, db, call.queue_id, person_id)

    if any(group_members.values_by_group_type(group_type)
            for group_type in GroupType.review_coord_groups()):
        return yes

    if any(group_members.values_by_group_type(group_type)
            for group_type in GroupType.review_view_groups()):
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

        if queue_ids:
            if db.search_reviewer(role_class=None,
                                  person_id=person.id,
                                  queue_id=list(queue_ids)):
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

    Currently only "view" authorization is considered.
    """

    if 'user_id' not in session or 'person' not in session:
        return no

    # If user is an administrator, allow access.
    # Probably not worthwhile to re-validate administrative access here.
    # NOTE: If this function is updated to also control editing MOCs
    # then administrative access should be verified.
    if session.get('is_admin', False):
        return view_only

    # Otherwise check groups for the given facility.
    # TODO: consider caching this information in the session object?
    if db.search_group_member(
            person_id=session['person']['id'],
            group_type=GroupType.private_moc_groups(),
            facility_id=facility_id).values():
        return view_only

    return no


def for_proposal(role_class, db, proposal, auth_cache=None):
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

    if proposal.reviewers is not None:
        # Give access to people assigned as reviewers of the proposal.
        for reviewer_role in proposal.reviewers.role_by_person_id(
                session['person']['id']):
            if proposal.state in role_class.get_editable_states(reviewer_role):
                return auth._replace(view=True)

    if ProposalState.is_submitted(proposal.state):
        # Give access to review groups with access to view all proposals.
        group_members = _get_group_membership(
            auth_cache, db, proposal.queue_id, session['person']['id'])

        if any(group_members.values_by_group_type(group_type)
                for group_type in GroupType.view_all_groups()):
            return auth._replace(view=True)

    return auth


def for_proposal_feedback(role_class, db, proposal):
    """
    Determine the current user's authorization regarding general feedback
    for a proposal.

    This may include, but is not limited to, the feedback review.  For more
    specific access to that review, use the for_review function.
    This function currently only allows view access.
    """

    if 'user_id' not in session or 'person' not in session:
        return no

    # Only allow access to the feedback information when the review is
    # complete.
    if not ProposalState.is_reviewed(proposal.state):
        return no

    # Allow administrators to view.
    if session.get('is_admin', False) and can_be_admin(db):
        return view_only

    # Allow proposal members to view.
    if proposal.members.has_person(session['person']['id']):
        return view_only

    # Otherwise deny access.
    return no


def for_review(role_class, db, reviewer, proposal, auth_cache=None):
    """
    Determine the current user's authorization regarding this review.

    "reviewer" can be set to "None" to skip reviewer-specific authorization.
    (Access will then be granted based only on proposal membership,
    administrative access and committee membership.)

    When making multiple calls to this function, an auth_cache dictionary
    can be provided.  This function can then use this to cache some
    information which it fetches from the database.

    :return AuthorizationWithRating: including field indicating whether
        the ratings can be viewed.
    """

    if 'user_id' not in session or 'person' not in session:
        return AuthorizationWithRating(*no, view_rating=False)

    person_id = session['person']['id']

    # Forbid access if the person is a member of the proposal.
    if proposal.members.has_person(person_id):
        return AuthorizationWithRating(*no, view_rating=False)

    # Determine whether the proposal is in a state where this review is
    # editable.  If we have a specific reviewer, check that role's states.
    if (reviewer is not None):
        if proposal.state in role_class.get_editable_states(reviewer.role):
            # Allow full access to the reviewer while the review is editable.
            if person_id == reviewer.person_id:
                return AuthorizationWithRating(*yes, view_rating=True)

            # Special case: if this is the feedback review, allow all reviewers
            # with suitable roles to edit it.
            if reviewer.role == role_class.FEEDBACK:
                if db.search_reviewer(role_class=role_class,
                                      proposal_id=reviewer.proposal_id,
                                      person_id=person_id,
                                      role=role_class.get_feedback_roles()):
                    return AuthorizationWithRating(*yes, view_rating=True)

            review_is_editable = True

        else:
            review_is_editable = False

        rating_is_viewable = (
            proposal.state
            in role_class.get_rating_viewable_states(reviewer.role))

    else:
        # If doing a non-reviewer-specific check, consider all
        # review states.
        review_is_editable = (proposal.state in ProposalState.review_states())
        rating_is_viewable = False

    # Allow administrators and review coordinators to view, with edit too if
    # still under review.  (This is to allow them to adjust review ratings
    # during the committee meeting.)
    if session.get('is_admin', False) and can_be_admin(db):
        return AuthorizationWithRating(
            view=True, edit=review_is_editable, view_rating=rating_is_viewable)

    group_members = _get_group_membership(
        auth_cache, db, proposal.queue_id, person_id)

    if any(group_members.values_by_group_type(group_type)
           for group_type in GroupType.review_coord_groups()):
        return AuthorizationWithRating(
            view=True, edit=review_is_editable, view_rating=rating_is_viewable)

    # Give view access to committee members.
    if any(group_members.values_by_group_type(group_type)
           for group_type in GroupType.review_view_groups()):
        return AuthorizationWithRating(
            view=True, edit=False, view_rating=rating_is_viewable)

    return AuthorizationWithRating(*no, view_rating=False)


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


def can_add_review_roles(role_class, db, proposal):
    """
    Determine for which reviewer roles a person can add a review to
    a proposal.

    If no reviews can be added then an empty list is returned.
    """

    person_id = session['person']['id']

    # If the person is a member of the proposal, they can't add any reviews.
    if proposal.members.has_person(person_id=person_id):
        return []

    roles = []

    # Determine whether the user can add a committee "other" review -- they
    # should be a committee member who doesn't already have a committee
    # review.
    if proposal.state in role_class.get_editable_states(
            role_class.CTTEE_OTHER):
        if not proposal.reviewers.has_person(
                person_id=person_id, roles=role_class.get_cttee_roles()):
            if db.search_group_member(
                    queue_id=proposal.queue_id,
                    group_type=GroupType.CTTEE,
                    person_id=person_id):
                roles.append(role_class.CTTEE_OTHER)

    # Determine whether the user can add a "feedback" review -- they should be
    # a reviewer in a suitable role (or have administrative privileges) but
    # there should not already be a review of this role.
    if proposal.state in role_class.get_editable_states(
            role_class.FEEDBACK):
        if not proposal.reviewers.has_role(role_class.FEEDBACK):
            if ((session.get('is_admin', False) and can_be_admin(db))
                    or proposal.reviewers.has_person(
                        person_id=person_id,
                        roles=role_class.get_feedback_roles())):
                roles.append(role_class.FEEDBACK)

    return roles


@memoized
def _get_group_membership(db, queue_id, person_id):
    return db.search_group_member(queue_id=queue_id, person_id=person_id)
