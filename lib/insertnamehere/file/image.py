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
import warnings

from PIL import Image

from ..type import ProposalFigureThumbPreview

warnings.simplefilter('error', Image.DecompressionBombWarning)


def create_thumbnail_and_preview(image, max_thumb=None, max_preview=None):
    """
    Generate a thumbnail image and preview if necessary.
    """

    if max_thumb is None:
        max_thumb = (100, 100)
    if max_preview is None:
        max_preview = (500, 500)

    with closing(StringIO(image)) as f:
        im = Image.open(f)
        im.load()

    orig_size = im.size

    new_size = _calculate_size(max_thumb, orig_size)

    with closing(StringIO()) as f:
        im_thumbnail = im.resize(new_size, resample=Image.BICUBIC)
        im_thumbnail.save(f, format='PNG')
        thumbnail = f.getvalue()

    new_size = _calculate_size(max_preview, orig_size, only_shrink=True)

    if new_size is None:
        preview = None

    else:
        with closing(StringIO()) as f:
            im_preview = im.resize(new_size, resample=Image.BICUBIC)
            im_preview.save(f, format='PNG')
            preview = f.getvalue()

    return ProposalFigureThumbPreview(thumbnail, preview)


def _calculate_size(max_size, orig_size, only_shrink=False):
    """
    Calculate (width, height) size tuple to which to scale image,
    or None if scaling isn't necessary.
    """

    (max_width, max_height) = max_size
    (orig_width, orig_height) = orig_size

    # Calculate scale factor required to ensure both dimensions are withing
    # the maximum allowed.
    scale = max(orig_width / max_width,
                orig_height / max_height)

    if only_shrink and scale <= 1:
        return None

    # Scale the image and return as PNG.
    width = int(orig_width / scale)
    height = int(orig_height / scale)

    return (width, height)
