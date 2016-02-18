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

from contextlib import closing
from cStringIO import StringIO

from PIL import Image
from PyPDF2 import PdfFileWriter

from hedwig.error import UserError
from hedwig.file.image import create_thumbnail_and_preview, \
    _calculate_size
from hedwig.file.info import determine_figure_type, \
    determine_pdf_page_count
from hedwig.file.pdf import pdf_to_png, pdf_to_svg, ps_to_png
from hedwig.type import FigureType

from .dummy_config import DummyConfigTestCase

with closing(StringIO()) as f:
    im = Image.new('RGB', (25, 50))
    im.save(f, format='PNG')
    example_png = f.getvalue()

with closing(StringIO()) as f:
    im = Image.new('RGB', (40, 30))
    im.save(f, format='JPEG')
    example_jpeg = f.getvalue()

with closing(StringIO()) as f:
    w = PdfFileWriter()
    w.addBlankPage(1, 1)
    w.write(f)
    example_pdf = f.getvalue()

example_eps = b"""%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 0 0 100 50
(Helvetica) findfont 12 scalefont setfont
40 20 moveto (test) show
showpage"""


class FileTest(DummyConfigTestCase):
    def test_figure_type(self):
        self.assertEqual(determine_figure_type(example_png), FigureType.PNG)

        self.assertEqual(determine_figure_type(example_jpeg), FigureType.JPEG)

        self.assertEqual(determine_figure_type(example_pdf), FigureType.PDF)

        self.assertEqual(determine_figure_type(example_eps), FigureType.PS)

        with self.assertRaisesRegexp(UserError, 'text/plain'):
            determine_figure_type(b'PLAIN TEXT')

    def test_pdf_pages(self):
        self.assertEqual(determine_pdf_page_count(example_pdf), 1)

    def test_pdf_to_png(self):
        # Render using "ghostscript".
        pages = pdf_to_png(example_pdf, renderer='ghostscript')
        self.assertEqual(len(pages), 1)
        self.assertEqual(determine_figure_type(pages[0]), FigureType.PNG)

        # Repeat using "pdftocairo".
        pages = pdf_to_png(example_pdf, renderer='pdftocairo')
        self.assertEqual(len(pages), 1)
        self.assertEqual(determine_figure_type(pages[0]), FigureType.PNG)

    def test_pdf_to_svg(self):
        page = pdf_to_svg(example_pdf, page=1)

        self.assertEqual(determine_figure_type(page), FigureType.SVG)

    def test_ps_to_png(self):
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

        with closing(StringIO(tp.thumbnail)) as f:
            self.assertEqual(Image.open(f).size, (3, 6))

        tp = create_thumbnail_and_preview(example_png, (80, 80), (12, 12))
        self.assertIsNotNone(tp.thumbnail)
        self.assertIsNotNone(tp.preview)

        self.assertEqual(determine_figure_type(tp.thumbnail), FigureType.PNG)

        self.assertEqual(determine_figure_type(tp.preview), FigureType.PNG)

        with closing(StringIO(tp.thumbnail)) as f:
            self.assertEqual(Image.open(f).size, (40, 80))

        with closing(StringIO(tp.preview)) as f:
            self.assertEqual(Image.open(f).size, (6, 12))

    def test_create_thumb_jpeg(self):
        tp = create_thumbnail_and_preview(example_jpeg, (10, 10), (20, 20))

        for image in (tp.thumbnail, tp.preview):
            self.assertIsNotNone(image)
            self.assertEqual(determine_figure_type(image), FigureType.PNG)
