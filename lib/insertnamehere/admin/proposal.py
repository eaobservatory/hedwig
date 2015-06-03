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

import logging

from ..error import NoSuchRecord, UserError
from ..type import MemberInstitution, ProposalState

logger = logging.getLogger(__name__)


def close_call_proposals(db, call_id):
    """
    Function to update the status of proposals at the closure of a
    call.

    * Sets the status to REVIEW (or ABANDONED if not submitted).
    * Writes the member institutions into the member table.
    """

    try:
        call = db.search_call(call_id=call_id, is_open=False).get_single()
    except NoSuchRecord:
        raise UserError('Call with id={0} not found or still open.',
                        call_id)

    for proposal in db.search_proposal(call_id=call_id).values():
        # Change the proposal state.
        new_state = None

        if proposal.state == ProposalState.SUBMITTED:
            new_state = ProposalState.REVIEW

        elif proposal.state in (ProposalState.PREPARATION,
                                ProposalState.WITHDRAWN):
            new_state = ProposalState.ABANDONED

        if new_state is not None:
            logger.info('Setting state of proposal %i to %s',
                        proposal.id, ProposalState.get_name(new_state))
            db.update_proposal(proposal.id, state=new_state)
        else:
            logger.warning('Proposal %i is in unexpected state "%s"',
                           proposal.id, ProposalState.get_name(proposal.state))

        # Freeze the current institution ID values in the member table.
        records = {}
        for member in db.search_member(proposal_id=proposal.id).values():
            records[member.id] = MemberInstitution(
                member.id, member.resolved_institution_id)

        logger.debug('Synchronizing institution_id values into member table')
        db.sync_proposal_member_institution(proposal.id, records)
