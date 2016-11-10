# Copyright (C) 2015-2016 East Asian Observatory
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

from contextlib import closing
from io import BytesIO
from os.path import exists

from PIL import Image

from hedwig.config import get_config
from hedwig.error import ConversionError, UserError
from hedwig.file.graphviz import graphviz_to_png
from hedwig.file.image import create_thumbnail_and_preview, \
    _calculate_size
from hedwig.file.info import determine_figure_type, \
    determine_pdf_page_count
from hedwig.file.pdf import pdf_to_png, pdf_to_svg, ps_to_png
from hedwig.type.enum import FigureType

from .dummy_config import DummyConfigTestCase
from .dummy_file import example_eps, example_jpeg, example_png, example_pdf


invalid_pdf = b'NOT PDF'


class FileTest(DummyConfigTestCase):
    def test_figure_type(self):
        self.assertEqual(determine_figure_type(example_png), FigureType.PNG)

        self.assertEqual(determine_figure_type(example_jpeg), FigureType.JPEG)

        self.assertEqual(determine_figure_type(example_pdf), FigureType.PDF)

        self.assertEqual(determine_figure_type(example_eps), FigureType.PS)

        with self.assertRaisesRegex(UserError, 'text/plain'):
            determine_figure_type(b'PLAIN TEXT')

    def test_pdf_pages(self):
        self.assertEqual(determine_pdf_page_count(example_pdf), 1)

        with self.assertRaisesRegex(UserError, '^Could not read the PDF file'):
            determine_pdf_page_count(invalid_pdf)

    def test_pdf_to_png_ghostscript(self):
        if not exists(get_config().get('utilities', 'ghostscript')):
            self.skipTest('Ghostscript not available')

        # Render using "ghostscript".
        pages = pdf_to_png(example_pdf, renderer='ghostscript')
        self.assertEqual(len(pages), 1)
        self.assertEqual(determine_figure_type(pages[0]), FigureType.PNG)

        # An invalid PDF fails when pdf_to_png tries to get the page count.
        with self.assertRaisesRegex(
                ConversionError, '^Could not determine PDF page count:'):
            pdf_to_png(invalid_pdf, renderer='ghostscript')

        # When specifying a page count, get an error from ghostscript instead.
        with self.assertRaisesRegex(
                ConversionError, '^PDF/PS to PNG conversion failed:'):
            pdf_to_png(invalid_pdf, page_count=1, renderer='ghostscript')

    def test_pdf_to_png_cairo(self):
        if not exists(get_config().get('utilities', 'pdftocairo')):
            self.skipTest('pdftocairo not available')

        # Repeat using "pdftocairo".
        pages = pdf_to_png(example_pdf, renderer='pdftocairo')
        self.assertEqual(len(pages), 1)
        self.assertEqual(determine_figure_type(pages[0]), FigureType.PNG)

        with self.assertRaisesRegex(
                ConversionError, '^PDF conversion \(pdftocairo\) failed:'):
            pages = pdf_to_png(
                invalid_pdf, page_count=1, renderer='pdftocairo')

    def test_pdf_to_svg(self):
        if not exists(get_config().get('utilities', 'pdftocairo')):
            self.skipTest('pdftocairo not available')

        page = pdf_to_svg(example_pdf, page=1)

        self.assertEqual(determine_figure_type(page), FigureType.SVG)

    def test_ps_to_png(self):
        if not exists(get_config().get('utilities', 'ghostscript')):
            self.skipTest('Ghostscript not available')

        pages = ps_to_png(example_eps)
        self.assertEqual(len(pages), 1)

        self.assertEqual(determine_figure_type(pages[0]), FigureType.PNG)

    def test_calculate_size(self):
        # Do not give a larger size if "only_shrink" is specified.
        self.assertEqual(_calculate_size((100, 100), (30, 60)), (50, 100))
        self.assertIsNone(_calculate_size((100, 100), (30, 60), True))

        # Always give a smaller size.
        self.assertEqual(_calculate_size((100, 100), (150, 75)), (100, 50))
        self.assertEqual(_calculate_size((100, 100), (150, 75), True),
                         (100, 50))

    def test_create_thumb_prev(self):
        tp = create_thumbnail_and_preview(example_png, (6, 6), (100, 100))
        self.assertIsNotNone(tp.thumbnail)
        self.assertIsNone(tp.preview)

        self.assertEqual(determine_figure_type(tp.thumbnail), FigureType.PNG)

        with closing(BytesIO(tp.thumbnail)) as f:
            self.assertEqual(Image.open(f).size, (3, 6))

        tp = create_thumbnail_and_preview(example_png, (80, 80), (12, 12))
        self.assertIsNotNone(tp.thumbnail)
        self.assertIsNotNone(tp.preview)

        self.assertEqual(determine_figure_type(tp.thumbnail), FigureType.PNG)

        self.assertEqual(determine_figure_type(tp.preview), FigureType.PNG)

        with closing(BytesIO(tp.thumbnail)) as f:
            self.assertEqual(Image.open(f).size, (40, 80))

        with closing(BytesIO(tp.preview)) as f:
            self.assertEqual(Image.open(f).size, (6, 12))

    def test_create_thumb_jpeg(self):
        tp = create_thumbnail_and_preview(example_jpeg, (10, 10), (20, 20))

        for image in (tp.thumbnail, tp.preview):
            self.assertIsNotNone(image)
            self.assertEqual(determine_figure_type(image), FigureType.PNG)

    def test_graphviz_to_png(self):
        example_dot = b'graph G {x -- y}'
        invalid_dot = b'graph G {x -> y}'

        out = graphviz_to_png(example_dot)

        self.assertEqual(determine_figure_type(out), FigureType.PNG)

        with self.assertRaisesRegex(
                ConversionError, '^Graphviz conversion failed:'):
            graphviz_to_png(invalid_dot)
