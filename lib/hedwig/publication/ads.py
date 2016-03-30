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

import json
from time import sleep

import requests

from ..config import get_config
from ..type.simple import PrevProposalPub
from ..type.util import null_tuple
from ..util import get_logger

logger = get_logger(__name__)


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


def _get_pub_info_ads_generic(type_, codes):
    """
    Get information via ADS for a given type of code.

    :param `type_`: can be "bibcode" or "doi"
    :param codes:  list of codes to query
    """

    url = 'https://api.adsabs.harvard.edu/v1/search/query'
    api_token = get_config().get('ads', 'api_token')

    ans = {}

    while codes:
        query = codes[:10]
        result = None

        if type_ == 'doi':
            query_type = 'identifier'
            query = ['doi:{}'.format(x) for x in query]
        else:
            query_type = type_

        try:
            r = requests.get(
                url,
                params={
                    'q': '{}:({})'.format(query_type, ' OR '.join(query)),
                    'fl': ','.join((type_, 'title', 'author', 'pubdate')),
                    'rows': 10,
                },
                headers={
                    'Authorization': 'Bearer {}'.format(api_token),
                },
                timeout=30)

            r.raise_for_status()

            result = json.loads(r.content)

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
                        ans[id_] = null_tuple(PrevProposalPub)._replace(
                            title=title,
                            author=author,
                            year=year)

            except:
                logger.exception('Failed to process ADS search response')

        codes = codes[10:]
        if codes:
            sleep(3)

    return ans
