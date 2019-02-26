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

from ..config import get_config
from ..error import ConsistencyError, ConversionError, FormattedError
from ..type.enum import AttachmentState, FigureType
from ..util import get_logger
from .image import create_thumbnail_and_preview
from .moc import read_moc
from .pdf import pdf_to_png, ps_to_png

logger = get_logger(__name__)


def process_moc(db, dry_run=False):
    """
    Function to process new clash tool MOC files by importing their cells
    into the "moc_cell" database table in order to make them searchable.
    """

    n_processed = 0

    for moc_info in db.search_moc(facility_id=None, public=None,
                                  state=AttachmentState.NEW).values():
        logger.debug('Importing MOC {}', moc_info.id)

        try:
            if not dry_run:
                db.update_moc(
                    moc_id=moc_info.id, state=AttachmentState.PROCESSING,
                    state_prev=AttachmentState.NEW)
        except ConsistencyError:
            continue

        try:
            moc = read_moc(buff=db.get_moc_fits(moc_info.id))

            if not dry_run:
                db.update_moc_cell(moc_info.id, moc)

            try:
                if not dry_run:
                    db.update_moc(
                        moc_id=moc_info.id, state=AttachmentState.READY,
                        state_prev=AttachmentState.PROCESSING)

                n_processed += 1

            except ConsistencyError:
                continue

        except Exception:
            logger.exception('Error importing MOC {}', moc_info.id)

            if not dry_run:
                db.update_moc(moc_id=moc_info.id, state=AttachmentState.ERROR)

    return n_processed


def process_proposal_figure(db, dry_run=False):
    """
    Function to process pending proposal figure uploads.
    """

    return _process_figure(db, 'proposal', dry_run=dry_run)


def process_review_figure(db, dry_run=False):
    """
    Function to process pending review figure uploads.
    """

    return _process_figure(db, 'review', dry_run=dry_run)


def _process_figure(db, _type, dry_run=False):
    if _type == 'proposal':
        config_section = 'proposal_fig'

        figures = db.search_proposal_figure(
            state=AttachmentState.NEW, no_link=True)

        def get_figure(fig_id):
            return db.get_proposal_figure(
                proposal_id=None, role=None, link_id=None, fig_id=fig_id)

        def set_state(fig_id, state, state_prev=None):
            db.update_proposal_figure(
                proposal_id=None, role=None, link_id=None, fig_id=fig_id,
                state=state, state_prev=state_prev)

        set_thumbnail = db.set_proposal_figure_thumbnail
        set_preview = db.set_proposal_figure_preview

    elif _type == 'review':
        config_section = 'review_fig'

        figures = db.search_review_figure(
            state=AttachmentState.NEW, no_link=True)

        def get_figure(fig_id):
            return db.get_review_figure(
                reviewer_id=None, link_id=None, fig_id=fig_id)

        def set_state(fig_id, state, state_prev=None):
            db.update_review_figure(
                reviewer_id=None, link_id=None, fig_id=fig_id,
                state=state, state_prev=state_prev)

        set_thumbnail = db.set_review_figure_thumbnail
        set_preview = db.set_review_figure_preview

    else:
        raise FormattedError('Unknown figure type: {}', _type)

    config = get_config()
    thumb_preview_options = {
        'max_thumb': (
            int(config.get(config_section, 'max_thumb_width')),
            int(config.get(config_section, 'max_thumb_height'))),
        'max_preview': (
            int(config.get(config_section, 'max_preview_width')),
            int(config.get(config_section, 'max_preview_height'))),
    }
    pdf_ps_options = {
        'resolution': int(config.get(config_section, 'resolution')),
        'downscale': int(config.get(config_section, 'downscale')),
    }

    n_processed = 0

    for figure_info in figures.values():
        logger.debug('Processing {} figure {}', _type, figure_info.fig_id)

        try:
            if not dry_run:
                set_state(figure_info.fig_id, AttachmentState.PROCESSING,
                          state_prev=AttachmentState.NEW)
        except ConsistencyError:
            continue

        figure = get_figure(figure_info.fig_id)

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
            if not dry_run:
                if preview is not None:
                    set_preview(figure_info.fig_id, preview)

                set_thumbnail(figure_info.fig_id, tp.thumbnail)

            try:
                if not dry_run:
                    set_state(figure_info.fig_id, AttachmentState.READY,
                              state_prev=AttachmentState.PROCESSING)

                n_processed += 1

            except ConsistencyError:
                continue

        except Exception as e:
            logger.exception(
                'Error converting {} figure {}', _type, figure_info.fig_id)

            if not dry_run:
                try:
                    set_state(figure_info.fig_id, AttachmentState.ERROR)

                except:
                    # It's possible that whatever prevented us processing the
                    # figure also prevents us updating the state, e.g.
                    # the figure having been deleted.
                    pass

    return n_processed


def process_proposal_pdf(db, dry_run=False):
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
            state=AttachmentState.NEW, no_link=True).values():
        logger.debug('Processing PDF {}', pdf.pdf_id)

        try:
            if not dry_run:
                db.update_proposal_pdf(
                    pdf_id=pdf.pdf_id,
                    state=AttachmentState.PROCESSING,
                    state_prev=AttachmentState.NEW)
        except ConsistencyError:
            continue

        buff = db.get_proposal_pdf(
            proposal_id=None, role=None, pdf_id=pdf.pdf_id).data

        try:
            pngs = pdf_to_png(buff, **pdf_options)

            if len(pngs) != pdf.pages:
                raise ConversionError('PDF generated wrong number of pages')

            if not dry_run:
                db.set_proposal_pdf_preview(pdf.pdf_id, pngs)

            try:
                if not dry_run:
                    db.update_proposal_pdf(
                        pdf_id=pdf.pdf_id,
                        state=AttachmentState.READY,
                        state_prev=AttachmentState.PROCESSING)

                n_processed += 1

            except ConsitencyError:
                # If another process (e.g. new upload) has altered the state,
                # stop trying to process this PDF.
                continue

        except Exception:
            logger.exception('Error processing PDF {}', pdf.pdf_id)

            if not dry_run:
                try:
                    db.update_proposal_pdf(
                        pdf_id=pdf.pdf_id, state=AttachmentState.ERROR)
                except:
                    # It's possible that whatever prevented us setting the
                    # previews also prevents us updating the state, e.g.
                    # the PDF having been deleted.
                    pass

    return n_processed
