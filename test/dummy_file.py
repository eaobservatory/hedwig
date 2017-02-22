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

from PIL import Image
from PyPDF2 import PdfFileWriter

with closing(BytesIO()) as f:
    im = Image.new('RGB', (25, 50))
    im.save(f, format='PNG')
    example_png = f.getvalue()

with closing(BytesIO()) as f:
    im = Image.new('RGB', (40, 30))
    im.save(f, format='JPEG')
    example_jpeg = f.getvalue()

with closing(BytesIO()) as f:
    w = PdfFileWriter()
    w.addBlankPage(1, 1)
    w.write(f)
    example_pdf = f.getvalue()

example_eps = b"""%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 0 0 100 50
(Helvetica) findfont 12 scalefont setfont
40 20 moveto (test) show
showpage"""
