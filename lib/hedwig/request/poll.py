# Copyright (C) 2019-2024 East Asian Observatory
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

from datetime import datetime

from ..config import get_config, get_facilities
from ..error import ConsistencyError, FormattedError, NoSuchRecord, UserError
from ..type.enum import AnnotationType, ProposalType, RequestState
from ..type.util import null_tuple
from hedwig.type.simple import CurrentUser, UserInfo
from ..util import get_logger

logger = get_logger(__name__)


def process_request_prop_copy(db, app, dry_run=False):
    """
    Function to handle requests to copy proposals and prepare
    continuation requests.
    """

    n_processed = 0

    for request in db.search_request_prop_copy(
            state=RequestState.NEW).values():
        logger.debug(
            'Handling proposal {} request {} (proposal {})',
            ('continuation' if request.continuation else 'copy'),
            request.id, request.proposal_id)

        try:
            if not dry_run:
                db.update_request_prop_copy(
                    request_id=request.id, state=RequestState.PROCESSING,
                    state_prev=RequestState.NEW, state_is_system=True)
        except ConsistencyError:
            continue

        try:
            copy_proposal_id = _copy_continue_proposal(
                db, app, request, dry_run=dry_run)

            try:
                if not dry_run:
                    db.update_request_prop_copy(
                        request_id=request.id, state=RequestState.READY,
                        processed=datetime.utcnow(),
                        copy_proposal_id=copy_proposal_id,
                        state_prev=RequestState.PROCESSING,
                        state_is_system=True)

                n_processed += 1

            except ConsistencyError:
                continue

        except:
            logger.exception(
                'Error handling proposal {} request {} (proposal {})',
                ('continuation' if request.continuation else 'copy'),
                request.id, request.proposal_id)

            if not dry_run:
                db.update_request_prop_copy(
                    request_id=request.id, state=RequestState.ERROR,
                    state_is_system=True)

    return n_processed


def _copy_continue_proposal(db, app, request, dry_run=False):
    """
    Handle a single request to copy a proposal
    or prepare a continuation request.
    """

    config = get_config()

    try:
        call = db.search_call(
            call_id=request.call_id).get_single()
    except NoSuchRecord:
        raise FormattedError('Call not found.')

    assert call.id == request.call_id

    try:
        facility = get_facilities(db=db)[call.facility_id].view
    except KeyError:
        raise FormattedError(
            'Call {} facility {} not found',
            call.id, call.facility_id)

    type_class = facility.get_call_types()
    role_class = facility.get_reviewer_roles()

    try:
        copier = db.get_person(person_id=request.requester)
    except NoSuchRecord:
        raise FormattedError('Copier person not found.')

    assert copier.id == request.requester

    try:
        old_proposal = db.get_proposal(
            facility.id_, request.proposal_id, with_members=True)
    except NoSuchRecord:
        raise FormattedError('Proposal to copy not found.')

    assert old_proposal.id == request.proposal_id

    if dry_run:
        return None

    if request.continuation:
        proposal_type = ProposalType.CONTINUATION
        annotation_type = AnnotationType.PROPOSAL_CONTINUATION
    else:
        proposal_type = ProposalType.STANDARD
        annotation_type = AnnotationType.PROPOSAL_COPY

    proposal_id = db.add_proposal(
        call_id=call.id, person_id=copier.id,
        affiliation_id=request.affiliation_id, title=old_proposal.title,
        type_=proposal_type,
        person_is_reviewer=type_class.has_reviewer_role(
            call.type, role_class.PEER),
        is_copy=True)

    proposal = db.get_proposal(facility.id_, proposal_id, with_members=True)

    assert proposal.id == proposal_id

    current_user = CurrentUser(
        user=null_tuple(UserInfo)._replace(id=copier.user_id),
        person=copier,
        is_admin=False,
        auth_token_id=None,
        options={})

    with app.test_request_context(
            path='/{}/'.format(facility.get_code()),
            base_url=config.get('application', 'base_url')):
        if request.continuation:
            atn = facility._continue_proposal(
                current_user, db, old_proposal, proposal)
        else:
            atn = facility._copy_proposal(
                current_user, db, old_proposal, proposal,
                copy_members=request.copy_members)

    db.add_proposal_annotation(
        proposal.id, annotation_type, atn)

    return proposal_id
