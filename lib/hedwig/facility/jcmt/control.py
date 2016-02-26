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

from sqlalchemy.sql import select
from sqlalchemy.sql.functions import count

from ...db.meta import call, proposal
from ...error import ConsistencyError
from .meta import jcmt_available, jcmt_allocation, jcmt_options, jcmt_request
from .type import \
    JCMTAvailable, JCMTAvailableCollection, \
    JCMTOptions, JCMTRequest, JCMTRequestCollection


class JCMTPart(object):
    def get_jcmt_options(self, proposal_id):
        """
        Retrieve the JCMT proposal options for a given proposal.
        """

        with self._transaction() as conn:
            row = conn.execute(jcmt_options.select().where(
                jcmt_options.c.proposal_id == proposal_id)).first()

            if row is None:
                return None

            else:
                return JCMTOptions(**row)

    def search_jcmt_allocation(self, proposal_id):
        """
        Retrieve the observing allocations for the given proposal.
        """

        ans = JCMTRequestCollection()

        stmt = jcmt_allocation.select().where(
            jcmt_allocation.c.proposal_id == proposal_id)

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(jcmt_allocation.c.id.asc())):
                ans[row['id']] = JCMTRequest(**row)

        return ans

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
                ans[row['id']] = JCMTAvailable(**row)

        return ans

    def search_jcmt_request(self, proposal_id):
        """
        Retrieve the observing requests for the given proposal.
        """

        ans = JCMTRequestCollection()

        stmt = jcmt_request.select().where(
            jcmt_request.c.proposal_id == proposal_id)

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(jcmt_request.c.id.asc())):
                ans[row['id']] = JCMTRequest(**row)

        return ans

    def set_jcmt_options(self, proposal_id, target_of_opp, daytime,
                         time_specific, polarimetry):
        """
        Set the JCMT proposal options for a given proposal.
        """

        values = {
            jcmt_options.c.target_of_opp: target_of_opp,
            jcmt_options.c.daytime: daytime,
            jcmt_options.c.time_specific: time_specific,
            jcmt_options.c.polarimetry: polarimetry,
        }

        with self._transaction() as conn:
            if 0 < conn.execute(select(
                    [count(jcmt_options.c.proposal_id)]).where(
                        jcmt_options.c.proposal_id == proposal_id)).scalar():
                # Update existing options.
                result = conn.execute(jcmt_options.update().where(
                    jcmt_options.c.proposal_id == proposal_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating JCMT options')

            else:
                # Add new options record.
                values.update({
                    jcmt_options.c.proposal_id: proposal_id,
                })

                conn.execute(jcmt_options.insert().values(values))

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

    def sync_jcmt_proposal_allocation(self, proposal_id, records,
                                      _test_skip_check=False):
        """
        Update the observing allocations for the given proposal to match
        the specified records.
        """

        records.validate()

        with self._transaction() as conn:
            if not _test_skip_check and \
                    not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            return self._sync_records(
                conn, jcmt_allocation, jcmt_allocation.c.proposal_id,
                proposal_id, records, unique_columns=(
                    jcmt_allocation.c.instrument, jcmt_allocation.c.weather))

    def sync_jcmt_proposal_request(self, proposal_id, records,
                                   _test_skip_check=False):
        """
        Update the observing requests for the given proposal to match
        the specified records.
        """

        records.validate()

        with self._transaction() as conn:
            if not _test_skip_check and \
                    not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            return self._sync_records(
                conn, jcmt_request, jcmt_request.c.proposal_id, proposal_id,
                records, unique_columns=(
                    jcmt_request.c.instrument, jcmt_request.c.weather))
