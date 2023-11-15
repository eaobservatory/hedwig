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

from datetime import datetime

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, case, not_
from sqlalchemy.sql.functions import count

from ...error import ConsistencyError, Error, FormattedError, \
    NoSuchRecord, UserError
from ...type.collection import GroupMemberCollection, ResultCollection, \
    ReviewerCollection, ReviewerAcceptanceCollection, ReviewDeadlineCollection, \
    ReviewFigureCollection
from ...type.enum import Assessment, FormatType, GroupType, ReviewState
from ...type.simple import GroupMember, Note, \
    Reviewer, ReviewerAcceptance, \
    ReviewDeadline, ReviewFigureInfo
from ...util import is_list_like
from ..meta import affiliation_weight_note, available_note, \
    call, decision, group_member, \
    institution, invitation, person, \
    proposal, queue, \
    review, reviewer, reviewer_acceptance, reviewer_note, review_deadline, \
    review_fig, review_fig_link, review_fig_preview, review_fig_thumbnail


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

    def add_reviewer_acceptance(
            self, role_class, proposal_id, person_id, role,
            accepted, text, format_, _conn=None):
        if not role_class.is_accepted_review(role):
            raise Error('This reviewer role does not require acceptance.')

        if text is None:
            raise Error('Acceptance explanation text not specified.')

        if not format_:
            raise UserError('Text format not specified.')
        if not FormatType.is_valid(format_):
            raise UserError('Text format not recognised.')

        values = {
            reviewer_acceptance.c.proposal_id: proposal_id,
            reviewer_acceptance.c.person_id: person_id,
            reviewer_acceptance.c.role: role,
            reviewer_acceptance.c.accepted: accepted,
            reviewer_acceptance.c.text: text,
            reviewer_acceptance.c.format: format_,
            reviewer_acceptance.c.date: datetime.utcnow(),
        }

        with self._transaction(_conn=_conn) as conn:
            if not self._exists_reviewer(conn, proposal_id, role, person_id):
                raise ConsistencyError(
                    'reviewer does not exist for prop {} person {} role {}',
                    proposal_id, person_id, role)

            result = conn.execute(reviewer_acceptance.insert().values(values))

        return result.inserted_primary_key[0]

    def add_review_figure(
            self, reviewer_id,
            type_, figure, caption, filename, uploader_person_id,
            _test_skip_check=False):
        return self._add_figure(
            review_fig, review_fig_link, review_fig_link.c.reviewer_id,
            reviewer_id, reviewer,
            type_, figure, caption, filename, uploader_person_id,
            _test_skip_check=_test_skip_check)

    def delete_affiliation_weight_note(self, call_id, _conn=None):
        self._delete_note(
            table=affiliation_weight_note,
            key_column=affiliation_weight_note.c.call_id,
            key_value=call_id,
            _conn=_conn)

    def delete_available_note(self, call_id, _conn=None):
        self._delete_note(
            table=available_note,
            key_column=available_note.c.call_id,
            key_value=call_id,
            _conn=_conn)

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

    def delete_reviewer_acceptance(self, reviewer_acceptance_id, _conn=None):
        """
        Delete a reviewer acceptance explanation record.
        """

        stmt = reviewer_acceptance.delete().where(
            reviewer_acceptance.c.id == reviewer_acceptance_id)

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt)

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting reviewer acceptance {}',
                    reviewer_acceptance_id)

    def delete_reviewer_note(self, reviewer_id, _conn=None):
        self._delete_note(
            table=reviewer_note,
            key_column=reviewer_note.c.reviewer_id,
            key_value=reviewer_id,
            _conn=_conn)

    def _delete_note(self, table, key_column, key_value, _conn):
        stmt = table.delete().where(key_column == key_value)

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt)

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting note for id {}', key_value)

    def delete_review_figure(self, reviewer_id, id_):
        where_extra = []

        if reviewer_id is not None:
            where_extra.append(review_fig_link.c.reviewer_id == reviewer_id)

        return self._delete_figure(
            review_fig, review_fig_link, id_, where_extra=where_extra)

    def get_affiliation_weight_note(self, call_id, _conn=None):
        return self._get_note(
            table=affiliation_weight_note,
            key_column=affiliation_weight_note.c.call_id,
            key_value=call_id,
            _conn=_conn)

    def get_available_note(self, call_id, _conn=None):
        return self._get_note(
            table=available_note,
            key_column=available_note.c.call_id,
            key_value=call_id,
            _conn=_conn)

    def _get_note(self, table, key_column, key_value, _conn):
        stmt = table.select().where(key_column == key_value)

        with self._transaction(_conn=_conn) as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('note does not exist')

        return Note(text=row['note'], format=row['note_format'])

    def get_review_figure(self, reviewer_id, link_id, fig_id=None, md5sum=None):
        where_extra = []

        if reviewer_id is not None:
            where_extra.append(review_fig_link.c.reviewer_id == reviewer_id)

        return self._get_figure(
            review_fig, review_fig_link, link_id, fig_id, md5sum,
            where_extra=where_extra)

    def get_review_figure_preview(
            self, reviewer_id, link_id, fig_id=None, md5sum=None):
        where_extra = []

        if reviewer_id is not None:
            where_extra.append(review_fig_link.c.reviewer_id == reviewer_id)

        return self._get_figure_alternate(
            review_fig, review_fig_link, review_fig_preview.c.preview,
            link_id, fig_id, md5sum, where_extra=where_extra)

    def get_review_figure_thumbnail(
            self, reviewer_id, link_id, fig_id=None, md5sum=None):
        where_extra = []

        if reviewer_id is not None:
            where_extra.append(review_fig_link.c.reviewer_id == reviewer_id)

        return self._get_figure_alternate(
            review_fig, review_fig_link, review_fig_thumbnail.c.thumbnail,
            link_id, fig_id, md5sum, where_extra=where_extra)

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
                            with_person=False, with_queue=False, _conn=None):
        select_from = group_member.join(queue)

        select_columns = [
            group_member,
            queue.c.facility_id,
        ]

        default = {}

        if with_person:
            select_columns.extend([
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

        else:
            default.update({
                'person_name': None,
                'person_public': None,
                'person_registered': None,
                'institution_id': None,
                'institution_name': None,
                'institution_department': None,
                'institution_organization': None,
                'institution_country': None,
            })

        if with_queue:
            select_columns.extend([
                queue.c.code.label('queue_code'),
                queue.c.name.label('queue_name'),
            ])

        else:
            default.update({
                'queue_code': None,
                'queue_name': None,
            })

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
                if default:
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
                        notified=None, accepted=(),
                        with_review=False, with_review_text=False,
                        with_review_note=False,
                        with_invitation=False,
                        with_acceptance=False,
                        with_note=False,
                        _conn=None):
        select_columns = [
            reviewer,
            person.c.name.label('person_name'),
            person.c.public.label('person_public'),
            (person.c.user_id.isnot(None)).label('person_registered'),
            person.c.user_id.label('user_id'),
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

        if with_acceptance:
            select_columns.extend((
                reviewer_acceptance.c.accepted.label('acceptance_accepted'),
                reviewer_acceptance.c.text.label('acceptance_text'),
                reviewer_acceptance.c.format.label('acceptance_format'),
                reviewer_acceptance.c.date.label('acceptance_date'),
            ))

            select_from = select_from.outerjoin(reviewer_acceptance, and_(
                reviewer.c.proposal_id == reviewer_acceptance.c.proposal_id,
                reviewer.c.person_id == reviewer_acceptance.c.person_id,
                reviewer.c.role == reviewer_acceptance.c.role,
            ))

        else:
            default.update({
                'acceptance_accepted': None,
                'acceptance_text': None,
                'acceptance_format': None,
                'acceptance_date': None,
            })

        if with_note:
            select_columns.extend((
                reviewer_note.c.note.label('note'),
                reviewer_note.c.note_format.label('note_format'),
            ))

            select_from = select_from.outerjoin(reviewer_note)

        else:
            default.update({
                'note': None,
                'note_format': None,
            })

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

        if accepted != ():
            if accepted is None:
                stmt = stmt.where(reviewer.c.accepted.is_(None))
            elif accepted:
                stmt = stmt.where(reviewer.c.accepted)
            else:
                stmt = stmt.where(not_(reviewer.c.accepted))

        if notified is not None:
            if notified:
                stmt = stmt.where(reviewer.c.notified)
            else:
                stmt = stmt.where(not_(reviewer.c.notified))

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
            (not_(reviewer.c.accepted), ReviewState.REJECTED),
            (review.c.reviewer_id.isnot(None), review.c.state),
        ], else_=ReviewState.NOT_DONE)

    def search_reviewer_acceptance(
            self, reviewer_acceptance_id=None,
            proposal_id=None, person_id=None, role=None,
            with_text=False,
            _conn=None):
        select_columns = [
            reviewer_acceptance.c.id,
            reviewer_acceptance.c.proposal_id,
            reviewer_acceptance.c.person_id,
            reviewer_acceptance.c.role,
            reviewer_acceptance.c.accepted,
            reviewer_acceptance.c.date,
        ]

        default = {}

        if with_text:
            select_columns.extend((
                reviewer_acceptance.c.text,
                reviewer_acceptance.c.format,
            ))

        else:
            default.update({
                'text': None,
                'format': None,
            })

        stmt = select(select_columns)

        iter_field = None
        iter_list = None

        if reviewer_acceptance_id is not None:
            stmt = stmt.where(reviewer_acceptance.c.id == reviewer_acceptance_id)

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = reviewer_acceptance.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(
                    reviewer_acceptance.c.proposal_id == proposal_id)

        if person_id is not None:
            if is_list_like(person_id):
                assert iter_field is None
                iter_field = reviewer_acceptance.c.person_id
                iter_list = person_id
            else:
                stmt = stmt.where(reviewer_acceptance.c.person_id == person_id)

        if role is not None:
            if is_list_like(role):
                stmt = stmt.where(reviewer_acceptance.c.role.in_(role))
            else:
                stmt = stmt.where(reviewer_acceptance.c.role == role)

        ans = ReviewerAcceptanceCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt.order_by(
                        reviewer_acceptance.c.id)):
                    values = default.copy()
                    values.update(**row)
                    ans[row['id']] = ReviewerAcceptance(**values)

        return ans

    def search_review_deadline(
            self, call_id=None, role=None, _conn=None):
        """
        Search for review deadlines.
        """

        stmt = review_deadline.select()

        iter_field = None
        iter_list = None

        if call_id is not None:
            if is_list_like(call_id):
                assert iter_field is None
                iter_field = review_deadline.c.call_id
                iter_list = call_id
            else:
                stmt = stmt.where(review_deadline.c.call_id == call_id)

        if role is not None:
            if is_list_like(role):
                stmt = stmt.where(review_deadline.c.role.in_(role))
            else:
                stmt = stmt.where(review_deadline.c.role == role)

        ans = ReviewDeadlineCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt):
                    ans[row['id']] = ReviewDeadline(**row)

        return ans

    def search_review_figure(
            self, reviewer_id=None, state=None, link_id=None, fig_id=None,
            with_caption=False, with_uploader_name=False,
            with_has_preview=False, order_by_date=False,
            no_link=False):
        where_extra = []
        select_extra = []
        default_extra = {}

        if reviewer_id is not None:
            if no_link:
                raise Error('reviewer_id specified with no_link')
            where_extra.append(review_fig_link.c.reviewer_id == reviewer_id)

        if no_link:
            default_extra.update({
                'reviewer_id': None,
            })

        else:
            select_extra.extend([
                review_fig_link.c.reviewer_id,
            ])

        return self._search_figure(
            review_fig, (None if no_link else review_fig_link),
            ReviewFigureInfo, ReviewFigureCollection,
            state, link_id, fig_id,
            with_caption, with_uploader_name, order_by_date,
            with_has_preview_table=(
                review_fig_preview if with_has_preview else None),
            select_extra=select_extra, default_extra=default_extra,
            where_extra=where_extra)

    def set_affiliation_weight_note(
            self, call_id, note=None, format_=None,
            _conn=None):
        self._set_note(
            parent_table=call,
            table=affiliation_weight_note,
            key_column=affiliation_weight_note.c.call_id,
            key_value=call_id,
            note=note, format_=format_, _conn=_conn)

    def set_available_note(
            self, call_id, note=None, format_=None,
            _conn=None):
        self._set_note(
            parent_table=call,
            table=available_note,
            key_column=available_note.c.call_id,
            key_value=call_id,
            note=note, format_=format_, _conn=_conn)

    def set_decision(self, proposal_id, accept=(), exempt=None, ready=None,
                     note=None, note_format=None):
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

        decision_id = None

        with self._transaction() as conn:
            proposal = self.get_proposal(
                facility_id=None, proposal_id=proposal_id,
                with_decision=True, _conn=conn)

            if proposal.has_decision:
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

                decision_id = result.inserted_primary_key[0]

        return decision_id

    def set_review(self, role_class, reviewer_id, text, format_,
                   assessment, rating, weight,
                   note, note_format, note_public,
                   state):
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

            # Perform the insert/update.
            if already_exists:
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

    def set_review_figure_preview(self, fig_id, preview):
        self._set_figure_alternate(
            review_fig_preview.c.preview, fig_id, preview)

    def set_review_figure_thumbnail(self, fig_id, thumbnail):
        self._set_figure_alternate(
            review_fig_thumbnail.c.thumbnail, fig_id, thumbnail)

    def set_reviewer_note(
            self, reviewer_id, note=None, format_=None,
            _conn=None):
        self._set_note(
            parent_table=reviewer,
            table=reviewer_note,
            key_column=reviewer_note.c.reviewer_id,
            key_value=reviewer_id,
            note=note, format_=format_, _conn=_conn)

    def _set_note(
            self, parent_table, table, key_column, key_value,
            note, format_, _conn):
        values = {}

        if note is not None:
            if not format_:
                raise UserError('Note format not specified.')
            if not FormatType.is_valid(format_, is_system=True):
                raise UserError('Note format not recognised.')
            values[table.c.note] = note
            values[table.c.note_format] = format_

        if not values:
            raise Error('no note update specified')

        with self._transaction(_conn=_conn) as conn:
            if not self._exists_id(conn, parent_table, key_value):
                raise ConsistencyError(
                    'parent entry does not exist for note with id={}',
                    key_value)

            already_exists = self._exists_note(conn, key_column, key_value)

            if already_exists:
                result = conn.execute(table.update().where(
                    key_column == key_value
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating note for id {}',
                        key_value)

            else:
                values.update({
                    key_column: key_value,
                })

                conn.execute(table.insert().values(values))

    def sync_call_review_deadline(
            self, role_class, call_id, records, _conn=None):
        """
        Update the review deadlines for a call.
        """

        records.validate(role_class)

        with self._transaction(_conn=_conn) as conn:
            if not self._exists_id(conn, call, call_id):
                raise ConsistencyError(
                    'call does not exist with id={}', call_id)

            return self._sync_records(
                conn, review_deadline,
                key_column=review_deadline.c.call_id, key_value=call_id,
                records=records, unique_columns=(review_deadline.c.role,))

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

    def sync_review_figure(self, reviewer_id, records):
        """
        Update the figures for a review.

        Currently only deleting figures and changing the sort order
        is supported.
        """

        records.ensure_sort_order()

        with self._transaction() as conn:
            if not self._exists_id(conn, reviewer, reviewer_id):
                raise ConsistencyError(
                    'reviewer does not exist with id={}', reviewer_id)

            (n_insert, n_update, n_delete) = self._sync_records(
                conn, review_fig_link, review_fig_link.c.reviewer_id, reviewer_id,
                records, update_columns=(
                    review_fig_link.c.sort_order,
                ), forbid_add=True)

            if n_delete:
                self._remove_orphan_records(
                    conn, review_fig, review_fig_link.c.fig_id)

        return (n_insert, n_update, n_delete)

    def update_reviewer(
            self, role_class, reviewer_id,
            notified=None, accepted=()):
        """
        Update the status information of a reviewer record.
        """

        with self._transaction() as conn:
            try:
                reviewer_record = self.search_reviewer(
                    reviewer_id=reviewer_id, _conn=conn).get_single()
            except NoSuchRecord:
                raise ConsistencyError(
                    'reviewer does not exist with id={}', reviewer_id)

            try:
                role_info = role_class.get_info(reviewer_record.role)
            except KeyError:
                raise Error('reviewer has invalid role')

            values = {}

            if notified is not None:
                if role_info.review_group is None:
                    raise Error('reviewer role is not assigned')

                values['notified'] = notified

            if accepted != ():
                if not role_info.accept:
                    raise Error('reviewer role is not accepted')

                values['accepted'] = accepted

            if not values:
                raise Error('no reviewer updates specified')

            result = conn.execute(reviewer.update().where(
                reviewer.c.id == reviewer_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating reviewer with id={}',
                    reveiwer_id)

    def update_reviewer_acceptance(
            self, reviewer_acceptance_id, accepted=None, text=None, format_=None,
            _conn=None):
        if accepted is None:
            raise Error('Accepted flag not specified.')

        if text is None:
            raise Error('Acceptance explanation text not specified.')

        if not format_:
            raise UserError('Text format not specified.')
        if not FormatType.is_valid(format_):
            raise UserError('Text format not recognised.')

        values = {
            reviewer_acceptance.c.accepted: accepted,
            reviewer_acceptance.c.text: text,
            reviewer_acceptance.c.format: format_,
            reviewer_acceptance.c.date: datetime.utcnow(),
        }

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(reviewer_acceptance.update().where(
                reviewer_acceptance.c.id == reviewer_acceptance_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating reviewer acceptance {}',
                    reviewer_acceptance_id)

    def update_review_figure(
            self, reviewer_id, link_id, fig_id=None,
            figure=None, type_=None, filename=None, uploader_person_id=None,
            state=None, state_prev=None, caption=None, state_is_system=False):
        """
        Update the record of a figure attached to a review.

        Can be used to update the figure or the state.

        If the figure is updated, then the type, filename and uploader
        must be specified and the state will be set to NEW -- the state
        must not be specifed explicitly.

        :return: the internal figure ID (not link ID) if it changed,
            for test purposes only
        """

        where_extra = []

        if reviewer_id is not None:
            where_extra.append(review_fig_link.c.reviewer_id == reviewer_id)

        return self._update_figure(
            review_fig, review_fig_link,
            review_fig_preview, review_fig_thumbnail,
            link_id, fig_id, figure, type_, filename, uploader_person_id,
            state, state_prev, caption,
            where_extra=where_extra, state_is_system=state_is_system,
        )

    def _exists_note(self, conn, key_column, key_value):
        """
        Test whether the given note exists.
        """

        return 0 < conn.execute(select([count(key_column)]).where(
            key_column == key_value
        )).scalar()

    def _exists_reviewer(self, conn, proposal_id, role, person_id=None):
        """
        Test whether a reviewer record of the given role already exists
        for a proposal.
        """

        stmt = select([count(reviewer.c.id)]).where(and_(
            reviewer.c.proposal_id == proposal_id,
            reviewer.c.role == role
        ))

        if person_id is not None:
            stmt = stmt.where(reviewer.c.person_id == person_id)

        return 0 < conn.execute(stmt).scalar()

    def _exists_review(self, conn, reviewer_id):
        """
        Test whether a review record by the given reviewer exists.
        """

        return 0 < conn.execute(select([count(review.c.reviewer_id)]).where(
            review.c.reviewer_id == reviewer_id
        )).scalar()
