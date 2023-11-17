# Copyright (C) 2017-2023 East Asian Observatory
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
from ...type.enum import FormatType
from ...util import is_list_like
from .meta import \
    ukirt_allocation, ukirt_request
from .type import \
    UKIRTRequest, UKIRTRequestCollection


class UKIRTPart(object):
    def search_ukirt_allocation(self, proposal_id):
        """
        Retrieve observing allocations for the given proposal.
        """

        iter_field = None
        iter_list = None

        stmt = ukirt_allocation.select()

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = ukirt_allocation.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(
                    ukirt_allocation.c.proposal_id == proposal_id)

        ans = UKIRTRequestCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(ukirt_allocation.c.id.asc())):
                    ans[row.id] = UKIRTRequest(**row_as_mapping(row))

        return ans

    def search_ukirt_request(self, proposal_id):
        """
        Retrieve observing requests for a the given propsoal.
        """

        iter_field = None
        iter_list = None

        stmt = ukirt_request.select()

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = ukirt_request.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(
                    ukirt_request.c.proposal_id == proposal_id)

        ans = UKIRTRequestCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(ukirt_request.c.id.asc())):
                    ans[row.id] = UKIRTRequest(**row_as_mapping(row))

        return ans

    def sync_ukirt_proposal_allocation(self, proposal_id, records,
                                       _test_skip_check=False):
        """
        Update the observing allocations for the given proposal.
        """

        records.validate()

        with self._transaction() as conn:
            if not _test_skip_check and \
                    not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            return self._sync_records(
                conn, ukirt_allocation, ukirt_allocation.c.proposal_id,
                proposal_id, records, unique_columns=(
                    ukirt_allocation.c.instrument,
                    ukirt_allocation.c.brightness))

    def sync_ukirt_proposal_request(self, proposal_id, records,
                                    _test_skip_check=False):
        """
        Update the observing requests for the given proposal.
        """

        records.validate()

        with self._transaction() as conn:
            if not _test_skip_check and \
                    not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            return self._sync_records(
                conn, ukirt_request, ukirt_request.c.proposal_id,
                proposal_id, records, unique_columns=(
                    ukirt_request.c.instrument,
                    ukirt_request.c.brightness))
