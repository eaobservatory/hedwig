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

from collections import defaultdict

from ..type import ProposalState, ReviewerRole
from .proposal import send_call_proposal_feedback


def send_proposal_feedback(db):
    """
    Send feedback for proposals when have been reviewed.

    Finds proposals which are:

        * In the REVIEW state.
        * Have decisions "ready".

    and then groups the proposals by call and passes them to send_call_feedback
    so that the feedback email messages can include aggregate information about
    the call.
    """

    proposals = db.search_proposal(
        state=ProposalState.REVIEW, with_members=True,
        with_reviewers=True, with_review_info=True, with_review_text=True,
        with_review_state=True, with_reviewer_role=ReviewerRole.FEEDBACK,
        with_decision=True, decision_ready=True)

    # Organise the proposals by call.
    calls = defaultdict(list)

    for proposal in proposals.values():
        calls[proposal.call_id].append(proposal)

    n_processed = 0

    for (call_id, call_proposals) in calls.items():
        n_processed += send_call_proposal_feedback(db, call_id, call_proposals)

    return n_processed
