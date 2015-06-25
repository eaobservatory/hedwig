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

from ...db.meta import proposal
from .meta import jcmt_request
from .type import JCMTRequest, JCMTRequestCollection


class JCMTPart(object):
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
                    'proposal does not exist with id={0}', proposal_id)

            return self._sync_records(
                conn, jcmt_request, jcmt_request.c.proposal_id, proposal_id,
                records)
