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

from collections import namedtuple

from ..db.util import memoized
from ..error import NoSuchRecord, NoSuchValue
from ..type.collection import ProposalCollection, ReviewerCollection
from ..type.enum import GroupType, ProposalState, ReviewState, SiteGroupType
from ..type.simple import Call, Person, Reviewer
from ..type.util import null_tuple
from ..web.util import HTTPError, HTTPForbidden, \
    HTTPRedirectWithReferrer, url_for

Authorization = namedtuple('Authorization', ('view', 'edit'))

no = Authorization(False, False)
yes = Authorization(True, True)
view_only = Authorization(view=True, edit=False)
edit_only = Authorization(view=False, edit=True)

AuthorizationWithRating = namedtuple(
    'AuthorizationWithRating', Authorization._fields + ('view_rating',))


def for_call(current_user, db, call, auth_cache=None):
    """
    Determine the current user's authorization regarding the
    given call.

    Currently only "view" authorization is considered.
    """

    if not call.hidden:
        return view_only

    if (current_user.user is None) or (current_user.person is None):
        return no
    elif current_user.is_admin:
        return view_only

    person_id = current_user.person.id

    group_members = _get_group_membership(auth_cache, db, person_id)

    if group_members.has_entry(
            queue_id=call.queue_id,
            group_type=GroupType.HIDDEN_CALL):
        return view_only

    return no


def for_call_review(current_user, db, call, auth_cache=None):
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

    if (current_user.user is None) or (current_user.person is None):
        return no
    elif current_user.is_admin:
        return yes

    person_id = current_user.person.id

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


def for_call_review_proposal(current_user, db, proposal, auth_cache=None):
    """
    Determine general authorization for call reviews,
    based on a proposal record.

    This constucts a dummy call record and then calls :func:`for_call_review`.
    """

    return for_call_review(current_user, db, null_tuple(Call)._replace(
        queue_id=proposal.queue_id,
    ), auth_cache=auth_cache)


def for_person(current_user, db, person, auth_cache=None):
    """
    Determine the current user's authorization regarding this
    profile.

    `person` can be set to `None` to skip person-specific authorization.
    (Access will then be granted based only on administrative access.)
    """

    if current_user.user is None:
        return no
    elif current_user.is_admin:
        return yes

    auth = no
    current_person_id = (
        None if (current_user.person is None) else current_user.person.id)

    if current_person_id is not None:
        site_group_members = _get_site_group_membership(
            auth_cache, db, current_person_id)
        if site_group_members.has_entry(
                site_group_type=SiteGroupType.view_all_profile_groups()):
            auth = auth._replace(view=True)

    if person is None:
        return auth

    if person.user_id is not None:
        # This is a registered user: allow access based on the "public"
        # flag and only allow them to edit their profile.
        is_user = (person.user_id == current_user.user.id)

        return Authorization(
            view=auth.view or is_user or person.public,
            edit=auth.edit or is_user)

    if current_person_id is None:
        return auth

    # Look for proposals of which this person is a member and allow
    # access based on the proposal settings.
    for member in _get_proposal_co_membership(
            auth_cache, db, current_person_id).values():
        if member.co_member_person_id == person.id:
            if member.editor:
                return yes
            else:
                auth = auth._replace(view=True)

    # Look for reviews for which this person is the reviewer and allow
    # access to review coordinators.
    group_members = _get_group_membership(auth_cache, db, current_person_id)

    queue_ids = frozenset((
        x.queue_id for x in group_members.values_by_group_type(
            GroupType.review_coord_groups())))

    if queue_ids:
        for reviewer in _get_queue_reviewers(
                auth_cache, db, queue_ids).values():
            if reviewer.person_id == person.id:
                return yes

    return auth


def for_person_list(current_user, db, auth_cache=None):
    """
    Determine the current user's authorization regarding the full person list
    (including those without public profiles).

    This is limited to site administrators and review coordinators.
    """

    if (current_user.user is None) or (current_user.person is None):
        return no

    elif current_user.is_admin:
        return view_only

    group_members = _get_group_membership(
        auth_cache, db, current_user.person.id)

    if group_members.has_entry(
            group_type=GroupType.review_coord_groups()):
        return view_only

    return no


def for_person_member(current_user, db, member, auth_cache=None):
    """
    Determine authorization for a person profile, based on a member record.

    This constucts a dummy person record and then calls :func:`for_person`.
    """

    return for_person(current_user, db, null_tuple(Person)._replace(
        id=member.person_id,
        user_id=member.user_id,
        public=member.person_public,
    ), auth_cache=auth_cache)


def for_person_reviewer(current_user, db, reviewer, auth_cache=None):
    """
    Determine authorization for a person profile, based on a reviewer record.

    This constucts a dummy person record and then calls :func:`for_person`.
    """

    return for_person(current_user, db, null_tuple(Person)._replace(
        id=reviewer.person_id,
        user_id=reviewer.user_id,
        public=reviewer.person_public,
    ), auth_cache=auth_cache)


def for_institution(current_user, db, institution, auth_cache=None):
    """
    Determine the current user's authorization regarding this
    institution.
    """

    if current_user.user is None:
        return no
    elif current_user.is_admin:
        return yes

    if current_user.person is None:
        return view_only

    if institution.id == current_user.person.institution_id:
        # If this is the person's institution, allow them to edit it.
        return yes

    # Allow for special access to edit the institution unless it has
    # registered representatives.
    if institution.id in _get_institutions(auth_cache, db, False):
        # Is the person an editor for a proposal with a representative of
        # this institution?
        for member in _get_proposal_co_membership(
                auth_cache, db, current_user.person.id).values():
            if ((member.co_member_institution_id == institution.id)
                    and member.editor):
                return yes

        # Look for reviews for which a representative of the institution
        # is the reviewer and allow access to review coordinators.
        group_members = _get_group_membership(
            auth_cache, db, current_user.person.id)

        queue_ids = frozenset((
            x.queue_id for x in group_members.values_by_group_type(
                GroupType.review_coord_groups())))

        if queue_ids:
            for reviewer in _get_queue_reviewers(
                    auth_cache, db, queue_ids).values():
                if reviewer.institution_id == institution.id:
                    return yes

    return view_only


def for_private_moc(current_user, db, facility_id, auth_cache=None):
    """
    Determine whether the current user can view/search private MOCs.

    Currently only "view" authorization is considered.
    """

    if (current_user.user is None) or (current_user.person is None):
        return no

    # If user is an administrator, allow access.
    if current_user.is_admin:
        return view_only

    # Otherwise check groups for the given facility.
    group_members = _get_group_membership(
        auth_cache, db, current_user.person.id)

    if group_members.has_entry(
            group_type=GroupType.private_moc_groups(),
            facility_id=facility_id):
        return view_only

    return no


def for_proposal(
        role_class, current_user, db, proposal, auth_cache=None,
        allow_unaccepted_review=None):
    """
    Determine the current user's authorization regarding this proposal.
    """

    if (current_user.user is None) or (current_user.person is None):
        return no

    redirect = None
    auth = no
    person_id = current_user.person.id

    if current_user.is_admin:
        auth = auth._replace(view=True)

    try:
        member = proposal.members.get_person(person_id)
        return Authorization(
            view=True,
            edit=(member.editor and ProposalState.can_edit(proposal.state)))
    except NoSuchValue:
        pass

    if proposal.reviewers is not None:
        # Give access to people assigned as reviewers of the proposal.
        for reviewer in proposal.reviewers.values_by_person_id(person_id):
            if proposal.state in role_class.get_editable_states(reviewer.role):
                if (role_class.is_accepted_review(reviewer.role)
                        and not reviewer.accepted
                        and not allow_unaccepted_review):
                    if reviewer.accepted is not None:
                        # The reviewer has rejected this review:
                        # do not proceed with authorization.
                        pass

                    elif allow_unaccepted_review is None:
                        # Prepare the redirect but do not raise yet in case
                        # the person has other authorization for the proposal.
                        redirect = _redirect_review_accept(reviewer)

                else:
                    return auth._replace(view=True)

    if ProposalState.is_submitted(proposal.state):
        # Give access to review groups with access to view all proposals.
        group_members = _get_group_membership(auth_cache, db, person_id)

        if group_members.has_entry(
                queue_id=proposal.queue_id,
                group_type=GroupType.view_all_groups()):
            return auth._replace(view=True)

    if redirect is not None:
        raise redirect

    return auth


def for_proposal_decision(
        current_user, db, proposal, call=None, auth_cache=None):
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
    if for_call_review(current_user, db, call, auth_cache=auth_cache).edit:
        return edit_only

    return no


def for_proposal_feedback(
        role_class, current_user, db, proposal, auth_cache=None):
    """
    Determine the current user's authorization regarding general feedback
    for a proposal.

    This may include, but is not limited to, the feedback review.  For more
    specific access to that review, use the for_review function.
    This function currently only allows view access.
    """

    if (current_user.user is None) or (current_user.person is None):
        return no

    # Only allow access to the feedback information when the review is
    # complete.
    if not ProposalState.is_reviewed(proposal.state):
        return no

    # Allow administrators to view.
    if current_user.is_admin:
        return view_only

    person_id = current_user.person.id

    # Allow proposal members to view.
    if proposal.members.has_person(person_id):
        return view_only

    # Give access to review groups with permission to view all feedback.
    group_members = _get_group_membership(auth_cache, db, person_id)

    if group_members.has_entry(
            queue_id=proposal.queue_id,
            group_type=GroupType.feedback_view_groups()):
        return view_only

    # Otherwise deny access.
    return no


def for_review(
        role_class, current_user, db, reviewer, proposal, auth_cache=None,
        skip_membership_test=False,
        allow_unaccepted=None):
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

    The `skip_membership_test` argument can be set to skip the check
    that the person is not a member of the proposal.  This should
    only be used when considering access for non-sensitive information
    which it is acceptable for the proposal members to see, such as
    calculation results.  The membership check is not applied if
    "reviewer" is given and the role is FEEDBACK because feedback
    reports should not contain sensitive information and the review
    coordinator may need to process feedback for thier own proposal.

    The `allow_unaccepted` argument controls handling of reviews roles
    with acceptance (`role_class.is_accepted_review` returns `True`).
    If this is `None` (the default) then an attempt to authenticate
    for an unaccepted review results in a redirect to the acceptance
    page.  This mode can only be used from routes within the facility
    blueprint.  If it is `True` then acceptance is ignored.  If it is `False`
    then authentication is denied for unaccepted reviews.

    :return AuthorizationWithRating: including field indicating whether
        the ratings can be viewed.
    """

    if (current_user.user is None) or (current_user.person is None):
        return AuthorizationWithRating(*no, view_rating=False)

    person_id = current_user.person.id

    # Forbid access if the person is a member of the proposal, unless this
    # is for the feedback review.
    if not skip_membership_test:
        if proposal.members.has_person(person_id):
            if (reviewer is None) or (reviewer.role != role_class.FEEDBACK):
                return AuthorizationWithRating(*no, view_rating=False)

    # Determine whether the proposal is in a state where this review is
    # editable.  If we have a specific reviewer, check that role's states.
    if (reviewer is not None):
        if proposal.state in role_class.get_editable_states(reviewer.role):
            # Allow full access to the reviewer while the review is editable.
            if person_id == reviewer.person_id:
                if (role_class.is_accepted_review(reviewer.role)
                        and not reviewer.accepted
                        and not allow_unaccepted):
                    if reviewer.accepted is not None:
                        # The reviewer has rejected this review:
                        # do not proceed with authorization.
                        pass

                    elif allow_unaccepted is None:
                        raise _redirect_review_accept(reviewer)

                else:
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
    if current_user.is_admin:
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


def can_be_admin(current_user, db, auth_cache=None):
    """
    Check whether the user is permitted to take administrative
    privileges.
    """

    if current_user.person is None:
        raise HTTPForbidden('Could not verify administrative access.')

    return current_user.person.admin


def can_add_review_roles(
        type_class, role_class,
        current_user, db, proposal, include_indirect=True,
        auth_cache=None):
    """
    Determine for which reviewer roles a person can add a review to
    a proposal.

    If no reviews can be added then an empty list is returned.
    """

    person_id = current_user.person.id

    # If the person is a member of the proposal, they can't add any reviews.
    if proposal.members.has_person(person_id=person_id):
        return []

    roles = []

    group_members = _get_group_membership(auth_cache, db, person_id)

    # Determine whether the user can add a committee "other" review -- they
    # should be a committee member who doesn't already have a committee
    # review.
    if (type_class.has_reviewer_role(proposal.call_type, role_class.CTTEE_OTHER)
            and (proposal.state in role_class.get_editable_states(
                role_class.CTTEE_OTHER))):
        if not proposal.reviewers.has_person(
                person_id=person_id, roles=role_class.get_cttee_roles()):
            if group_members.has_entry(
                    queue_id=proposal.queue_id, group_type=GroupType.CTTEE):
                roles.append(role_class.CTTEE_OTHER)

    # Determine whether the user can add a "feedback" review -- they should be
    # a reviewer in a suitable role (or have administrative privileges) but
    # there should not already be a review of this role.
    if (type_class.has_reviewer_role(proposal.call_type, role_class.FEEDBACK)
            and (proposal.state in role_class.get_editable_states(
                role_class.FEEDBACK))):
        if not proposal.reviewers.has_role(role_class.FEEDBACK):
            if (proposal.reviewers.has_person(
                    person_id=person_id,
                    roles=role_class.get_feedback_roles(
                        include_indirect=include_indirect))
                    or (include_indirect and (
                        current_user.is_admin
                        or group_members.has_entry(
                            queue_id=proposal.queue_id,
                            group_type=GroupType.review_coord_groups())))):
                roles.append(role_class.FEEDBACK)

    return roles


def find_addable_reviews(current_user, db, facilities, auth_cache=None):
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
        auth_cache, db, current_user.person.id)
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
        type_class = facility.view.get_call_types()

        for proposal in proposals.values_by_facility(facility.id):
            roles = can_add_review_roles(
                type_class, role_class, current_user, db, proposal,
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


def _redirect_review_accept(reviewer):
    """
    Generate (but do not raise) a redirect exception to the acceptance page
    for the given review.

    This generates a URL in the current blueprint, so it can only be used
    from the blueprint of the facility corresponding to the given review.
    """

    return HTTPRedirectWithReferrer(
        url_for('.review_accept', reviewer_id=reviewer.id))


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
def _get_institutions(db, has_registered_person):
    return db.search_institution(has_registered_person=has_registered_person)


@memoized
def _get_proposal_co_membership(db, person_id):
    """Get proposal membership for proposals in editable states."""
    return db.search_co_member(
        person_id, with_institution_id=True,
        proposal_state=ProposalState.editable_states())


@memoized
def _get_site_group_membership(db, person_id):
    return db.search_site_group_member(person_id=person_id)


@memoized
def _get_queue_reviewers(db, queue_id):
    """Get reviewers in for the given queue for proposals in review states."""
    return db.search_reviewer(
        queue_id=queue_id,
        proposal_state=ProposalState.review_states())
