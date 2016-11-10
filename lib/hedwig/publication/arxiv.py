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

from codecs import ascii_decode
from datetime import datetime
import re
from time import sleep

from xml.etree import ElementTree as etree
import requests

from ..compat import python_version
from ..type.simple import PrevProposalPub
from ..type.util import null_tuple
from ..util import get_logger

logger = get_logger(__name__)


if python_version < 3:
    # Python 2: ElementTree can return text as either ASCII byte strings or
    # as unicode.
    def element_text(element):
        text = element.text
        if isinstance(text, unicode):
            return text
        return ascii_decode(text, 'replace')[0]

else:
    # ElementTree should always return unicode (i.e. str).
    def element_text(element):
        return element.text


def get_pub_info_arxiv(article_ids):
    """
    Get information on a list of article IDs.

    :return: a dictionary by article ID
    """

    url = 'http://export.arxiv.org/api/query'
    xmlns = {'atom': 'http://www.w3.org/2005/Atom'}

    ans = {}

    while article_ids:
        query = article_ids[:10]

        feed = None

        try:
            r = requests.get(url, params={
                'max_results': 10,
                'id_list': ','.join(query),
            }, timeout=30)

            r.raise_for_status()

            feed = etree.fromstring(r.content)

        except requests.exceptions.RequestException:
            logger.exception('Failed to retrive feed from arXiv')

        except:
            logger.exception('Failed to parse arXiv feed')

        if feed is not None:
            for entry in feed.findall('atom:entry', xmlns):
                try:
                    # Read elements from the feed entry.
                    id_element = entry.find('atom:id', xmlns)
                    if id_element is None:
                        continue

                    id_ = element_text(id_element)
                    title = element_text(entry.find('atom:title', xmlns))

                    authors = entry.findall('atom:author', xmlns)
                    author = element_text(authors[0].find('atom:name', xmlns))
                    if len(authors) > 1:
                        author += ' et al.'

                    published = element_text(
                        entry.find('atom:published', xmlns))
                    if published.endswith('Z'):
                        published = published[:-1]
                        year = datetime.strptime(
                            published, '%Y-%m-%dT%H:%M:%S').year

                    # Create publication info tuple.
                    pub = null_tuple(PrevProposalPub)._replace(
                        title=re.sub('\s+', ' ', title).strip(),
                        author=re.sub('\s+', ' ', author).strip(),
                        year='{}'.format(year))

                    # Try to determine to which article ID this entry
                    # relates and store it in the dictionary.
                    for query_id in query:
                        if query_id in id_:
                            ans[query_id] = pub
                            break
                    else:
                        logger.warning('Got unexpected ID {} from arXiv', id_)

                except:
                    logger.exception('Failed to parse arXiv feed entry')

        article_ids = article_ids[10:]
        if article_ids:
            sleep(3)

    return ans
