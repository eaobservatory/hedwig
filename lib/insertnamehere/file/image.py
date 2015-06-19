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


def create_thumbnail(image, max_width=100, max_height=100):
    """
    Generate a thumbnail image.
    """

    with closing(StringIO(image)) as f:
        im = Image.open(f)
        im.load()

    (orig_width, orig_height) = im.size

    # Calculate scale factor required to ensure both dimensions are withing
    # the maximum allowed.
    scale = max(orig_width / max_width,
                orig_height / max_height)

    # Scale the image and return as PNG.
    width = int(orig_width / scale)
    height = int(orig_height / scale)

    with closing(StringIO()) as f:
        thumbnail = im.resize((width, height), resample=Image.BICUBIC)
        thumbnail.save(f, format='PNG')
        return f.getvalue()
