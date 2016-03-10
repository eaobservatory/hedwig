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

from cStringIO import StringIO
from contextlib import closing

from magic import Magic
from PyPDF2 import PdfFileReader
from PyPDF2.utils import PdfReadError

from ..error import UserError
from ..type.enum import FigureType


def determine_figure_type(buff):
    m = Magic(mime=True)

    # Raises a UserError exception if the MIME type is not recognised.
    return FigureType.from_mime_type(m.from_buffer(buff))


def determine_pdf_page_count(buff):
    with closing(StringIO(buff)) as s:
        try:
            r = PdfFileReader(s)
            return r.numPages

        except PdfReadError:
            raise UserError('Could not read the PDF file.')
