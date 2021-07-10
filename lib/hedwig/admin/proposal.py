# Copyright (C) 2015-2021 East Asian Observatory
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

from ..config import get_facilities
from ..email.format import render_email_template
from ..error import ConsistencyError, FormattedError, NoSuchRecord, UserError
from ..stats.quartile import label_quartiles
from ..type.enum import CallState, FormatType, ProposalState, ReviewState
from ..type.simple import MemberInstitution
from ..util import get_logger

logger = get_logger(__name__)


class FeedbackError(FormattedError):
    pass


def close_call_proposals(db, call_id, dry_run=False):
    """
    Function to update the status of proposals at the closure of a
    call.

    * Sets the status to REVIEW (or ABANDONED if not submitted).
    * Freezes proposal member institutions.
    * Writes the member institutions into the member table.
    """

    logger.debug('Preparing to close call {}', call_id)

    try:
        call = db.search_call(
            call_id=call_id, state=CallState.CLOSED).get_single()
    except NoSuchRecord:
        raise UserError('Call with id={} not found or not closed.', call_id)

    # Determine if the call has intermediate closing.  It would be simplest
    # to check the call type info mid_close attribute, but we may not have
    # loaded the facility view class.  We just use this to know whether to
    # expect proposals already to be in various submitted states.
    has_mid_close = True if db.search_call_mid_close(
        call_id=call_id) else False

    n_closed = 0

    for proposal in db.search_proposal(call_id=call_id,
                                       with_members=True).values():
        logger.debug('Closing call {} proposal {}', call_id, proposal.id)

        # Change the proposal state.
        new_state = None

        if proposal.state == ProposalState.SUBMITTED:
            new_state = ProposalState.REVIEW

        elif proposal.state in (ProposalState.PREPARATION,
                                ProposalState.WITHDRAWN):
            new_state = ProposalState.ABANDONED

        elif has_mid_close and (
                proposal.state in ProposalState.submitted_states()):
            # The proposal is in another submitted state, but this is a call
            # with intermediate close dates, so that can happen.
            continue

        if new_state is None:
            # If the proposal is in an unexpected state, issue a warning
            # and skip to the next proposal.  (We don't want a poll process
            # to repeatedly perform the member institution freezing step.)
            logger.warning('Proposal {} is in unexpected state "{}"',
                           proposal.id, ProposalState.get_name(proposal.state))
            continue

        _close_proposal(db, proposal, new_state, dry_run=dry_run)

        n_closed += 1

    return n_closed


def close_mid_call(db, call_id, mid_close_id, dry_run=False):
    """
    Function to process an intermediate closure for a call.

    * Sets the status of SUBMITTED proposals to REVIEW.
    * Freezes proposal member institutions.
    * Marks the intermediate closure as closed.
    """

    logger.debug(
        'Preparing to perform intermediate closure {} for call {}',
        mid_close_id, call_id)

    n_closed = 0

    for proposal in db.search_proposal(
            call_id=call_id, state=ProposalState.SUBMITTED,
            with_members=True).values():
        logger.debug('Closing call {} proposal {}', call_id, proposal.id)

        _close_proposal(db, proposal, ProposalState.REVIEW, dry_run=dry_run)

        n_closed += 1

    if not dry_run:
        db.update_call_mid_close(mid_close_id, closed=True)

    return n_closed


def _close_proposal(db, proposal, new_state, dry_run=False):
    try:
        logger.info('Setting state of proposal {} to {}',
                    proposal.id, ProposalState.get_name(new_state))

        if not dry_run:
            db.update_proposal(proposal.id, state=new_state,
                               state_prev=proposal.state)

        # Freeze the current institution ID values in the member table.
        records = {}
        for member in proposal.members.values():
            records[member.id] = MemberInstitution(
                member.id, member.resolved_institution_id)

        logger.debug('Sync institution IDs into proposal {} member table',
                     proposal.id)
        if not dry_run:
            db.sync_proposal_member_institution(proposal.id, records)

    except ConsistencyError:
        logger.exception(
            'Consistency error closing call for proposal {}',
            proposal.id)


def finalize_call_review(db, call_id, proposals=None):
    """
    Function to update the status of proposals at the closure of a
    review process, prior to the final decision making process
    of the time allocation committee.

    * Sets the status to FINAL_REVIEW.

    :param db: database access object
    :param call_id: identifer of call to update
    :param proposals: list of Proposal objects when individual proposals
        are to be selected.  If this is not specified, then all proposals
        for the given call are updated.

    .. note::
        This function simply sets the state of the corresponding proposals,
        so it can be used from the web interface.  If it ever needs to do
        more work than this, it should be run offline in the poll process
        and gain logger output.  An alternative way to specify individual
        proposals may also be required.
    """

    n_update = 0
    n_error = 0

    if proposals is None:
        proposals = db.search_proposal(
            call_id=call_id, state=ProposalState.REVIEW).values()

    for proposal in proposals:
        try:
            db.update_proposal(proposal.id, state=ProposalState.FINAL_REVIEW,
                               state_prev=ProposalState.REVIEW)
            n_update += 1

        except ConsistencyError:
            n_error += 1

    return (n_update, n_error)


def send_call_proposal_feedback(db, call_id, proposals, dry_run=False):
    """
    Sends feedback for the given proposals.

    Applies the following action to each of the given proposals:

        * Sets the status to ACCEPTED or REJECTED based on the decision.
        * Write a feedback email message into the database including the
          feedback report.

    The proposals argument must be a list of Proposal objects including
    the feedback reviews, decision note and all members.
    """

    logger.debug('Preparing to send feedback for call {}', call_id)

    # Determine the facility class.
    logger.debug('Determining facility class for this call')
    try:
        call = db.get_call(facility_id=None, call_id=call_id)
        assert call.id == call_id

    except NoSuchRecord:
        logger.error('Call {} not found', call_id)
        return 0

    try:
        facility = get_facilities(db=db)[call.facility_id].view
    except KeyError:
        logger.error('Call {} facility {} not present',
                     call_id, call.facility_id)
        return 0

    role_class = facility.get_reviewer_roles()
    type_class = facility.get_call_types()

    # Compute overall ratings for all submitted proposals in the call,
    # but only if this is not an "immediate review" or "multi-close" call.
    immediate_review = type_class.has_immediate_review(call.type)
    proposal_rating = {}

    if immediate_review or type_class.has_mid_close(call.type):
        proposal_quartile = {}

    else:
        call_proposals = db.search_proposal(
            call_id=call_id, state=ProposalState.submitted_states(),
            with_reviewers=True, with_review_info=True,
            with_review_state=ReviewState.DONE)

        facility.attach_review_extra(db, call_proposals)

        for proposal in call_proposals.values():
            rating = facility.calculate_overall_rating(proposal.reviewers)
            if rating is not None:
                proposal_rating[proposal.id] = rating

        proposal_quartile = label_quartiles(proposal_rating)

    # Iterate over proposals and send feedback.
    n_processed = 0

    for proposal in proposals:
        logger.debug('Preparing to send feedback for proposal {}', proposal.id)

        try:
            # Check that the proposal is still in the FINAL_REVIEW state.
            if proposal.state != ProposalState.FINAL_REVIEW:
                raise FeedbackError('Proposal {} is not in final review',
                                    proposal.id)

            # Double-check facility assignment.
            if facility.id_ != proposal.facility_id:
                raise FeedbackError(
                    'Proposal {} has different facility from the call',
                    proposal.id)

            # Double-check the call assignment.
            if proposal.call_id != call_id:
                raise FeedbackError(
                    'Proposal {} has different call ({}) from specified ({})',
                    proposal.call_id, call_id)

            # Filter reviews in case the proposal record contains more than
            # just the feedback report.  Also check the reviews are plain text
            # so that we can include them in the email message.
            feedback = []
            for review in proposal.reviewers.values():
                if review.role != role_class.FEEDBACK:
                    continue

                if review.review_format != FormatType.PLAIN:
                    raise FeedbackError('Feedback review {} is not plain text',
                                        review.id)

                feedback.append(review.review_text)

            # Prepare email (but don't write now -- set the state first so
            # that, if something goes wrong, we don't get into a loop of
            # sending the email again every time we poll for feedback
            # which is ready to send).
            proposal_code = facility.make_proposal_code(db, proposal)
            email_subject = 'Proposal {} {}'.format(
                proposal_code,
                ('approved' if proposal.decision_accept else 'not approved'))
            email_ctx = {
                'proposal': proposal,
                'proposal_code': proposal_code,
                'proposal_rating': proposal_rating.get(proposal.id),
                'proposal_quartile': proposal_quartile.get(proposal.id),
                'feedback': feedback,
                'is_peer_review': type_class.has_reviewer_role(
                    call.type, role_class.PEER)
            }
            email_ctx.update(facility.get_feedback_extra(db, proposal))
            email_body = render_email_template(
                'proposal_feedback.txt', email_ctx, facility=facility)

            # Change the proposal state.
            new_state = (ProposalState.ACCEPTED if proposal.decision_accept
                         else ProposalState.REJECTED)

            logger.info('Setting state of proposal {} to {}',
                        proposal.id, ProposalState.get_name(new_state))

            if not dry_run:
                db.update_proposal(proposal.id, state=new_state,
                                   state_prev=ProposalState.FINAL_REVIEW)

            # Write feedback email message into the database.  Do this after
            # setting the state (see comment above for why).
            logger.debug('Writing feedback message for proposal {}',
                         proposal.id)

            if not dry_run:
                db.add_message(
                    email_subject, email_body,
                    [x.person_id for x in proposal.members.values()])

            # If a proposal for an immediate review call was accepted, send
            # an additional notification message.  For now send this to
            # site administrators.
            if (proposal.decision_accept and immediate_review):
                logger.debug('Writing approval notification for proposal {}',
                             proposal.id)

                email_ctx.update({
                    'call_type': type_class.get_name(proposal.call_type),
                    'immediate_review': immediate_review,
                    'decision_note': None,
                })

                if proposal.decision_note is not None:
                    if proposal.decision_note_format == FormatType.PLAIN:
                        email_ctx['decision_note'] = proposal.decision_note
                    else:
                        logger.warning('Proposal {} note is not plain text',
                                       proposal_code)

                site_administrators = db.search_person(admin=True)

                if not dry_run:
                    db.add_message(
                        email_subject + ' in immediate review',
                        render_email_template(
                            'proposal_reviewed_notification.txt',
                            email_ctx, facility=facility),
                        [x.id for x in site_administrators.values()])

            n_processed += 1

        except FeedbackError:
            logger.exception(
                'Failed to send feedback for proposal {}',
                proposal.id)

        except ConsistencyError:
            logger.exception(
                'Consistency error sending feedback for proposal {}',
                proposal.id)

    return n_processed
