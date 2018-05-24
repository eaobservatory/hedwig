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

from hedwig.config import get_config
from hedwig.publication.ads import get_pub_info_ads, fixed_responses
from hedwig.type.simple import PrevProposalPub

from .dummy_config import DummyConfigTestCase
from .dummy_publication import ads_responses
from .util import temporary_dict


class ADSPublicationTestCase(DummyConfigTestCase):
    def test_ads_bibcode(self):
        # Test for the API token now (rather than with a decorator) so that
        # we're looking in the "dummy" configuration.
        config = get_config()
        if config.getboolean('test', 'query_ads'):
            if not config.get('ads', 'api_token'):
                self.skipTest('ADS API token not configured')
            responses = {}
        else:
            responses = ads_responses

        bibcode = '1965ApJ...142..419P'
        with temporary_dict(fixed_responses, responses):
            result = get_pub_info_ads([bibcode])
        self.assertIsInstance(result, dict)
        self.assertEqual(sorted(result.keys()), [bibcode])

        info = result[bibcode]
        self.assertIsInstance(info, PrevProposalPub)
        self.assertTrue(info.title.startswith('A Measurement of Excess'))
        self.assertTrue(info.author.startswith('Penzias'))
        self.assertEqual(info.year, '1965')
