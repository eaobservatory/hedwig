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
from ..type.collection import ProposalCollection, ReviewerCollection
from ..type.enum import GroupType, ProposalState, ReviewState
from ..type.simple import Reviewer
from ..type.util import null_tuple
from ..web.util import session, HTTPError, HTTPForbidden

Authorization = namedtuple('Authorization', ('view', 'edit'))

no = Authorization(False, False)
yes = Authorization(True, True)
view_only = Authorization(view=True, edit=False)
edit_only = Authorization(view=False, edit=True)

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
    elif (session.get('is_admin', False)
            and can_be_admin(db, auth_cache=auth_cache)):
        return yes

    person_id = session['person']['id']

    # Give full access to review coordinators and
    # view access to committee members.
    group_members = _get_group_membership(auth_cache, db, person_id)

    if group_members.has_entry(
            queue_id=call.queue_id,
            group_type=GroupType.review_coord_groups()):
        return yes

    if group_members.has_entry(
            queue_id=call.queue_id,
            group_type=GroupType.review_view_groups()):
        return view_only

    return no


def for_person(db, person, auth_cache=None):
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

        for member in db.search_member(
                person_id=session['person']['id'],
                co_member_person_id=person.id,
                co_member_proposal_state=ProposalState.editable_states()
                ).values():
            if member.editor:
                return yes
            else:
                auth = auth._replace(view=True)

        # Look for reviews for which this person is the reviewer and allow
        # access to review coordinators.
        group_members = _get_group_membership(
            auth_cache, db, session['person']['id'])

        queue_ids = set((
            x.queue_id
            for x in group_members.values_by_group_type(
                GroupType.review_coord_groups())))

        if queue_ids:
            if db.search_reviewer(
                    person_id=person.id, queue_id=queue_ids,
                    proposal_state=ProposalState.review_states()):
                return yes

        return auth


def for_institution(db, institution, auth_cache=None):
    """
    Determine the current user's authorization regarding this
    institution.
    """

    if 'user_id' not in session:
        return no
    elif session.get('is_admin', False) and can_be_admin(db):
        return yes

    if 'person' not in session:
        return view_only

    if institution.id == session['person']['institution_id']:
        # If this is the person's institution, allow them to edit it.

        return yes

    else:
        # Allow for special access to edit the institution unless it has
        # registered representatives.

        if not db.search_person(registered=True,
                                institution_id=institution.id):
            # Is the person an editor for a proposal with a representative of
            # this institution?
            if db.search_member(
                    person_id=session['person']['id'],
                    editor=True,
                    co_member_institution_id=institution.id,
                    co_member_proposal_state=ProposalState.editable_states()):

                return yes

            # Look for reviews for which a representative of the institution
            # is the reviewer and allow access to review coordinators.
            group_members = _get_group_membership(
                auth_cache, db, session['person']['id'])

            queue_ids = set((
                x.queue_id
                for x in group_members.values_by_group_type(
                    GroupType.review_coord_groups())))

            if queue_ids:
                if db.search_reviewer(
                        institution_id=institution.id, queue_id=queue_ids,
                        proposal_state=ProposalState.review_states()):
                    return yes

    return view_only


def for_private_moc(db, facility_id, auth_cache=None):
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
    group_members = _get_group_membership(
        auth_cache, db, session['person']['id'])

    if group_members.has_entry(
            group_type=GroupType.private_moc_groups(),
            facility_id=facility_id):
        return view_only

    return no


def for_proposal(role_class, db, proposal, auth_cache=None):
    """
    Determine the current user's authorization regarding this proposal.
    """

    if 'user_id' not in session or 'person' not in session:
        return no

    auth = no

    if (session.get('is_admin', False)
            and can_be_admin(db, auth_cache=auth_cache)):
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
            auth_cache, db, session['person']['id'])

        if group_members.has_entry(
                queue_id=proposal.queue_id,
                group_type=GroupType.view_all_groups()):
            return auth._replace(view=True)

    return auth


def for_proposal_decision(db, proposal, call=None, auth_cache=None):
    """
    Determine the current user's authorization regarding the
    review committee decision.

    Currently only "edit" authorization is considered.

    The call object can optionally be provided.  Otherwise the call is
    looked up based on the proposal's call identifier.
    """

    # Deny access if the state is anything other than final review.
    if proposal.state != ProposalState.FINAL_REVIEW:
        return no

    # Deny access if the decision and feedback have already been approved.
    if proposal.decision_ready:
        return no

    if call is None:
        call = _get_call(auth_cache, db, proposal.call_id)
        if call is None:
            raise HTTPError('The corresponding call was not found.')

    # Assume that the user has permission to edit the decision of they
    # can edit the call.  (I.e. they are review coordinator or admin.)
    if for_call_review(db, call, auth_cache=auth_cache).edit:
        return edit_only

    return no


def for_proposal_feedback(role_class, db, proposal, auth_cache=None):
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
    if (session.get('is_admin', False)
            and can_be_admin(db, auth_cache=auth_cache)):
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
    Otherwise this can be either a `Reviewer` or `ReviewerInfo` object.

    When making multiple calls to this function, an auth_cache dictionary
    can be provided.  This function can then use this to cache some
    information which it fetches from the database.

    If the `proposal` has a non-`None` reviewers attribute, then this
    may be used in determining authorization in cases where it may
    depend on other roles.  (The only example so far is allowing
    reviewers in "feedback roles" to edit the "feedback" review.)
    **This means that if some reviewers are attached, they all must be.**

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
            # NOTE: if the proposal has its reviewers attached, use them rather
            # than making a new database search.
            if reviewer.role == role_class.FEEDBACK:
                if proposal.reviewers is None:
                    if db.search_reviewer(
                            proposal_id=reviewer.proposal_id,
                            person_id=person_id,
                            role=role_class.get_feedback_roles()):
                        return AuthorizationWithRating(*yes, view_rating=True)
                else:
                    if proposal.reviewers.has_person(
                            person_id, roles=role_class.get_feedback_roles()):
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
    if (session.get('is_admin', False)
            and can_be_admin(db, auth_cache=auth_cache)):
        return AuthorizationWithRating(
            view=True, edit=review_is_editable, view_rating=rating_is_viewable)

    group_members = _get_group_membership(auth_cache, db, person_id)

    if group_members.has_entry(
            queue_id=proposal.queue_id,
            group_type=GroupType.review_coord_groups()):
        return AuthorizationWithRating(
            view=True, edit=review_is_editable, view_rating=rating_is_viewable)

    # Give view access to committee members.
    if group_members.has_entry(
            queue_id=proposal.queue_id,
            group_type=GroupType.review_view_groups()):
        return AuthorizationWithRating(
            view=True, edit=False, view_rating=rating_is_viewable)

    return AuthorizationWithRating(*no, view_rating=False)


def can_be_admin(db, auth_cache=None):
    """
    Check whether the user is permitted to take administrative
    privileges.
    """

    person = _get_user_profile(auth_cache, db, session['user_id'])
    if person is None:
        raise HTTPForbidden('Could not verify administrative access.')

    return person.admin


def can_add_review_roles(role_class, db, proposal, include_indirect=True,
                         auth_cache=None):
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

    group_members = _get_group_membership(auth_cache, db, person_id)

    # Determine whether the user can add a committee "other" review -- they
    # should be a committee member who doesn't already have a committee
    # review.
    if proposal.state in role_class.get_editable_states(
            role_class.CTTEE_OTHER):
        if not proposal.reviewers.has_person(
                person_id=person_id, roles=role_class.get_cttee_roles()):
            if group_members.has_entry(
                    queue_id=proposal.queue_id, group_type=GroupType.CTTEE):
                roles.append(role_class.CTTEE_OTHER)

    # Determine whether the user can add a "feedback" review -- they should be
    # a reviewer in a suitable role (or have administrative privileges) but
    # there should not already be a review of this role.
    if proposal.state in role_class.get_editable_states(
            role_class.FEEDBACK):
        if not proposal.reviewers.has_role(role_class.FEEDBACK):
            if (proposal.reviewers.has_person(
                    person_id=person_id,
                    roles=role_class.get_feedback_roles(
                        include_indirect=include_indirect))
                    or (include_indirect and (
                        (session.get('is_admin', False)
                            and can_be_admin(db, auth_cache=auth_cache))
                        or group_members.has_entry(
                            queue_id=proposal.queue_id,
                            group_type=GroupType.review_coord_groups())))):
                roles.append(role_class.FEEDBACK)

    return roles


def find_addable_reviews(db, facilities, auth_cache=None):
    """
    Find proposals for which the user can add reviews.

    This function only considers reviews which the user can "directly"
    add --- i.e. for suitable proposals it calls
    :func:`can_add_review_roles` with `include_indirect=False`.

    :param db: database control object/
    :param facilities: dictionary of FacilityInfo objects.
    :param auth_cache: authentication cache dictionary.
        **Providing this dictionary is strongly recommended.**

    :return ProposalCollection: proposals for which the user can add reviews,
        with the reviewers attribute containing a ReviewerCollection of dummy
        Review namedtuples for those reviews.
    """

    ans = ProposalCollection()

    # Assume that they can't add a review if they're not a member of any
    # review groups, so give up now if that is the case.
    group_members = _get_group_membership(
        auth_cache, db, session['person']['id'])
    if not group_members:
        return ans

    # Assume that reviews can only be added when proposals are in review
    # states -- find such proposals.  Also search only for relevant queues.
    proposals = db.search_proposal(
        state=ProposalState.review_states(),
        with_members=True, with_reviewers=True,
        queue_id=set((x.queue_id for x in group_members.values())))

    if not proposals:
        return ans

    for facility in facilities.values():
        role_class = facility.view.get_reviewer_roles()

        for proposal in proposals.values_by_facility(facility.id):
            roles = can_add_review_roles(role_class, db, proposal,
                                         include_indirect=False,
                                         auth_cache=auth_cache)
            if not roles:
                continue

            ans[proposal.id] = proposal._replace(reviewers=ReviewerCollection(
                (i, null_tuple(Reviewer)._replace(
                    role=role, review_state=ReviewState.ADDABLE))
                for (i, role) in enumerate(roles)
            ))

    return ans


@memoized
def _get_call(db, call_id):
    try:
        return db.search_call(call_id=call_id).get_single()
    except NoSuchRecord:
        return None


@memoized
def _get_group_membership(db, person_id):
    return db.search_group_member(person_id=person_id)


@memoized
def _get_user_profile(db, user_id):
    try:
        return db.get_person(person_id=None, user_id=user_id)
    except NoSuchRecord:
        return None
