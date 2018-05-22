# Copyright (C) 2015-2017 East Asian Observatory
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

from datetime import datetime

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, case
from sqlalchemy.sql.functions import count

from ...error import ConsistencyError, Error, FormattedError, \
    NoSuchRecord, UserError
from ...type.collection import GroupMemberCollection, ReviewerCollection
from ...type.enum import Assessment, FormatType, GroupType, ReviewState
from ...type.simple import GroupMember, Reviewer
from ...util import is_list_like
from ..meta import call, decision, group_member, \
    institution, invitation, person, \
    proposal, queue, \
    review, reviewer


class ReviewPart(object):
    def add_group_member(self, queue_id, group_type, person_id,
                         _conn=None, _test_skip_check=False):
        if not GroupType.is_valid(group_type):
            raise Error('invalid group type')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, queue, queue_id):
                    raise ConsistencyError('queue does not exist with id={}',
                                           queue_id)
                if not self._exists_id(conn, person, person_id):
                    raise ConsistencyError('person does not exist with id={}',
                                           person_id)

            result = conn.execute(group_member.insert().values({
                group_member.c.queue_id: queue_id,
                group_member.c.group_type: group_type,
                group_member.c.person_id: person_id,
            }))

        return result.inserted_primary_key[0]

    def add_reviewer(self, role_class, proposal_id, person_id, role,
                     _test_skip_check=False, _conn=None):
        try:
            role_info = role_class.get_info(role)
        except KeyError:
            raise Error('invalid reviewer role')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, proposal, proposal_id):
                    raise ConsistencyError(
                        'proposal does not exist with id={}', proposal_id)
                if not self._exists_id(conn, person, person_id):
                    raise ConsistencyError(
                        'person does not exist with id={}', person_id)

            # Do not allow the "unique" check to be skipped because there is
            # no database constraint for this.  (Which is because some roles
            # are unique and others are not.)
            if role_info.unique:
                if self._exists_reviewer(conn, proposal_id, role):
                    raise UserError(
                        'There is already a "{}" reviewer for this proposal.',
                        role_info.name)

            result = conn.execute(reviewer.insert().values({
                reviewer.c.proposal_id: proposal_id,
                reviewer.c.person_id: person_id,
                reviewer.c.role: role,
            }))

        return result.inserted_primary_key[0]

    def delete_reviewer(self, reviewer_id=None,
                        proposal_id=None, person_id=None, role=None,
                        delete_review=False, _conn=None):
        """
        Delete a reviewer record from the database.

        This can, optionally, also delete any associated review.  This
        is because, in the database, review.reviewer references
        reviewer.id with "ondelete" set to restrict.  (We don't want
        to accidentally delete reviews when working with th reviewer table.)
        The option allows the deletion to be "cascaded" manually when
        necessary.

        Either selects the reviewer to delete by the "reviewer_id"
        argument, if it is specified, or, otherwise, by the proposal_id,
        person_id and role, all of whic must be specified together.
        """

        with self._transaction(_conn=_conn) as conn:
            if delete_review:
                result = conn.execute(review.delete().where(
                    review.c.reviewer_id == reviewer_id))
                if result.rowcount > 1:
                    raise ConsistencyError(
                        'multiple rows matched deleting reviews by {}',
                        reviewer_id)

            stmt = reviewer.delete()

            if reviewer_id is not None:
                stmt = stmt.where(reviewer.c.id == reviewer_id)

            elif proposal_id is None or person_id is None or role is None:
                raise Error('Either reviewer_id or proposal/person/role '
                            'must be specified.')

            else:
                stmt = stmt.where(and_(reviewer.c.proposal_id == proposal_id,
                                       reviewer.c.person_id == person_id,
                                       reviewer.c.role == role))

            result = conn.execute(stmt)

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting reviewer {}', reviewer_id)

    def multiple_reviewer_update(self, role_class, remove=None, add=None):
        """
        Perform multiple reviewer updates.

        This is so that multiple updates to the reviewer assignment
        table can be prepared and then carried out (here) in a single
        transaction.  The removals are performed first to avoid
        triggering the uniqueness constraint when the reviewer for
        a "unique" role is being changed.

        The "role_class" for the relevant facility must be provided -- this
        will be passed to "add_reviewer".

        "remove" and "add" are lists of kwargs dictionaries to be passed
        to "delete_reviewer" and "add_reviewer" respectively.
        """

        with self._transaction() as conn:
            if remove is not None:
                for kwargs in remove:
                    self.delete_reviewer(_conn=conn, **kwargs)

            if add is not None:
                for kwargs in add:
                    self.add_reviewer(role_class=role_class,
                                      _conn=conn, **kwargs)

    def search_group_member(self, queue_id=None, group_type=None,
                            person_id=None, facility_id=None,
                            group_member_id=None,
                            with_person=False, _conn=None):
        select_from = group_member.join(queue)

        select_columns = [
            group_member,
            queue.c.facility_id,
        ]

        if with_person:
            select_columns.extend([
                group_member,
                person.c.name.label('person_name'),
                person.c.public.label('person_public'),
                (person.c.user_id.isnot(None)).label('person_registered'),
                person.c.institution_id,
                institution.c.name.label('institution_name'),
                institution.c.department.label('institution_department'),
                institution.c.organization.label('institution_organization'),
                institution.c.country.label('institution_country'),
            ])

            select_from = select_from.join(person).outerjoin(institution)

            default = None
        else:
            default = {
                'person_name': None,
                'person_public': None,
                'person_registered': None,
                'institution_id': None,
                'institution_name': None,
                'institution_department': None,
                'institution_organization': None,
                'institution_country': None,
            }

        stmt = select(select_columns).select_from(select_from)

        if queue_id is not None:
            stmt = stmt.where(group_member.c.queue_id == queue_id)

        if group_type is not None:
            if is_list_like(group_type):
                stmt = stmt.where(group_member.c.group_type.in_(group_type))
            else:
                stmt = stmt.where(group_member.c.group_type == group_type)

        if person_id is not None:
            stmt = stmt.where(group_member.c.person_id == person_id)

        if facility_id is not None:
            stmt = stmt.where(queue.c.facility_id == facility_id)

        if group_member_id is not None:
            stmt = stmt.where(group_member.c.id == group_member_id)

        if with_person:
            stmt = stmt.order_by(person.c.name.asc())
        else:
            stmt = stmt.order_by(group_member.c.id.asc())

        ans = GroupMemberCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                if default is not None:
                    values = default.copy()
                    values.update(**row)
                else:
                    values = row

                ans[row['id']] = GroupMember(**values)

        return ans

    def search_reviewer(self,
                        proposal_id=None, role=None, reviewer_id=None,
                        person_id=None, review_state=None,
                        call_id=None, queue_id=None,
                        proposal_state=None, institution_id=None,
                        with_review=False, with_review_text=False,
                        with_review_note=False,
                        with_invitation=False,
                        _conn=None):
        select_columns = [
            reviewer,
            person.c.name.label('person_name'),
            person.c.public.label('person_public'),
            (person.c.user_id.isnot(None)).label('person_registered'),
            person.c.institution_id,
            institution.c.name.label('institution_name'),
            institution.c.department.label('institution_department'),
            institution.c.organization.label('institution_organization'),
            institution.c.country.label('institution_country'),
        ]

        select_from = reviewer.join(person).outerjoin(institution)

        iter_field = None
        iter_list = None

        default = {'review_extra': None}

        if with_invitation:
            select_columns.extend((
                invitation.c.token.label('invitation_token'),
                invitation.c.expiry.label('invitation_expiry'),
            ))

            select_from = select_from.outerjoin(invitation)

        else:
            default.update({
                'invitation_token': None,
                'invitation_expiry': None,
            })

        if with_review:
            select_columns.append(
                self._expr_review_state().label('review_state'))

            select_columns.extend((x.label('review_{}'.format(x.name))
                                   for x in review.columns
                                   if x not in (review.c.reviewer_id,
                                                review.c.text,
                                                review.c.note,
                                                review.c.state)))

            if with_review_text:
                select_columns.append(review.c.text.label('review_text'))
            else:
                default['review_text'] = None

            if with_review_note:
                select_columns.append(review.c.note.label('review_note'))
            else:
                default['review_note'] = None

        else:
            default.update({
                'review_{}'.format(x.name): None
                for x in review.columns if x != review.c.reviewer_id})

        if (with_review or (review_state is not None)):
            select_from = select_from.outerjoin(review)

        if ((call_id is not None)
                or (queue_id is not None)
                or (proposal_state is not None)):
            select_from = select_from.join(proposal)

            if queue_id is not None:
                select_from = select_from.join(call)

        stmt = select(select_columns).select_from(select_from)

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = reviewer.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(reviewer.c.proposal_id == proposal_id)

        if role is not None:
            if is_list_like(role):
                stmt = stmt.where(reviewer.c.role.in_(role))
            else:
                stmt = stmt.where(reviewer.c.role == role)

        if reviewer_id is not None:
            stmt = stmt.where(reviewer.c.id == reviewer_id)

        if person_id is not None:
            stmt = stmt.where(reviewer.c.person_id == person_id)

        if review_state is not None:
            if is_list_like(review_state):
                stmt = stmt.where(self._expr_review_state().in_(review_state))
            else:
                stmt = stmt.where(self._expr_review_state() == review_state)

        if call_id is not None:
            if is_list_like(call_id):
                stmt = stmt.where(proposal.c.call_id.in_(call_id))
            else:
                stmt = stmt.where(proposal.c.call_id == call_id)

        if queue_id is not None:
            if is_list_like(queue_id):
                stmt = stmt.where(call.c.queue_id.in_(queue_id))
            else:
                stmt = stmt.where(call.c.queue_id == queue_id)

        if proposal_state is not None:
            if is_list_like(proposal_state):
                stmt = stmt.where(proposal.c.state.in_(proposal_state))
            else:
                stmt = stmt.where(proposal.c.state == proposal_state)

        if institution_id is not None:
            stmt = stmt.where(person.c.institution_id == institution_id)

        ans = ReviewerCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt.order_by(
                        reviewer.c.role, person.c.name, reviewer.c.id)):
                    values = default.copy()
                    values.update(**row)
                    ans[row['id']] = Reviewer(**values)

        return ans

    def _expr_review_state(self):
        return case([
            (review.c.reviewer_id.isnot(None), review.c.state),
        ], else_=ReviewState.NOT_DONE)

    def set_decision(self, proposal_id, accept=(), exempt=None, ready=None,
                     note=None, note_format=None, is_update=False):
        values = {}

        if accept != ():
            values[decision.c.accept] = accept
        if exempt is not None:
            values[decision.c.exempt] = exempt
        if ready is not None:
            values[decision.c.ready] = ready
        if note is not None:
            if not note_format:
                raise UserError('Note format not specified.')
            if not FormatType.is_valid(note_format):
                raise UserError('Note format not recognised.')
            values[decision.c.note] = note
            values[decision.c.note_format] = note_format

        if not values:
            raise Error('no decision update specified')

        with self._transaction() as conn:
            proposal = self.get_proposal(
                facility_id=None, proposal_id=proposal_id,
                with_decision=True, _conn=conn)

            if is_update and not proposal.has_decision:
                raise ConsistencyError(
                    'decision does not already exist for {}', proposal_id)
            elif proposal.has_decision and not is_update:
                raise ConsistencyError(
                    'decision already exists for {}', proposal_id)

            if is_update:
                result = conn.execute(decision.update().where(
                    decision.c.proposal_id == proposal_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating decision for proposal {}',
                        proposal_id)

            else:
                values.update({
                    decision.c.proposal_id: proposal_id,
                })

                result = conn.execute(decision.insert().values(values))

    def set_review(self, role_class, reviewer_id, text, format_,
                   assessment, rating, weight,
                   note, note_format, note_public,
                   state, is_update):
        if text is not None:
            if not format_:
                raise UserError('Text format not specified.')
            if not FormatType.is_valid(format_):
                raise UserError('Text format not recognised.')

        if note is not None:
            if not note_format:
                raise UserError('Note format not specified.')
            if not FormatType.is_valid(note_format):
                raise UserError('Note format not recognised.')

        if assessment is not None:
            if not Assessment.is_valid(assessment):
                raise UserError('Assessment value not recognised.')

        if not (ReviewState.is_valid(state) and ReviewState.is_present(state)):
            raise Error('invalid review state')
        state_done = (state == ReviewState.DONE)

        values = {
            review.c.text: text,
            review.c.format: (None if text is None else format_),
            review.c.assessment: assessment,
            review.c.rating: rating,
            review.c.weight: weight,
            review.c.edited: datetime.utcnow(),
            review.c.note: note,
            review.c.note_format: (None if note is None else note_format),
            review.c.note_public: ((note is not None) and note_public),
            review.c.state: state,
        }

        with self._transaction() as conn:
            # Find out what type of review this is so that we can
            # determine which attributes are appropriate.
            reviewer = self.search_reviewer(
                reviewer_id=reviewer_id, _conn=conn).get_single()

            role_info = role_class.get_info(reviewer.role)
            attr_values = {k.name: v for (k, v) in values.items()}

            for attr in ('text', 'assessment', 'rating', 'weight', 'note'):
                if getattr(role_info, attr):
                    # Check for missing attributes only if review is done.
                    if state_done and (attr_values[attr] is None):
                        raise FormattedError(
                            'The {} should be specified.', attr)
                else:
                    if attr_values[attr] is not None:
                        raise FormattedError(
                            'The {} should not be specified.', attr)

            # Check if the review already exists.
            already_exists = self._exists_review(conn, reviewer_id=reviewer_id)
            if is_update and not already_exists:
                raise ConsistencyError(
                    'review does not exist for reviewer {}', reviewer_id)
            elif already_exists and not is_update:
                raise ConsistencyError(
                    'review already exists for reviewer {}', reviewer_id)

            # Perform the insert/update.
            if is_update:
                result = conn.execute(review.update().where(
                    review.c.reviewer_id == reviewer_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating review {}', reviewer_id)

            else:
                values.update({
                    review.c.reviewer_id: reviewer_id,
                })

                result = conn.execute(review.insert().values(values))

    def sync_group_member(self, queue_id, group_type, records):
        """
        Update the member records of the given group for the given queue.

        Currently this just allows removing members of the group,
        but could be extended if group members gain extra attributes.
        (E.g. the chair of a group representing a committee.)
        """

        if not GroupType.is_valid(group_type):
            raise Error('invalid group type')

        with self._transaction() as conn:
            if not self._exists_id(conn, queue, queue_id):
                raise ConsistencyError('queue does not exist with id={}',
                                       queue_id)

            self._sync_records(
                conn, group_member,
                key_column=(group_member.c.queue_id,
                            group_member.c.group_type),
                key_value=(queue_id, group_type),
                records=records,
                update_columns=(),
                forbid_add=True)

    def _exists_reviewer(self, conn, proposal_id, role):
        """
        Test whether a reviewer record of the given role already exists
        for a proposal.
        """

        return 0 < conn.execute(select([count(reviewer.c.id)]).where(and_(
            reviewer.c.proposal_id == proposal_id,
            reviewer.c.role == role
        ))).scalar()

    def _exists_review(self, conn, reviewer_id):
        """
        Test whether a review record by the given reviewer exists.
        """

        return 0 < conn.execute(select([count(review.c.reviewer_id)]).where(
            review.c.reviewer_id == reviewer_id
        )).scalar()
