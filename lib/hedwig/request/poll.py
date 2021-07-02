# Copyright (C) 2019-2021 East Asian Observatory
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
from ..type.enum import AnnotationType, RequestState
from ..view.people import _update_session_person
from ..web.util import session
from ..util import get_logger

logger = get_logger(__name__)


def process_request_prop_copy(db, app, dry_run=False):
    """
    Function to handle requests to copy proposals.
    """

    n_processed = 0

    for request in db.search_request_prop_copy(
            state=RequestState.NEW).values():
        logger.debug(
            'Handling proposal copy request {} (proposal {})',
            request.id, request.proposal_id)

        try:
            if not dry_run:
                db.update_request_prop_copy(
                    request_id=request.id, state=RequestState.PROCESSING,
                    state_prev=RequestState.NEW)
        except ConsistencyError:
            continue

        try:
            copy_proposal_id = _copy_proposal(
                db, app, request, dry_run=dry_run)

            try:
                if not dry_run:
                    db.update_request_prop_copy(
                        request_id=request.id, state=RequestState.READY,
                        processed=datetime.utcnow(),
                        copy_proposal_id=copy_proposal_id,
                        state_prev=RequestState.PROCESSING)

                n_processed += 1

            except ConsistencyError:
                continue

        except:
            logger.exception(
                'Error handling proposal copy request {} (proposal {})',
                request.id, request.proposal_id)

            if not dry_run:
                db.update_request_prop_copy(
                    request_id=request.id, state=RequestState.ERROR)

    return n_processed


def _copy_proposal(db, app, request, dry_run=False):
    config = get_config()

    try:
        call = db.search_call(
            call_id=request.call_id, with_facility_code=True).get_single()
    except NoSuchRecord:
        raise FormattedError('Call not found.')

    assert call.id == request.call_id

    for facility_class in get_facilities():
        if facility_class.get_code() == call.facility_code:
            facility = facility_class(call.facility_id)
            break
    else:
        raise FormattedError(
            'Call {} facility {} not found',
            call.id, call.facility_code)

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

    proposal_id = db.add_proposal(
        call_id=call.id, person_id=copier.id,
        affiliation_id=request.affiliation_id, title=old_proposal.title,
        person_is_reviewer=type_class.has_reviewer_role(
            call.type, role_class.PEER))

    proposal = db.get_proposal(facility.id_, proposal_id, with_members=True)

    assert proposal.id == proposal_id

    with app.test_request_context(
            path='/{}/'.format(facility.get_code()),
            base_url=config.get('application', 'base_url')):
        _update_session_person(copier)

        atn = facility._copy_proposal(
            db, old_proposal, proposal, copy_members=request.copy_members)

        session.clear()

    db.add_proposal_annotation(
        proposal.id, AnnotationType.PROPOSAL_COPY, atn)

    return proposal_id
