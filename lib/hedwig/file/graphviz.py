# Copyright (C) 2016 East Asian Observatory
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
import subprocess

from ..config import get_config
from ..error import ConversionError


def graphviz_to_png(buff):
    """
    Convert a Graphviz file to an SVG file.
    """

    dot = get_config().get('utilities', 'graphviz')

    try:
        p = subprocess.Popen(
            [
                dot,
                '-Tpng',
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        (stdoutdata, stderrdata) = p.communicate(buff)

        if p.returncode:
            stderrdata = latin_1_decode(stderrdata, 'replace')[0]
            raise ConversionError('Graphviz conversion failed: {}',
                                  stderrdata.replace('\n', ' ').strip())

        return stdoutdata

    except OSError as e:
        raise ConversionError('Failed to run {}: {}', dot, e.strerror)
