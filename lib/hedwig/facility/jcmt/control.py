# Copyright (C) 2015-2024 East Asian Observatory
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

from sqlalchemy.sql.functions import count

from ...db.compat import row_as_mapping, select
from ...db.meta import call, proposal, reviewer
from ...error import ConsistencyError, FormattedError, UserError
from ...type.collection import ResultCollection
from ...type.enum import FormatType, ReviewState
from ...util import is_list_like
from .meta import jcmt_available, jcmt_alloc_options, jcmt_allocation, \
    jcmt_call_options, jcmt_options, \
    jcmt_request, jcmt_review
from .type import \
    JCMTAvailable, JCMTAvailableCollection, JCMTCallOptions, \
    JCMTOptions, JCMTOptionsCollection, \
    JCMTPeerReviewerExpertise, JCMTPeerReviewRating, \
    JCMTRequest, JCMTRequestCollection, \
    JCMTReview, JCMTReviewerExpertise, \
    JCMTReviewRatingJustification, JCMTReviewRatingTechnical, \
    JCMTReviewRatingUrgency


class JCMTPart(object):
    def get_jcmt_alloc_options(self, proposal_id):
        """
        Retrieve the JCMT allocation options for a given proposal.
        """

        return self.search_jcmt_alloc_options(
            proposal_id=proposal_id).get_single()

    def get_jcmt_call_options(self, call_id):
        """
        Retrieve the JCMT call options for a given call.
        """

        return self.search_jcmt_call_options(
            call_id=call_id).get_single()

    def get_jcmt_options(self, proposal_id):
        """
        Retrieve the JCMT proposal options for a given proposal.
        """

        return self.search_jcmt_options(
            proposal_id=proposal_id).get_single()

    def get_jcmt_review(self, reviewer_id):
        """
        Retrieve the JCMT-specific parts of a review.
        """

        return self.search_jcmt_review(reviewer_id=reviewer_id).get_single()

    def search_jcmt_alloc_options(self, proposal_id=None):
        """
        Retrieve JCMT allocation options for one or more proposals.
        """

        return self._search_jcmt_prop_alloc_opt(
            jcmt_alloc_options, proposal_id=proposal_id)

    def search_jcmt_allocation(self, proposal_id):
        """
        Retrieve the observing allocations for the given proposal.
        """

        return self._search_jcmt_req_alloc(jcmt_allocation, proposal_id)

    def search_jcmt_available(self, call_id):
        """
        Retrieve information about the observing time available (normally
        for a given call for proposals).
        """

        stmt = jcmt_available.select()

        if call_id is not None:
            stmt = stmt.where(jcmt_available.c.call_id == call_id)

        ans = JCMTAvailableCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(jcmt_available.c.id.asc())):
                ans[row.id] = JCMTAvailable(**row_as_mapping(row))

        return ans

    def search_jcmt_call_options(self, call_id=None):
        """
        Retrieve JCMT options for one or more calls.
        """

        iter_field = None
        iter_list = None

        stmt = jcmt_call_options.select()

        if call_id is not None:
            if is_list_like(call_id):
                assert iter_field is None
                iter_field = jcmt_call_options.c.call_id
                iter_list = call_id
            else:
                stmt = stmt.where(jcmt_call_options.c.call_id == call_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt):
                    ans[row.call_id] = JCMTCallOptions(**row_as_mapping(row))

        return ans

    def search_jcmt_options(self, proposal_id=None):
        """
        Retrieve JCMT options for one or more proposals.
        """

        return self._search_jcmt_prop_alloc_opt(
            jcmt_options, proposal_id=proposal_id)

    def _search_jcmt_prop_alloc_opt(self, table, proposal_id):
        iter_field = None
        iter_list = None

        stmt = table.select()

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = table.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(table.c.proposal_id == proposal_id)

        ans = JCMTOptionsCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt):
                    ans[row.proposal_id] = JCMTOptions(**row_as_mapping(row))

        return ans

    def search_jcmt_request(self, proposal_id):
        """
        Retrieve the observing requests for the given proposal.
        """

        return self._search_jcmt_req_alloc(jcmt_request, proposal_id)

    def _search_jcmt_req_alloc(self, table, proposal_id):
        """
        Common method to search for either requests or allocations.
        """

        iter_field = None
        iter_list = None

        stmt = table.select()

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = table.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(table.c.proposal_id == proposal_id)

        ans = JCMTRequestCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(table.c.id.asc())):
                    ans[row.id] = JCMTRequest(**row_as_mapping(row))

        return ans

    def search_jcmt_review(self, reviewer_id=None, proposal_id=None):
        """
        Search for JCMT review entries.
        """

        stmt = jcmt_review.select()
        select_from = jcmt_review

        iter_field = None
        iter_list = None

        if reviewer_id is not None:
            if is_list_like(reviewer_id):
                assert iter_field is None
                iter_field = jcmt_review.c.reviewer_id
                iter_list = reviewer_id
            else:
                stmt = stmt.where(jcmt_review.c.reviewer_id == reviewer_id)

        if proposal_id is not None:
            select_from = select_from.join(reviewer)

            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = reviewer.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(reviewer.c.proposal_id == proposal_id)

        stmt = stmt.select_from(select_from)

        ans = ResultCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt):
                    ans[row.reviewer_id] = JCMTReview(*row)

        return ans

    def set_jcmt_alloc_options(self, proposal_id, **kwargs):
        """
        Set the JCMT proposal options for a given proposal.
        """

        self._set_jcmt_prop_alloc_opt(
            jcmt_alloc_options, proposal_id, **kwargs)

    def set_jcmt_call_options(
            self, call_id, time_min, time_max, time_excl_free):
        """
        Set the JCMT options for a given call.
        """

        if (time_min is not None) and (time_max is not None):
            if time_min > time_max:
                raise UserError(
                    'Minimum observing request time is greater than maximum.')

        values = {
            jcmt_call_options.c.time_min: time_min,
            jcmt_call_options.c.time_max: time_max,
            jcmt_call_options.c.time_excl_free: time_excl_free,
        }

        with self._transaction() as conn:
            if 0 < conn.execute(select(
                    [count(jcmt_call_options.c.call_id)]).where(
                        jcmt_call_options.c.call_id == call_id)).scalar():
                # Update existing call options.
                result = conn.execute(jcmt_call_options.update().where(
                    jcmt_call_options.c.call_id == call_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating JCMT options')

            else:
                # Add new call options record.
                values.update({
                    jcmt_call_options.c.call_id: call_id,
                })

                conn.execute(jcmt_call_options.insert().values(values))

    def set_jcmt_options(self, proposal_id, **kwargs):
        """
        Set the JCMT proposal options for a given proposal.
        """

        self._set_jcmt_prop_alloc_opt(
            jcmt_options, proposal_id, **kwargs)

    def _set_jcmt_prop_alloc_opt(
            self, table, proposal_id,
            target_of_opp=None, daytime=None, time_specific=None,
            polarimetry=None):
        values = {
            table.c.target_of_opp: target_of_opp,
            table.c.daytime: daytime,
            table.c.time_specific: time_specific,
            table.c.polarimetry: polarimetry,
        }

        with self._transaction() as conn:
            if 0 < conn.execute(select(
                    [count(table.c.proposal_id)]).where(
                        table.c.proposal_id == proposal_id)).scalar():
                # Update existing options.
                result = conn.execute(table.update().where(
                    table.c.proposal_id == proposal_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating JCMT options')

            else:
                # Add new options record.
                values.update({
                    table.c.proposal_id: proposal_id,
                })

                conn.execute(table.insert().values(values))

    def set_jcmt_review(
            self, role_class, reviewer_id, review_state, review):
        state_done = (review_state == ReviewState.DONE)

        if review.expertise is not None:
            if not JCMTReviewerExpertise.is_valid(review.expertise):
                raise UserError('Reviewer expertise level not recognised.')

        if review.rating_justification is not None:
            if not JCMTReviewRatingJustification.is_valid(
                    review.rating_justification):
                raise UserError('Justification rating not recognised.')

        if review.rating_technical is not None:
            if not JCMTReviewRatingTechnical.is_valid(review.rating_technical):
                raise UserError('Technical rating not recognised.')

        if review.rating_urgency is not None:
            if not JCMTReviewRatingUrgency.is_valid(review.rating_urgency):
                raise UserError('Urgency rating not recognised.')

        if review.review_format is not None:
            if not FormatType.is_valid(review.review_format):
                raise UserError('Question response format not recognised.')

        if review.peer_expertise is not None:
            if not JCMTPeerReviewerExpertise.is_valid(review.peer_expertise):
                raise UserError('Expertise level not recognised.')

        if review.peer_rating is not None:
            if not JCMTPeerReviewRating.is_valid(review.peer_rating):
                raise UserError('Rating value not recognised.')

        values = {
            x: getattr(review, x.name)
            for x in jcmt_review.columns if x.name != 'reviewer_id'}

        with self._transaction() as conn:
            # Determine type of review and check values are valid for it.
            reviewer = self.search_reviewer(
                reviewer_id=reviewer_id, _conn=conn).get_single()

            role_info = role_class.get_info(reviewer.role)
            attr_req = {
                jcmt_review.c.expertise: role_info.jcmt_expertise,
                jcmt_review.c.review_aims: role_info.jcmt_external,
                jcmt_review.c.review_goals: (None if role_info.jcmt_external else False),
                jcmt_review.c.review_analysis: role_info.jcmt_external,
                jcmt_review.c.review_difficulties: role_info.jcmt_external,
                jcmt_review.c.rating_justification: role_info.jcmt_external,
                jcmt_review.c.review_details: role_info.jcmt_external,
                jcmt_review.c.review_obj_inst: role_info.jcmt_external,
                jcmt_review.c.review_telescope: role_info.jcmt_external,
                jcmt_review.c.rating_technical: role_info.jcmt_external,
                jcmt_review.c.rating_urgency: role_info.jcmt_external,
                jcmt_review.c.review_format: role_info.jcmt_external,
                jcmt_review.c.peer_expertise: role_info.jcmt_peer_expertise,
                jcmt_review.c.peer_rating: role_info.jcmt_peer_rating,
            }

            for (attr, attr_allowed) in attr_req.items():
                if attr_allowed:
                    # Check for missing attributes only if review is done.
                    if state_done and (values[attr] is None):
                        raise FormattedError(
                            '{} should be specified', attr.name)

                elif attr_allowed is None:
                    # Attribute is optional.
                    pass

                else:
                    if values[attr] is not None:
                        raise FormattedError(
                            '{} should not be specified', attr.name)

            # Check if the review already exists.
            already_exists = self._exists_jcmt_review(
                conn, reviewer_id=reviewer_id)

            # Perform the insert/update.
            if already_exists:
                result = conn.execute(jcmt_review.update().where(
                    jcmt_review.c.reviewer_id == reviewer_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating JCMT review {}', reviewer_id)

            else:
                values.update({
                    jcmt_review.c.reviewer_id: reviewer_id,
                })

                result = conn.execute(jcmt_review.insert().values(values))

    def sync_jcmt_call_available(self, call_id, records,
                                 _test_skip_check=False):
        """
        Update the records of the amount of time available for a call.
        """

        records.validate()

        with self._transaction() as conn:
            if not _test_skip_check and \
                    not self._exists_id(conn, call, call_id):
                raise ConsistencyError(
                    'call does not exist with id={}', call_id)

            return self._sync_records(
                conn, jcmt_available, jcmt_available.c.call_id, call_id,
                records, unique_columns=(jcmt_available.c.weather,))

    def sync_jcmt_proposal_allocation(
            self, proposal_id, records, _test_skip_check=False):
        """
        Update the observing allocations for the given proposal to match
        the specified records.
        """

        return self._sync_jcmt_proposal_alloc_req(
            jcmt_allocation, proposal_id, records, _test_skip_check)

    def sync_jcmt_proposal_request(
            self, proposal_id, records, _test_skip_check=False):
        """
        Update the observing requests for the given proposal to match
        the specified records.
        """

        return self._sync_jcmt_proposal_alloc_req(
            jcmt_request, proposal_id, records, _test_skip_check)

    def _sync_jcmt_proposal_alloc_req(
            self, table, proposal_id, records, _test_skip_check):
        """
        Common method to sync either requests or allocations.
        """

        records.validate()

        with self._transaction() as conn:
            if not _test_skip_check and \
                    not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            return self._sync_records(
                conn, table, table.c.proposal_id, proposal_id,
                records, unique_columns=(
                    table.c.instrument, table.c.ancillary, table.c.weather))

    def _exists_jcmt_review(self, conn, reviewer_id):
        """
        Test whether a JCMT review record exists.
        """

        return 0 < conn.execute(select([
            count(jcmt_review.c.reviewer_id)
        ]).where(
            jcmt_review.c.reviewer_id == reviewer_id
        )).scalar()
