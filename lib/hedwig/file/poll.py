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

from ..config import get_config
from ..error import ConsistencyError, ConversionError
from ..type import AttachmentState, FigureType
from ..util import get_logger
from .image import create_thumbnail_and_preview
from .pdf import pdf_to_png, ps_to_png

logger = get_logger(__name__)


def process_proposal_figure(db):
    """
    Function to process pending proposal figure uploads.
    """

    config = get_config()
    thumb_preview_options = {
        'max_thumb': (
            int(config.get('proposal_fig', 'max_thumb_width')),
            int(config.get('proposal_fig', 'max_thumb_height'))),
        'max_preview': (
            int(config.get('proposal_fig', 'max_preview_width')),
            int(config.get('proposal_fig', 'max_preview_height'))),
    }
    pdf_ps_options = {
        'resolution': int(config.get('proposal_fig', 'resolution')),
        'downscale': int(config.get('proposal_fig', 'downscale')),
    }

    n_processed = 0

    for figure_info in db.search_proposal_figure(
            state=AttachmentState.NEW).values():
        logger.debug('Processing figure {}', figure_info.id)

        try:
            db.update_proposal_figure(
                proposal_id=None, role=None, fig_id=figure_info.id,
                state=AttachmentState.PROCESSING,
                state_prev=AttachmentState.NEW)
        except ConsistencyError:
            continue

        figure = db.get_proposal_figure(
            proposal_id=None, role=None, id_=figure_info.id)

        try:
            # Create figure preview if necessary.
            preview = None

            if FigureType.needs_preview(figure.type):
                if figure.type == FigureType.PDF:
                    pngs = pdf_to_png(
                        figure.data,
                        renderer=config.get('proposal_fig', 'pdf_renderer'),
                        **pdf_ps_options)

                    if len(pngs) != 1:
                        raise ConversionError(
                            'PDF figure did not generate one page')

                    preview = pngs[0]

                elif figure.type == FigureType.PS:
                    pngs = ps_to_png(figure.data, **pdf_ps_options)

                    if len(pngs) != 1:
                        raise ConversionError(
                            'PS/EPS figure did not generate one page')

                    preview = pngs[0]

                else:
                    raise ConversionError(
                        'Do not know how to make preview of type {}',
                        FigureType.get_name(figure.type))

            # Create figure thumbnail.
            tp = create_thumbnail_and_preview(
                figure.data if preview is None else preview,
                **thumb_preview_options)

            if tp.preview is not None:
                preview = tp.preview

            # Store the processed data.
            if preview is not None:
                db.set_proposal_figure_preview(figure_info.id, preview)

            db.set_proposal_figure_thumbnail(figure_info.id, tp.thumbnail)

            try:
                db.update_proposal_figure(
                    proposal_id=None, role=None, fig_id=figure_info.id,
                    state=AttachmentState.READY,
                    state_prev=AttachmentState.PROCESSING)

                n_processed += 1

            except ConsistencyError:
                continue

        except Exception as e:
            logger.error('Error converting figure {}: {}',
                         figure_info.id, e.message)
            db.update_proposal_figure(
                proposal_id=None, role=None, fig_id=figure_info.id,
                state=AttachmentState.ERROR)

    return n_processed


def process_proposal_pdf(db):
    """
    Function to process pending proposal PDF uploads.
    """

    config = get_config()
    pdf_options = {
        'renderer': config.get('proposal_pdf', 'renderer'),
        'resolution': int(config.get('proposal_pdf', 'resolution')),
        'downscale': int(config.get('proposal_pdf', 'downscale')),
    }

    n_processed = 0

    for pdf in db.search_proposal_pdf(
            state=AttachmentState.NEW).values():
        logger.debug('Processing PDF {}', pdf.id)

        try:
            db.update_proposal_pdf(
                pdf.id,
                state=AttachmentState.PROCESSING,
                state_prev=AttachmentState.NEW)
        except ConsistencyError:
            continue

        buff = db.get_proposal_pdf(proposal_id=None, role=None,
                                   id_=pdf.id).data

        try:
            pngs = pdf_to_png(buff, **pdf_options)

            if len(pngs) != pdf.pages:
                raise ConversionError('PDF generated wrong number of pages')

            db.set_proposal_pdf_preview(pdf.id, pngs)

            try:
                db.update_proposal_pdf(
                    pdf.id,
                    state=AttachmentState.READY,
                    state_prev=AttachmentState.PROCESSING)

                n_processed += 1

            except ConsitencyError:
                # If another process (e.g. new upload) has altered the state,
                # stop trying to process this PDF.
                continue

        except Exception as e:
            logger.error('Error converting PDF {}: {}', pdf.id, e.message)
            db.update_proposal_pdf(pdf.id, state=AttachmentState.ERROR)

    return n_processed
