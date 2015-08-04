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

from ..error import ConsistencyError
from ..util import get_logger
from ..type import AttachmentState, PublicationType
from .arxiv import get_pub_info_arxiv

logger = get_logger(__name__)


def process_publication_references(db):
    """
    Function to process newly added publication references.
    """

    n_processed = 0

    arxiv = set()

    logger.debug('Checking for publication references to retrieve')

    for publication in db.search_prev_proposal_pub(
            state=AttachmentState.NEW, type_=PublicationType.ARXIV).values():

        if publication.type == PublicationType.ARXIV:
            arxiv.add(publication.description)

    if arxiv:
        logger.debug('Retreiving references from arXiv')

        arxiv_info = get_pub_info_arxiv(list(arxiv))

        for reference in arxiv:
            info = arxiv_info.get(reference)

            if info is None:
                logger.warning(
                    'No info received for {} - setting error state',
                    reference)

                db.update_prev_proposal_pub(
                    type_=PublicationType.ARXIV, description=reference,
                    state=AttachmentState.ERROR,
                    title=None, author=None, year=None)

            else:
                logger.debug('Received info for {} - updating database',
                             reference)

                try:
                    db.update_prev_proposal_pub(
                        type_=PublicationType.ARXIV, description=reference,
                        state=AttachmentState.READY,
                        title=info.title, author=info.author, year=info.year)

                    n_processed += 1

                except:
                    logger.exception('Failed to update publication reference')

    return n_processed
