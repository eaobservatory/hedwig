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


def pdf_to_png(pdf, page_count=None, resolution=100):
    """
    Convert a PDF file to a list of PNG images.
    """

    if page_count is None:
        try:
            page_count = determine_pdf_page_count(pdf)
        except Error as e:
            raise ConversionError(e.message)

    ghostscript = get_config().get('utilities', 'ghostscript')
    pages = []

    try:
        for i in range(0, page_count):
            p = subprocess.Popen(
                [
                    ghostscript,
                    '-q',
                    '-dNOPAUSE',
                    '-dBATCH',
                    '-dSAFER',
                    '-dNOTRANSPARENCY',
                    '-sDEVICE=png16m',
                    '-r{}'.format(resolution),
                    '-dGraphicsAlphaBits=4',
                    '-dTextAlphaBits=4',
                    '-dFirstPage={}'.format(i + 1),
                    '-dLastPage={}'.format(i + 1),
                    '-sOutputFile=-',
                    '-'
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            (stdoutdata, stderrdata) = p.communicate(pdf)

            if p.returncode:
                raise ConversionError('PDF to PNG conversion failed: ' +
                                      stderrdata.replace('\n', ' ').strip())

            pages.append(stdoutdata)

    except OSError as e:
        raise ConversionError('Failed to run {}: {}'.format(ghostscript,
                                                            e.strerror))

    return pages
