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

from os.path import exists

from pymoc import MOC

from hedwig.config import get_config
from hedwig.file.poll import process_moc, \
    process_proposal_figure, process_proposal_pdf, process_review_figure
from hedwig.type.enum import AttachmentState, BaseTextRole, \
    FigureType, FormatType

from .dummy_db import DBTestCase
from .dummy_file import example_png, example_pdf


class FilePollTestCase(DBTestCase):
    def test_poll_process_moc(self):
        facility_id = self.db.ensure_facility('test')

        # Should initially find nothing to process.
        self.assertEqual(process_moc(self.db), 0)

        # Insert a new MOC.
        moc = MOC(order=10, cells=(1234, 4321))
        moc_id = self.db.add_moc(
            facility_id, 'test', 'Test', FormatType.PLAIN, True, moc)

        # The MOC should be marked NEW.
        mocs = self.db.search_moc(facility_id, None, moc_id=moc_id)
        self.assertEqual(list(mocs.keys()), [moc_id])
        self.assertEqual(mocs[moc_id].state, AttachmentState.NEW)

        # Should now find 1 MOC to process.
        self.assertEqual(process_moc(self.db), 1)

        # The MOC should now be marked READY.
        mocs = self.db.search_moc(facility_id, None, moc_id=moc_id)
        self.assertEqual(list(mocs.keys()), [moc_id])
        self.assertEqual(mocs[moc_id].state, AttachmentState.READY)

    def test_poll_proposal_figure(self):
        # Should initially find nothing to process.
        self.assertEqual(process_proposal_figure(self.db), 0)

        # Create a proposal and add a figure.
        proposal_id = self._create_test_proposal()
        person_id = self.db.add_person('Figure Uploader')
        (link_id, figure_id) = self.db.add_proposal_figure(
            BaseTextRole, proposal_id, BaseTextRole.TECHNICAL_CASE,
            FigureType.PNG, example_png, 'Dummy Caption',
            'dummy.png', person_id)

        # The figure should initially be marked NEW.
        figures = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(list(figures.keys()), [link_id])
        self.assertEqual(figures[link_id].state, AttachmentState.NEW)

        # Should now find 1 figure to process.
        self.assertEqual(process_proposal_figure(self.db), 1)

        # The figure should now be marked READY.
        figures = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(list(figures.keys()), [link_id])
        self.assertEqual(figures[link_id].state, AttachmentState.READY)

    def test_poll_review_figure(self):
        # Should initially find nothing to process.
        self.assertEqual(process_review_figure(self.db), 0)

        # Create a proposal and add a figure.
        proposal_id = self._create_test_proposal()
        reviewer_id = self._create_test_reviewer(proposal_id)
        person_id = self.db.add_person('Figure Uploader')
        (link_id, figure_id) = self.db.add_review_figure(
            reviewer_id, FigureType.PNG, example_png, 'Dummy Caption',
            'dummy.png', person_id)

        # The figure should initially be marked NEW.
        figures = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertEqual(list(figures.keys()), [link_id])
        self.assertEqual(figures[link_id].state, AttachmentState.NEW)

        # Should now find 1 figure to process.
        self.assertEqual(process_review_figure(self.db), 1)

        # The figure should now be marked READY.
        figures = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertEqual(list(figures.keys()), [link_id])
        self.assertEqual(figures[link_id].state, AttachmentState.READY)

    def test_poll_proposal_pdf(self):
        # Should initially find nothing to process.
        self.assertEqual(process_proposal_pdf(self.db), 0)

        # Determine if we have the configured PDF processing application so
        # that the test can be skipped if it is not present.
        config = get_config()
        pdf_renderer = config.get('proposal_pdf', 'renderer')
        if not pdf_renderer:
            self.skipTest('Proposal PDF renderer not configured')
        if pdf_renderer == 'ghostscript':
            if not exists(get_config().get('utilities', 'ghostscript')):
                self.skipTest('Ghostscript not available')
        elif pdf_renderer == 'pdftocairo':
            if not exists(get_config().get('utilities', 'pdftocairo')):
                self.skipTest('pdftocairo not available')
        else:
            self.fail('Unexpected proposal PDF renderer')

        # Create a proposal and add a PDF.
        proposal_id = self._create_test_proposal()
        person_id = self.db.add_person('PDF Uploader')
        (link_id, pdf_id) = self.db.set_proposal_pdf(
            BaseTextRole, proposal_id, BaseTextRole.TECHNICAL_CASE,
            example_pdf, 1, 'dummy.pdf', person_id)

        # The PDF should initially be marked NEW.
        pdfs = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(list(pdfs.keys()), [link_id])
        self.assertEqual(pdfs[link_id].state, AttachmentState.NEW)

        # Should now find 1 PDF to process.
        self.assertEqual(process_proposal_pdf(self.db), 1)

        # The PDF should now be marked READY.
        pdfs = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(list(pdfs.keys()), [link_id])
        self.assertEqual(pdfs[link_id].state, AttachmentState.READY)
