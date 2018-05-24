# Copyright (C) 2016-2018 East Asian Observatory
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

from hedwig.compat import string_type
from hedwig.config import get_config
from hedwig.publication.arxiv import get_pub_info_arxiv, fixed_responses
from hedwig.type.simple import PrevProposalPub

from .dummy_config import DummyConfigTestCase
from .dummy_publication import arxiv_responses
from .util import temporary_dict


class ADSPublicationTestCase(DummyConfigTestCase):
    def test_arxiv(self):
        id_ = '1001.0001'
        with temporary_dict(
                fixed_responses,
                {} if get_config().getboolean('test', 'query_arxiv')
                else arxiv_responses):
            result = get_pub_info_arxiv([id_])
        self.assertIsInstance(result, dict)
        self.assertEqual(sorted(result.keys()), [id_])

        info = result[id_]
        self.assertIsInstance(info, PrevProposalPub)
        self.assertIsInstance(info.title, string_type)
        self.assertIsInstance(info.author, string_type)
        self.assertIsInstance(info.year, string_type)

        self.assertTrue(info.title.startswith('On the structure'))
        self.assertTrue(info.author.startswith('Denis Krotov'))
        self.assertEqual(info.year, '2009')
