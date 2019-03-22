# Copyright (C) 2015-2019 East Asian Observatory
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
from datetime import datetime, timedelta

from ..config import get_config
from ..type.enum import BaseReviewerRole, ProposalState, ReviewState
from ..util import get_logger
from .proposal import close_call_proposals, close_mid_call, \
    send_call_proposal_feedback

logger = get_logger(__name__)


def close_completed_call(db, dry_run=False, _test_date=None):
    """
    Close calls for which the submission deadline has passed.
    """

    deadline = _closure_deadline() if _test_date is None else _test_date

    n_closed = 0

    for call_id in db.search_call(
            date_close_before=_closure_deadline(),
            has_proposal_state=ProposalState.open_states()):
        try:
            close_call_proposals(db=db, call_id=call_id, dry_run=dry_run)

            n_closed += 1

        except:
            logger.exception('Error closing call {}', call_id)

    return n_closed


def close_completed_mid_call(db, dry_run=False, _test_date=None):
    """
    Process intermediate call closures.
    """

    deadline = _closure_deadline() if _test_date is None else _test_date

    n_closed = 0

    for mid_close in db.search_call_mid_close(
            closed=False, date_before=deadline).values():
        try:
            close_mid_call(
                db=db, call_id=mid_close.call_id, mid_close_id=mid_close.id,
                dry_run=dry_run)

            n_closed += 1

        except:
            logger.exception(
                'Error closing intermediate call {}', mid_close.id)

    return n_closed


def _closure_deadline():
    """
    Get the closure deadline for use in finding calls to close.

    This returns the current UT time less the configured grade period.
    """

    grace_period = timedelta(
        minutes=int(get_config().get('application', 'grace_period')))

    return (datetime.utcnow() - grace_period)


def send_proposal_feedback(db, dry_run=False):
    """
    Send feedback for proposals when have been reviewed.

    Finds proposals which:

        * Are in the FINAL_REVIEW state.
        * Have decisions defined and marked "ready".

    and then groups the proposals by call and passes them to send_call_feedback
    so that the feedback email messages can include aggregate information about
    the call.
    """

    proposals = db.search_proposal(
        state=ProposalState.FINAL_REVIEW, with_members=True,
        with_reviewers=True, with_review_info=True, with_review_text=True,
        with_review_state=ReviewState.DONE,
        with_reviewer_role=BaseReviewerRole.FEEDBACK,
        with_decision=True, with_decision_note=True,
        decision_ready=True, decision_accept_defined=True)

    # Organise the proposals by call.
    calls = defaultdict(list)

    for proposal in proposals.values():
        calls[proposal.call_id].append(proposal)

    n_processed = 0

    for (call_id, call_proposals) in calls.items():
        n_processed += send_call_proposal_feedback(db, call_id, call_proposals,
                                                   dry_run=dry_run)

    return n_processed
