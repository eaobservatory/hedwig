# Copyright (C) 2020-2021 East Asian Observatory
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

from datetime import datetime, timedelta
import os

from .request import get_proposal_filename
from ..config import get_pdf_writer
from ..error import ConsistencyError, FormattedError
from ..type.enum import RequestState
from ..util import get_logger

logger = get_logger(__name__)


def process_request_prop_pdf(db, app, dry_run=False):
    """
    Function to handle requests for PDF versions of proposals.
    """

    requests = db.search_request_prop_pdf(state=RequestState.NEW)

    if not requests:
        return 0

    pdf_writer = get_pdf_writer(db=db, app=app)

    n_processed = 0

    for request in requests.values():
        logger.debug(
            'Handling proposal PDF request {} (proposal {})',
            request.id, request.proposal_id)

        try:
            if not dry_run:
                db.update_request_prop_pdf(
                    request_id=request.id, state=RequestState.PROCESSING,
                    state_prev=RequestState.NEW,
                    state_is_system=True)
        except ConsistencyError:
            continue

        try:
            pdf = pdf_writer.proposal(request.proposal_id)

            filename = get_proposal_filename(request)

            if os.path.exists(filename):
                raise FormattedError(
                    'File {} already exists (for request {}, proposal {})',
                    filename, request.id, request.proposal_id)

            if not dry_run:
                with open(filename, 'wb') as f:
                    f.write(pdf)

            try:
                if not dry_run:
                    db.update_request_prop_pdf(
                        request_id=request.id, state=RequestState.READY,
                        processed=datetime.utcnow(),
                        state_prev=RequestState.PROCESSING,
                        state_is_system=True)

                n_processed += 1

            except ConsistencyError:
                continue

        except Exception:
            logger.exception(
                'Error handling proposal PDF request {} (proposal {})',
                request.id, request.proposal_id)

            if not dry_run:
                db.update_request_prop_pdf(
                    request_id=request.id, state=RequestState.ERROR,
                    state_is_system=True)

    return n_processed


def process_request_prop_pdf_expiry(db, dry_run=False):
    """
    Function to expire processed requests for PDF versions of proposals.
    """

    n_expired = 0

    for request in db.search_request_prop_pdf(
            state=RequestState.READY,
            processed_before=(
                datetime.utcnow() - timedelta(hours=24))).values():
        logger.debug(
            'Expiring proposal PDF request {} (proposal {})',
            request.id, request.proposal_id)

        try:
            if not dry_run:
                db.update_request_prop_pdf(
                    request_id=request.id, state=RequestState.EXPIRING,
                    state_prev=RequestState.READY,
                    state_is_system=True)
        except ConsistencyError:
            continue

        try:
            filename = get_proposal_filename(request)

            if not os.path.isfile(filename):
                raise FormattedError(
                    'File {} doest not exist (for request {}, proposal {})',
                    filename, request.id, request.proposal_id)

            if not dry_run:
                os.unlink(filename)

            try:
                if not dry_run:
                    db.update_request_prop_pdf(
                        request_id=request.id, state=RequestState.EXPIRED,
                        state_prev=RequestState.EXPIRING,
                        state_is_system=True)

                n_expired += 1

            except ConsistencyError:
                continue

        except Exception:
            logger.exception(
                'Error expiring proposal PDF request {} (proposal {})',
                request.id, request.proposal_id)

            if not dry_run:
                db.update_request_prop_pdf(
                    request_id=request.id, state=RequestState.EXPIRE_ERROR,
                    state_is_system=True)

    return n_expired
