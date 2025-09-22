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

from codecs import utf_8_decode
import json
from time import sleep

import requests

from ..config import get_config
from ..type.simple import PrevProposalPub
from ..type.util import null_tuple
from ..util import get_logger, list_in_blocks

logger = get_logger(__name__)


fixed_responses = {}
query_block_size = 10
query_delay = 3


def get_pub_info_ads(bibcodes):
    """
    Get information on a list of bibcodes.

    :return: a dictionary by bibcode
    """

    return _get_pub_info_ads_generic('bibcode', bibcodes)


def get_pub_info_doi(dois):
    """
    Get information on a list of DOIs.

    :return: a dictionary by DOI.
    """

    return _get_pub_info_ads_generic('doi', dois)


def get_pub_info_atel(numbers):
    """
    Get information on a list of ATel numbers.

    :return: a dictionary by number.
    """

    return _get_pub_info_ads_generic('atel', numbers)


def get_pub_info_arxiv_ads(article_ids):
    """
    Get information on a list of article IDs.

    This is a fallback function for use if
    :func:`hedwig.publication.arxiv.get_pub_info_arxiv`
    is not usable.

    :return: a dictionary by article ID.

    .. warning::
        This function may return the wrong year, i.e. the year of
        final publication rather than the year in which the publication
        was uploaded to arXiv, because ADS may have combined these records.
    """

    return _get_pub_info_ads_generic('arxiv', article_ids)


def _get_pub_info_ads_generic(type_, codes):
    """
    Get information via ADS for a given type of code.

    :param `type_`: can be "bibcode" or "doi"
    :param codes:  list of codes to query
    """

    url = 'https://api.adsabs.harvard.edu/v1/search/query'
    api_token = get_config().get('ads', 'api_token')

    ans = {}

    n_query = 0
    for query in list_in_blocks(codes, query_block_size):
        if n_query > 0:
            sleep(query_delay)
        n_query += 1

        result = None
        query_extra = None
        id_filter = None

        if type_ == 'doi':
            query_type = 'identifier'
            query = ['doi:"{}"'.format(_escape_term(x)) for x in query]

        elif type_ == 'arxiv':
            type_ = query_type = 'identifier'
            query = ['arXiv:"{}"'.format(_escape_term(x)) for x in query]

            def id_filter(id_):
                return id_[6:] if id_.startswith('arXiv:') else None

        elif type_ == 'atel':
            type_ = query_type = 'volume'
            query_extra = 'bibstem:ATel'

        else:
            query_type = type_

        try:
            query_str = '{}:({})'.format(query_type, ' OR '.join(query))

            if query_extra is not None:
                query_str = ' '.join((query_str, query_extra))

            response = fixed_responses.get(query_str)

            if response is None:
                r = requests.get(
                    url,
                    params={
                        'q': query_str,
                        'fl': ','.join((type_, 'title', 'author', 'pubdate')),
                        'rows': 10,
                    },
                    headers={
                        'Authorization': 'Bearer {}'.format(api_token),
                    },
                    timeout=30)

                r.raise_for_status()

                response = utf_8_decode(r.content)[0]

            result = json.loads(response)

        except requests.exceptions.RequestException:
            logger.exception('Failed to search ADS')

        except:
            logger.exception('Failed to parse ADS search response')

        if result is not None:
            try:
                for doc in result['response']['docs']:
                    ids = doc[type_]
                    if not isinstance(ids, list):
                        ids = [ids]

                    title = doc['title']
                    if isinstance(title, list):
                        title = title[0]

                    author = doc['author'][0]
                    if len(doc['author']) > 1:
                        author += ' et al.'

                    (year, date) = doc['pubdate'].split('-', 1)

                    for id_ in ids:
                        if id_filter is not None:
                            id_ = id_filter(id_)
                            if id_ is None:
                                continue

                        ans[id_] = null_tuple(PrevProposalPub)._replace(
                            title=title,
                            author=author,
                            year=year)

            except:
                logger.exception('Failed to process ADS search response')

    return ans


def _escape_term(string):
    return string.replace('"', '\\"')
