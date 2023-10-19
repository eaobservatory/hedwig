# Copyright (C) 2015-2022 East Asian Observatory
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

from markupsafe import Markup

from ..email.format import wrap_email_text
from ..format.rst import rst_to_html
from ..type.enum import FormatType
from .util import HTTPError


def format_text(text, format=None, as_email=False, as_inline=False):
    """
    Format text, possibly using different formatting schemes.

    If "format" is not specified, it defaults to PLAIN unless
    "text" has attributes "text" and "format", in which case those
    are used instead.

    The "as_inline" option requests inline formatting elements only,
    if the format type supports this.
    """

    if format is None:
        if hasattr(text, 'text') and hasattr(text, 'format'):
            format = text.format
            text = text.text
        else:
            format = FormatType.PLAIN

    prefix = ''
    if as_email:
        if format == FormatType.PLAIN:
            return Markup('<pre>') + wrap_email_text(text) + Markup('</pre>')
        else:
            prefix = Markup('<p class="warning">Format is not plain text.</p>')

    if format == FormatType.PLAIN:
        if as_inline:
            return prefix + format_text_plain_inline(text)
        return prefix + format_text_plain(text)

    elif format == FormatType.RST:
        return prefix + format_text_rst(text)

    else:
        raise HTTPError('Unknown format type.')


def format_text_plain(text):
    """
    Format plain text for display as HTML.

    The text is broken into paragraphs at double line breaks.
    Within each paragraph, a line break tag (`<br />`) is inserted
    at remaining (single) line breaks.

    :return: Flask Markup object containing the formatted text
    """

    result = Markup('')

    for paragraph in text.replace('\r', '').split('\n\n'):
        if not paragraph:
            continue

        result += Markup('<p>') + \
            Markup('<br />').join(paragraph.split('\n')) + \
            Markup('</p>')

    return result


def format_text_plain_inline(text):
    """
    Format plain text for display as inline HTML.

    This is a variation of `format_text_plain` which only adds
    line breaks, not paragraphs.  This can be used for small pieces
    of text inside other elements, such as <td>.

    :return: Flask Markup object containing the formatted text
    """

    return Markup('<br />').join(
        filter((lambda x: x), text.replace('\r', '').split('\n')))


def format_text_rst(text, extract_title_toc=False, start_heading=3):
    """
    Format RST for display as HTML.

    This applies the :func:`hedwig.format.rst.rst_to_html` function.

    :param text: text marked up as RST for formatting
    :param extract_title_toc: indicate whether to extract title and TOC
    :param start_heading: initial heading level

    :return: Flask Markup object containing the formatted text, unless
        `extract_title_toc` is specified, in which case a tuple
        of the Markup object, a Markup object containing the title,
        and a list of TOC items.
    """

    (body, title, toc) = rst_to_html(text, extract_title=extract_title_toc,
                                     start_heading=start_heading)

    if not extract_title_toc:
        return Markup(body)

    else:
        return (Markup(body), Markup(title), toc)
