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

import subprocess

from ..config import get_config
from ..error import Error, ConversionError
from .info import determine_pdf_page_count

ghostscript_version = None


def pdf_to_png(pdf, page_count=None, **kwargs):
    """
    Convert a PDF file to a list of PNG images.

    The page count is determined automatically if not specified.

    Any additional keyword arguments are passed on to _pdf_ps_to_png.
    """

    if page_count is None:
        try:
            page_count = determine_pdf_page_count(pdf)
        except Error as e:
            raise ConversionError(e.message)

    return _pdf_ps_to_png(pdf, page_count, **kwargs)


def ps_to_png(ps, page_count=None, **kwargs):
    """
    Convert a PS or EPS image to a list of PNG images.

    Currently assumes there is only one page if no page_count is given,
    so one PNG should be created in that case.

    Any additional keyword arguments are passed on to _pdf_ps_to_png.
    """

    if page_count is None:
        page_count = 1

    return _pdf_ps_to_png(ps, page_count=1, **kwargs)


def _pdf_ps_to_png(buff, page_count, resolution=100, downscale=4):
    """
    Implements PDF or PS conversion to PDF via Ghostscript.
    """

    global ghostscript_version

    ghostscript = get_config().get('utilities', 'ghostscript')

    if ghostscript_version is None:
        # Determine which version of Ghostscript we have in order to tell if it
        # has features we need.
        try:
            ghostscript_version = float(subprocess.check_output(
                [ghostscript, '--version'], shell=False).strip())

        except subprocess.CalledProcessError:
            raise ConversionError('Could not determine Ghostscript version')

        except ValueError:
            raise ConversionError('Could not parse Ghostscript version')

    ghostscript_has_downscale = (ghostscript_version >= 9.04)

    # Prepare Ghostscript configuration.
    ghostscript_options = [
        '-q',
        '-dNOPAUSE',
        '-dBATCH',
        '-dSAFER',
        '-dPARANOIDSAFER',
        '-dNOTRANSPARENCY',
        '-sDEVICE=png16m',
        '-r{}'.format(resolution * downscale),
        '-dGraphicsAlphaBits=4',
        '-dTextAlphaBits=4',
        '-dEPSCrop',
    ]

    if ghostscript_has_downscale:
        ghostscript_options.append('-dDownScaleFactor={}'.format(downscale))

    # Convert pages to images using Ghostscript.
    pages = []

    try:
        for i in range(0, page_count):
            p = subprocess.Popen(
                [ghostscript] + ghostscript_options + [
                    '-dFirstPage={}'.format(i + 1),
                    '-dLastPage={}'.format(i + 1),
                    '-sOutputFile=-',
                    '-'
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            (stdoutdata, stderrdata) = p.communicate(buff)

            if p.returncode:
                raise ConversionError('PDF/PS to PNG conversion failed: ' +
                                      stderrdata.replace('\n', ' ').strip())

            # If we need to downscale but our Ghostscript doesn't support that
            # feature, scale using Pillow instead.
            if (not ghostscript_has_downscale) and (downscale != 1):
                from PIL import Image
                from .image import _read_image, _write_image
                im = _read_image(stdoutdata)
                (width, height) = im.size
                stdoutdata = _write_image(im.resize(
                    (int(width / downscale), int(height / downscale)),
                    resample=Image.BICUBIC))

            pages.append(stdoutdata)

    except OSError as e:
        raise ConversionError('Failed to run {}: {}'.format(ghostscript,
                                                            e.strerror))

    return pages
