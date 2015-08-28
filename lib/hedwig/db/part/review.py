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

from datetime import datetime

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_
from sqlalchemy.sql.functions import count

from ...error import ConsistencyError, Error, FormattedError, \
    NoSuchRecord, UserError
from ...type import Assessment, FormatType, \
    GroupMember, GroupMemberCollection, GroupType, \
    NoteRole, ProposalNote, Reviewer, ReviewerCollection, ReviewerRole
from ..meta import group_member, institution, person, \
    proposal, proposal_note, queue, \
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

    def add_reviewer(self, proposal_id, person_id, role,
                     _test_skip_check=False, _conn=None):
        try:
            role_info = ReviewerRole.get_info(role)
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

    def delete_reviewer(self, reviewer_id, delete_review=False):
        """
        Delete a reviewer record from the database.

        This can, optionally, also delete any associated review.  This
        is because, in the database, review.reviewer references
        reviewer.id with "ondelete" set to restrict.  (We don't want
        to accidentally delete reviews when working with th reviewer table.)
        The option allows the deletion to be "cascaded" manually when
        necessary.
        """

        with self._transaction() as conn:
            if delete_review:
                result = conn.execute(review.delete().where(
                    review.c.reviewer_id == reviewer_id))
                if result.rowcount > 1:
                    raise ConsistencyError(
                        'multiple rows matched deleting reviews by {}',
                        reviewer_id)

            result = conn.execute(reviewer.delete().where(
                reviewer.c.id == reviewer_id))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting reviewer {}', reviewer_id)

    def get_proposal_note(self, proposal_id, role):
        """
        Get the given review process note associated with a proposal.
        """

        if not NoteRole.is_valid(role):
            raise Error('invalid note role')

        with self._transaction() as conn:
            row = conn.execute(proposal_note.select().where(and_(
                proposal_note.c.proposal_id == proposal_id,
                proposal_note.c.role == role
            ))).first()

        if row is None:
            raise NoSuchRecord('note does not exist for {} role {}',
                               proposal_id, role)

        return ProposalNote(**row)

    def search_group_member(self, queue_id=None, group_type=None,
                            person_id=None, facility_id=None,
                            with_person=False, _conn=None):
        select_from = group_member

        if facility_id is not None:
            select_from = select_from.join(queue)

        if with_person:
            stmt = select([
                group_member,
                person.c.name.label('person_name'),
                person.c.public.label('person_public'),
                (person.c.user_id.isnot(None)).label('person_registered'),
                institution.c.name.label('institution_name'),
                institution.c.department.label('institution_department'),
                institution.c.organization.label('institution_organization'),
                institution.c.country.label('institution_country'),
            ])

            select_from = select_from.join(person).outerjoin(institution)

            default = None
        else:
            stmt = group_member.select()

            default = {
                'person_name': None,
                'person_public': None,
                'person_registered': None,
                'institution_name': None,
                'institution_department': None,
                'institution_organization': None,
                'institution_country': None,
            }

        stmt = stmt.select_from(select_from)

        if queue_id is not None:
            stmt = stmt.where(group_member.c.queue_id == queue_id)

        if group_type is not None:
            stmt = stmt.where(group_member.c.group_type == group_type)

        if person_id is not None:
            stmt = stmt.where(group_member.c.person_id == person_id)

        if facility_id is not None:
            stmt = stmt.where(queue.c.facility_id == facility_id)

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

    def search_reviewer(self, proposal_id=None, role=None, reviewer_id=None,
                        with_review=False, with_review_text=False,
                        _conn=None):
        select_columns = [
            reviewer,
            person.c.name.label('person_name'),
            person.c.public.label('person_public'),
            (person.c.user_id.isnot(None)).label('person_registered'),
            institution.c.name.label('institution_name'),
            institution.c.department.label('institution_department'),
            institution.c.organization.label('institution_organization'),
            institution.c.country.label('institution_country'),
        ]

        select_from = reviewer.join(person).outerjoin(institution)

        if with_review:
            select_columns.append(
                (review.c.reviewer_id.isnot(None)).label('review_present'))

            select_columns.extend((x.label('review_{}'.format(x.name))
                                   for x in review.columns
                                   if x not in (review.c.reviewer_id,
                                                review.c.text)))

            if with_review_text:
                select_columns.append(review.c.text.label('review_text'))
                default = {}

            else:
                default = {'review_text': None}

            select_from = select_from.outerjoin(review)

        else:
            default = {'review_{}'.format(x.name): None
                       for x in review.columns if x != review.c.reviewer_id}

            default['review_present'] = None

        stmt = select(select_columns).select_from(select_from)

        if proposal_id is not None:
            stmt = stmt.where(reviewer.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(reviewer.c.role == role)

        if reviewer_id is not None:
            stmt = stmt.where(reviewer.c.id == reviewer_id)

        ans = ReviewerCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(reviewer.c.id)):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = Reviewer(**values)

        return ans

    def set_proposal_note(self, proposal_id, role, text, format_, is_update,
                          _test_skip_check=False):
        if not NoteRole.is_valid(role):
            raise Error('invalid note role')

        if not format_:
            raise UserError('Text format not specified.')
        if not FormatType.is_valid(format_):
            raise UserError('Text format not recognised.')

        with self._transaction() as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, proposal, proposal_id):
                    raise ConsistencyError('proposal does not exist with id={}',
                                           proposal_id)

                already_exists = self._exists_proposal_note(
                    conn, proposal_id, role)
                if is_update and not already_exists:
                    raise ConsistencyError(
                        'note does not exist for proposal {} role {}',
                        proposal_id, role)
                elif already_exists and not is_update:
                    raise ConsistencyError(
                        'note already exists for proposal {} role {}',
                        proposal_id, role)

            values = {
                proposal_note.c.text: text,
                proposal_note.c.format: format_,
                proposal_note.c.edited: datetime.utcnow(),
            }

            if is_update:
                result = conn.execute(proposal_note.update().where(and_(
                    proposal_note.c.proposal_id == proposal_id,
                    proposal_note.c.role == role
                )).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating proposal text {} role {}',
                        proposal_id, role)

            else:
                values.update({
                    proposal_note.c.proposal_id: proposal_id,
                    proposal_note.c.role: role,
                })

                result = conn.execute(proposal_note.insert().values(values))

    def set_review(self, reviewer_id, text, format_,
                   assessment, rating, weight,
                   is_update):
        if text is not None:
            if not format_:
                raise UserError('Text format not specified.')
            if not FormatType.is_valid(format_):
                raise UserError('Text format not recognised.')

        if assessment is not None:
            if not Assessment.is_valid(assessment):
                raise UserError('Assessment value not recognised.')

        values = {
            review.c.text: text,
            review.c.format: (None if text is None else format_),
            review.c.assessment: assessment,
            review.c.rating: rating,
            review.c.weight: weight,
            review.c.edited: datetime.utcnow(),
        }

        with self._transaction() as conn:
            # Find out what type of review this is so that we can
            # determine which attributes are appropriate.
            reviewer = self.search_reviewer(reviewer_id=reviewer_id,
                                            _conn=conn).get_single()

            role_info = ReviewerRole.get_info(reviewer.role)
            attr_values = {k.name: v for (k, v) in values.items()}

            for attr in ('text', 'assessment', 'rating', 'weight'):
                if getattr(role_info, attr):
                    if attr_values[attr] is None:
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
                    review.c.reviewer_id == reviewer_id,
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

    def _exists_proposal_note(self, conn, proposal_id, role):
        """
        Test whether a note of the given role already exists for a proposal.
        """

        return 0 < conn.execute(select([count(proposal_note.c.id)]).where(and_(
            proposal_note.c.proposal_id == proposal_id,
            proposal_note.c.role == role
        ))).scalar()

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
            review.c.reviewer_id == reviewer_id,
        )).scalar()
