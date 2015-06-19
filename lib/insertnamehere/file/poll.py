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

from ..error import ConsistencyError, ConversionError
from ..type import ProposalAttachmentState, ProposalFigureType
from ..util import get_logger
from .image import create_thumbnail
from .pdf import pdf_to_png

logger = get_logger(__name__)


def process_proposal_figure(db):
    """
    Function to process pending proposal figure uploads.
    """

    for figure_info in db.search_proposal_figure(
            state=ProposalAttachmentState.NEW).values():
        logger.debug('Processing figure {}', figure_info.id)

        try:
            db.update_proposal_figure(
                proposal_id=None, role=None, fig_id=figure_info.id,
                state=ProposalAttachmentState.PROCESSING,
                state_prev=ProposalAttachmentState.NEW)
        except ConsistencyError:
            continue

        figure = db.get_proposal_figure(
            proposal_id=None, role=None, id_=figure_info.id)

        try:
            # Create figure preview if necessary.
            preview = None

            if ProposalFigureType.needs_preview(figure.type):
                if figure.type == ProposalFigureType.PDF:
                    pngs = pdf_to_png(figure.data)

                    if len(pngs) != 1:
                        raise ConversionError(
                            'PDF figure did not generate one page')

                    preview = pngs[0]

                else:
                    raise ConversionError(
                        'Do not know how to make preview of type {}',
                        ProposalFigureType.get_name(figure.type))

            # Create figure thumbnail.
            thumbnail = create_thumbnail(
                figure.data if preview is None else preview)

            # Store the processed data.
            if preview is not None:
                db.set_proposal_figure_preview(figure_info.id, preview)

            db.set_proposal_figure_thumbnail(figure_info.id, thumbnail)

            try:
                db.update_proposal_figure(
                    proposal_id=None, role=None, fig_id=figure_info.id,
                    state=ProposalAttachmentState.READY,
                    state_prev=ProposalAttachmentState.PROCESSING)
            except ConsistencyError:
                continue

        except Exception as e:
            logger.error('Error converting figure {}: {}',
                         figure_info.id, e.message)
            db.update_proposal_figure(
                proposal_id=None, role=None, fig_id=figure_info.id,
                state=ProposalAttachmentState.ERROR)


def process_proposal_pdf(db):
    """
    Function to process pending proposal PDF uploads.
    """

    for pdf in db.search_proposal_pdf(
            state=ProposalAttachmentState.NEW).values():
        logger.debug('Processing PDF {}', pdf.id)

        try:
            db.update_proposal_pdf(
                pdf.id,
                state=ProposalAttachmentState.PROCESSING,
                state_prev=ProposalAttachmentState.NEW)
        except ConsistencyError:
            continue

        buff = db.get_proposal_pdf(proposal_id=None, role=None, id_=pdf.id)

        try:
            pngs = pdf_to_png(buff)

            if len(pngs) != pdf.pages:
                raise ConversionError('PDF generated wrong number of pages')

            db.set_proposal_pdf_preview(pdf.id, pngs)

            try:
                db.update_proposal_pdf(
                    pdf.id,
                    state=ProposalAttachmentState.READY,
                    state_prev=ProposalAttachmentState.PROCESSING)
            except ConsitencyError:
                # If another process (e.g. new upload) has altered the state,
                # stop trying to process this PDF.
                continue

        except Exception as e:
            logger.error('Error converting PDF {}: {}', pdf.id, e.message)
            db.update_proposal_pdf(pdf.id, state=ProposalAttachmentState.ERROR)
