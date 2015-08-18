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

from ..error import NoSuchRecord
from ..web.util import HTTPForbidden, HTTPNotFound
from . import auth


class BaseTargetTool(object):
    def __init__(self, facility, id_):
        self.facility = facility
        self.id_ = id_

    def get_custom_routes(self):
        """
        Method used to find any custom routes required by this tool.

        Returns a list of (template, rule, endpoint, view_func, options)
        tuples.
        """

        return []

    def view_proposal(self, db, proposal_id, args):
        try:
            proposal = db.get_proposal(self.facility.id_, proposal_id,
                                       with_members=True)
        except NoSuchRecord:
            raise HTTPNotFound('Proposal not found')

        assert proposal.id == proposal_id

        if not auth.for_proposal(db, proposal).view:
            raise HTTPForbidden('Permission denied for this proposal.')

        targets = db.search_target(proposal_id=proposal_id)

        ctx = self._view_proposal(db, proposal, targets, args)

        ctx.update({
            'proposal_id': proposal.id,
            'proposal_code': self.facility.make_proposal_code(db, proposal),
        })

        return ctx
