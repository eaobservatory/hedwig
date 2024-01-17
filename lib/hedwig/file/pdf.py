# Copyright (C) 2015-2024 East Asian Observatory
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

from codecs import latin_1_decode
from io import BytesIO
import subprocess

try:
    from PyPDF2 import PdfMerger as PdfFileMerger
    merge_kwargs = {'import_outline': False}
except ImportError:
    from PyPDF2 import PdfFileMerger
    merge_kwargs = {'import_bookmarks': False}

from ..compat import split_version
from ..config import get_config
from ..error import Error, ConversionError
from ..type.enum import FigureType
from ..util import ClosingMultiple
from .info import determine_pdf_page_count

ghostscript_version = None


def pdf_merge(pdfs):
    """
    Merge a sequence of PDFs (supplied as buffers containing the PDF data)
    into a single document (returned also as a buffer).
    """

    with ClosingMultiple() as closer:
        merger = closer(PdfFileMerger(strict=False))

        for buff in pdfs:
            f = closer(BytesIO(buff))
            merger.append(f, **merge_kwargs)

        f = closer(BytesIO())
        merger.write(f)

        return f.getvalue()


def pdf_to_png(pdf, page_count=None, renderer='ghostscript', **kwargs):
    """
    Convert a PDF file to a list of PNG images.

    The page count is determined automatically if not specified.

    The PDF renderer can be either "ghostscript" or "pdftocairo".  The
    path to the selected program is looked up in the configuration file.

    Any additional keyword arguments are passed on to :func:`_pdf_ps_to_png`
    (for "ghostscript") or :func:`_pdf_to_cairo` (for "pdftocairo").
    """

    if page_count is None:
        try:
            page_count = determine_pdf_page_count(pdf)
        except Error as e:
            raise ConversionError(
                'Could not determine PDF page count: ' + e.message)

    if renderer == 'ghostscript':
        return _pdf_ps_to_png(pdf, page_count=page_count, **kwargs)

    elif renderer == 'pdftocairo':
        pages = range(1, page_count + 1)
        return _pdf_to_cairo(pdf, FigureType.PNG, pages=pages, **kwargs)

    else:
        raise ConversionError('Unrecognised PDF renderer: {}', renderer)


def pdf_to_svg(pdf, page, **kwargs):
    """
    Convert a given page of the PDF file to SVG format.
    """

    svg_pages = _pdf_to_cairo(pdf, FigureType.SVG, pages=[page], **kwargs)

    return svg_pages[0]


def ps_to_png(ps, page_count=None, **kwargs):
    """
    Convert a PS or EPS image to a list of PNG images.

    Currently assumes there is only one page if no page_count is given,
    so one PNG should be created in that case.

    Any additional keyword arguments are passed on to :func:`_pdf_ps_to_png`.
    """

    if page_count is None:
        page_count = 1

    return _pdf_ps_to_png(ps, page_count=page_count, **kwargs)


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
            ghostscript_version = split_version(latin_1_decode(
                subprocess.check_output(
                    [ghostscript, '--version'], shell=False
                ).strip(), 'replace')[0])

        except subprocess.CalledProcessError:
            raise ConversionError('Could not determine Ghostscript version')

        except ValueError:
            raise ConversionError('Could not parse Ghostscript version')

    ghostscript_has_downscale = (ghostscript_version >= (9, 4))

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
        '-sstdout=%stderr',
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
                stderrdata = latin_1_decode(stderrdata, 'replace')[0]
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
        raise ConversionError('Failed to run {}: {}', ghostscript, e.strerror)

    return pages


def _pdf_to_cairo(buff, type_, pages, resolution=100, downscale=None):
    """
    Process a PDF file using pdftocairo.

    The arguments specify the desired figure type (PNG or SVG) and a list
    of the pages (by page number) to process.

    The `downscale` argument is ignored (it is present for compatibility
    with the equivalent ghostscript-based method).
    """

    pdftocairo = get_config().get('utilities', 'pdftocairo')

    pdftocairo_options = [
        '-q',
    ]

    if type_ == FigureType.PNG:
        pdftocairo_options.extend([
            '-png',
            '-singlefile',
            '-r', str(resolution),
        ])

    elif type_ == FigureType.SVG:
        pdftocairo_options.extend([
            '-svg',
            '-origpagesizes',
        ])

    else:
        raise ConversionError('Unrecognised target type for pdftocairo: {}',
                              type_)

    # Convert pages using pdftocairo.
    rendered_pages = []

    try:
        for page in pages:
            p = subprocess.Popen(
                [pdftocairo] + pdftocairo_options + [
                    '-f', str(page),
                    '-l', str(page),
                    '-', '-',
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            (stdoutdata, stderrdata) = p.communicate(buff)

            if p.returncode:
                stderrdata = latin_1_decode(stderrdata, 'replace')[0]
                raise ConversionError('PDF conversion (pdftocairo) failed: ' +
                                      stderrdata.replace('\n', ' ').strip())

            rendered_pages.append(stdoutdata)

    except OSError as e:
        raise ConversionError('Failed to run {}: {}', pdftocairo, e.strerror)

    return rendered_pages
