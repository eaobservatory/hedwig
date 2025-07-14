# Copyright (C) 2015-2025 East Asian Observatory
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

from collections import namedtuple

from ..error import ConsistencyError
from ..util import get_logger
from ..type.enum import AttachmentState, PublicationType
from .arxiv import get_pub_info_arxiv
from .ads import get_pub_info_ads, get_pub_info_atel, get_pub_info_doi

logger = get_logger(__name__)

PubTypeInfo = namedtuple('PubTypeInfo', ('set', 'query_function'))


def process_publication_references(db, dry_run=False):
    """
    Function to process newly added publication references.

    Searches for publication references in the `NEW` state
    and organizes them by type.  Then the collection of
    references of each type is passed to the :func:`_process_ref_type`
    function.

    :return: the total number of references processed
    """

    n_processed = 0

    types = {
        PublicationType.DOI:   PubTypeInfo(set(), get_pub_info_doi),
        PublicationType.ADS:   PubTypeInfo(set(), get_pub_info_ads),
        PublicationType.ARXIV: PubTypeInfo(set(), get_pub_info_arxiv),
        PublicationType.ATEL:  PubTypeInfo(set(), get_pub_info_atel),
    }

    for publication in db.search_prev_proposal_pub(
            state=AttachmentState.NEW).values():

        if publication.type in types:
            types[publication.type].set.add(publication.description)

        else:
            type_name = PublicationType.get_info(publication.type).name
            logger.warning('Can not look up reference type: {}', type_name)

    for (type_, type_info) in types.items():
        if type_info.set:
            n_processed += _process_ref_type(
                db, type_, type_info.query_function, type_info.set,
                dry_run=dry_run)

    return n_processed


def _process_ref_type(db, type_, query_function, references, dry_run=False):
    """
    Look up references of a given type using the specified query function
    and update their entries in the database.

    The state of the publication reference is set to `READY` if
    it is processed successfully or `ERROR` otherwise.

    Note that references should be given as a `set` (of unique values)
    and database updates are performed by matching by `type_` and
    reference `description` (rather than by `prev_proposal_pub` ID)
    to allow multiple copies of the same reference to be resolved together.

    :param db: database control object
    :param `type_`: type of reference being updated
    :param query_function: function to look up lists of references
    :param references: set of references to update
    :param dry_run: enable dry run mode if true

    :return: the number of references successfully processed
    """

    type_name = PublicationType.get_info(type_).name

    logger.debug('Retreiving {} references', type_name)

    n_processed = 0

    reference_info = query_function(list(references))

    for reference in references:
        info = reference_info.get(reference)

        if info is None:
            logger.warning(
                'No info received for {} - setting error state',
                reference)

            try:
                if not dry_run:
                    db.update_prev_proposal_pub(
                        type_=type_, description=reference,
                        state=AttachmentState.ERROR,
                        title=None, author=None, year=None,
                        state_prev=AttachmentState.NEW)

            except:
                logger.exception('Failed to set publication error state')

        else:
            logger.debug('Received info for {} - updating database',
                         reference)

            try:
                if not dry_run:
                    db.update_prev_proposal_pub(
                        type_=type_, description=reference,
                        state=AttachmentState.READY,
                        title=info.title, author=info.author, year=info.year,
                        state_prev=AttachmentState.NEW)

                n_processed += 1

            except:
                logger.exception('Failed to update publication reference')

    return n_processed
