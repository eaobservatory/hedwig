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

from ...error import DatabaseIntegrityError, NoSuchRecord, UserError
from ...view.util import with_verified_admin
from ...web.util import ErrorPage, HTTPError, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from ...type import GroupType, Link, \
    ProposalState, ProposalWithCode, ReviewerRole

ProposalWithReviewerPersons = namedtuple(
    'ProposalWithReviewerPersons',
    ProposalWithCode._fields + ('person_ids_primary', 'person_ids_secondary'))


class GenericReview(object):
    @with_verified_admin
    def view_review_call_reviewers(self, db, call_id):
        try:
            call = db.get_call(facility_id=self.id_, call_id=call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call or semester not found')

        proposals = db.search_proposal(
            call_id=call_id, state=ProposalState.submitted_states(),
            person_pi=True, with_reviewers=True, with_review_info=True)

        return {
            'title': 'Reviewers: {} {}'.format(call.semester_name,
                                               call.queue_name),
            'proposals': [
                ProposalWithCode(*x, code=self.make_proposal_code(db, x),
                                 facility_code=None)
                for x in proposals.values()],
            'targets': [
                Link('Assign technical reviewers',
                     url_for('.review_call_technical', call_id=call_id)),
                Link('Assign committee members',
                     url_for('.review_call_committee', call_id=call_id))],
        }

    @with_verified_admin
    def view_reviewer_grid(self, db, call_id, primary_role, form):
        try:
            call = db.get_call(facility_id=self.id_, call_id=call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call or semester not found')

        if primary_role == ReviewerRole.TECH:
            group_type = GroupType.TECH
            secondary_role = None
            target = url_for('.review_call_technical', call_id=call_id)

        elif primary_role == ReviewerRole.CTTEE_PRIMARY:
            group_type = GroupType.CTTEE
            secondary_role = ReviewerRole.CTTEE_SECONDARY
            target = url_for('.review_call_committee', call_id=call_id)

        else:
            raise ErrorPage('Unexpected reviewer role')

        primary_role_info = ReviewerRole.get_info(primary_role)
        secondary_role_info = (None if secondary_role is None else
                               ReviewerRole.get_info(secondary_role))

        group_info = GroupType.get_info(group_type)

        group_members = db.search_group_member(queue_id=call.queue_id,
                                               group_type=group_type,
                                               with_person=True)

        group_person_ids = [x.person_id for x in group_members.values()]

        proposals = [
            ProposalWithReviewerPersons(
                *x, code=self.make_proposal_code(db, x),
                facility_code=None,
                person_ids_primary=x.reviewers.person_id_by_role(primary_role),
                person_ids_secondary=(None if secondary_role is None else
                                      x.reviewers.person_id_by_role(
                                          secondary_role)))
            for x in db.search_proposal(
                call_id=call_id, state=ProposalState.submitted_states(),
                person_pi=True, with_reviewers=True).values()]

        role_list = zip([primary_role, secondary_role],
                        [primary_role_info, secondary_role_info],
                        ['primary', 'secondary'])

        message = None

        if form is not None:
            # Read the form inputs into an updated proposal list.  Do this
            # first so that we can return the whole updated grid to the user
            # in case of an error performing the update.
            proposals_updated = []
            for proposal in proposals:
                for (role, role_info, prefix) in role_list:
                    if role is None:
                        continue

                    if role_info.unique:
                        # Read the radio button setting.
                        person_ids = []
                        id_ = '{}_{}'.format(prefix, proposal.id)
                        if id_ in form:
                            person_id = int(form[id_])
                            if person_id in group_person_ids:
                                person_ids = [person_id]

                    else:
                        # See which checkbox inputs are present.
                        person_ids = [
                            x for x in group_person_ids
                            if '{}_{}_{}'.format(prefix, proposal.id, x)
                            in form]

                    proposal = proposal._replace(
                        **{'person_ids_{}'.format(prefix): person_ids})

                proposals_updated.append(proposal)

            try:
                for (proposal, proposal_updated) in zip(
                        proposals, proposals_updated):
                    for (role, role_info, prefix) in role_list:
                        if role is None:
                            continue
                        if proposal.id != proposal_updated.id:
                            raise HTTPError('Proposals got out of sync.')

                        id_ = 'person_ids_{}'.format(prefix)
                        orig = getattr(proposal, id_)
                        updated = getattr(proposal_updated, id_)

                        # Apply uniqueness constraint.
                        if role_info.unique and (len(updated) > 1):
                            raise UserError(
                                'Multiple {} reviewers selected for '
                                'proposal {}.',
                                prefix, proposal.code)

                        # Make list of people to add and remove from original
                        # list (so that this is the removal list) and then
                        # apply removals first to avoid violating the
                        # uniqueness constraint in the database code.
                        person_new = []

                        for person_id in updated:
                            if person_id in orig:
                                orig.remove(person_id)
                            else:
                                person_new.append(person_id)

                        for person_id in orig:
                            try:
                                db.delete_reviewer(
                                    proposal_id=proposal.id,
                                    person_id=person_id,
                                    role=role)
                            except DatabaseIntegrityError:
                                raise UserError(
                                    'Could not remove previous reviewer for '
                                    'proposal {}.  Perhaps they have already '
                                    'provided a review?',
                                    proposal.code)

                        for person_id in person_new:
                            db.add_reviewer(
                                proposal_id=proposal.id, person_id=person_id,
                                role=role)

                flash('The {} assignments have been updated.',
                      group_info.name.lower())
                raise HTTPRedirect(url_for('.review_call_reviewers',
                                           call_id=call_id))

            except UserError as e:
                message = e.message
                proposals = proposals_updated

        return {
            'title': '{}: {} {}'.format(group_info.name.title(),
                                        call.semester_name, call.queue_name),
            'proposals': proposals,
            'target': target,
            'group_members': list(group_members.values()),
            'primary_unique': primary_role_info.unique,
            'secondary_unique': (None if secondary_role_info is None else
                                 secondary_role_info.unique),
            'message': message,
        }
