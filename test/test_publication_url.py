# Copyright (C) 2017 East Asian Observatory
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
from hedwig.publication.url import make_publication_url
from hedwig.type.enum import PublicationType

from .compat import TestCase


class PublicationURLTestCase(TestCase):
    def test_publication_url(self):
        # Test formatting generation of basic reference URLs.
        url = make_publication_url(PublicationType.PLAIN, 'reference...')
        self.assertIsNone(url)

        url = make_publication_url(PublicationType.DOI, '00.0000/a b')
        self.assertIsInstance(url, string_type)
        self.assertEqual(url, 'http://doi.org/00.0000/a%20b')

        url = make_publication_url(PublicationType.ADS, '0000............. X')
        self.assertIsInstance(url, string_type)
        self.assertEqual(
            url, 'http://adsabs.harvard.edu/abs/0000.............%20X')

        url = make_publication_url(PublicationType.ARXIV, '0000.00000')
        self.assertIsInstance(url, string_type)
        self.assertEqual(url, 'http://arxiv.org/abs/0000.00000')

        # Test handling of references with non-ASCII characters.
        url = make_publication_url(
            PublicationType.DOI, '00.0000/\u201Cab\u201D')
        self.assertIsInstance(url, string_type)
        self.assertEqual(url, 'http://doi.org/00.0000/%E2%80%9Cab%E2%80%9D')
