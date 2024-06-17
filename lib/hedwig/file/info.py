# Copyright (C) 2015-2023 East Asian Observatory
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

from magic import Magic

try:
    from PyPDF2 import PdfReader as PdfFileReader

    def pdf_num_pages(r):
        return len(r.pages)

    def _pdf_page_sizes(r):
        return [
            ((page.user_unit if hasattr(page, 'user_unit') else 1.0) / 72.0,
             page.mediabox.width, page.mediabox.height)
            for page in r.pages]

except ImportError:
    from PyPDF2 import PdfFileReader

    def pdf_num_pages(r):
        return r.numPages

    def _pdf_page_sizes(r):
        return [
            (1.0 / 72.0, page.mediaBox.getWidth(), page.mediaBox.getHeight())
            for page in r.pages]

try:
    from PyPDF2.errors import PdfReadError
except ImportError:
    from PyPDF2.utils import PdfReadError

from ..error import UserError
from ..type.enum import FigureType


def determine_figure_type(buff):
    """
    Attempt to determine the figure type of an image file stored in a buffer.

    Uses the `magic` module to try to determine the MIME type of the
    image and then converts that to a Hedwig `FigureType` enum value.

    Raises a `UserError` exception if the determined MIME type is not
    recognised as a Hedwig figure type.
    """

    m = Magic(mime=True)

    return FigureType.from_mime_type(m.from_buffer(buff))


def determine_pdf_page_count(buff, with_max_size=False):
    """
    Determine the number of pages in a PDF file stored in a buffer.

    :return: the number of pages if `with_max_size` is false,
        otherwise a tuple containing the number of pages and the
        maximum sizes as determined by the `pdf_max_size` function.
    """

    with closing(BytesIO(buff)) as s:
        try:
            r = PdfFileReader(s)

            num_pages = pdf_num_pages(r)

            if not with_max_size:
                return num_pages

            (max_maj, max_min) = pdf_max_size(r)

            return (num_pages, max_maj, max_min)

        except PdfReadError:
            raise UserError('Could not read the PDF file.')


def pdf_max_size(r):
    """
    Determine the maximum major and minor dimension of the pages
    of a PDF file, given a `PdfFileReader` object.

    Applies the scale factor to the width and height returned
    by `_pdf_page_sizes` for each page.  Identifies the major
    (larger dimension) and minor (smaller dimension) axes.
    Returns the maximum values for the major and minor sizes.

    Sizes should be returned in inches.
    """

    sizes = _pdf_page_sizes(r)

    max_maj = 0.0
    max_min = 0.0

    for (scale, width, height) in sizes:
        # Ensure width and height are floats as some version of
        # PyPDF return sizes as Decimal objects.
        width = float(width) * scale
        height = float(height) * scale

        if width > height:
            (maj, min_) = (width, height)

        else:
            (maj, min_) = (height, width)

        if maj > max_maj:
            max_maj = maj

        if min_ > max_min:
            max_min = min_

    return (max_maj, max_min)
