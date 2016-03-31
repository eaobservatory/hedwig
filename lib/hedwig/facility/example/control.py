# Copyright (C) 2016 East Asian Observatory
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

from __future__ import \
    absolute_import, division, print_function, \
    unicode_literals

from ...type.collection import ResultCollection
from ...db.meta import proposal
from .meta import example_request
from .type import ExampleRequest


class ExamplePart(object):
    def search_example_request(
            self, proposal_id):
        """
        Retrieve observing requests
        for the given proposal.
        """

        stmt = example_request.select().where(
            example_request.c.proposal_id == proposal_id
        ).order_by(example_request.c.id.asc())

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                ans[row['id']] = ExampleRequest(**row)

        return ans

    def sync_example_proposal_request(
            self, proposal_id, records):
        """
        Update the observing requests
        for the given proposal.
        """

        with self._transaction() as conn:
            return self._sync_records(
                conn,
                example_request,
                example_request.c.proposal_id,
                proposal_id,
                records,
                unique_columns=(
                    example_request.c.instrument,))
