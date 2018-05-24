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

from hedwig.compat import first_value
from hedwig.config import get_config
from hedwig.publication.arxiv import fixed_responses as arxiv_fixed_responses
from hedwig.publication.poll import process_publication_references
from hedwig.type.enum import AttachmentState, PublicationType
from hedwig.type.collection import PrevProposalCollection
from hedwig.type.simple import PrevProposal, PrevProposalPub
from hedwig.type.util import null_tuple

from .dummy_db import DBTestCase
from .dummy_publication import arxiv_responses
from .util import temporary_dict


class PublicationPollTestCase(DBTestCase):
    def test_poll_publication_references(self):
        # Should initially find nothing to process.
        self.assertEqual(process_publication_references(self.db), 0)

        # Create a proposal and add a reference.
        proposal_id = self._create_test_proposal()
        records = PrevProposalCollection()
        records[0] = null_tuple(PrevProposal)._replace(
            this_proposal_id=proposal_id,
            proposal_code='DUMMY',
            continuation=False,
            publications=[
                null_tuple(PrevProposalPub)._replace(
                    description='1611.02297',
                    type=PublicationType.ARXIV,
                ),
            ])
        (n_insert, n_update, n_delete) = self.db.sync_proposal_prev_proposal(
            proposal_id, records)
        self.assertEqual(n_insert, 1)
        self.assertEqual(n_update, 1)  # Updates to publications counted here.
        self.assertEqual(n_delete, 0)

        # Record starts off marked NEW.
        result = self.db.search_prev_proposal_pub()
        self.assertEqual(len(result), 1)
        info = first_value(result)
        self.assertIsInstance(info, PrevProposalPub)
        self.assertEqual(info.state, AttachmentState.NEW)

        # Should now find 1 record to process.
        with temporary_dict(
                arxiv_fixed_responses,
                {} if get_config().getboolean('test', 'query_arxiv')
                else arxiv_responses):
            self.assertEqual(process_publication_references(self.db), 1)

        # Record should have been filled in and marked READY.
        result = self.db.search_prev_proposal_pub()
        self.assertEqual(len(result), 1)
        info = first_value(result)
        self.assertIsInstance(info, PrevProposalPub)
        self.assertEqual(info.state, AttachmentState.READY)
        self.assertTrue(info.title.startswith('Dynamical modeling'))
        self.assertTrue(info.author.startswith('Damir'))
        self.assertEqual(info.year, '2016')
