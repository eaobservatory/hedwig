# Copyright (C) 2015-2025 East Asian Observatory
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

import re

from markupsafe import Markup

from ..format.rst import rst_to_html
from ..type.enum import FormatType, MessageFormatType
from .util import get_logger, HTTPError


def format_text(text, format=None, as_inline=False):
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

    if format == FormatType.PLAIN:
        if as_inline:
            return format_text_plain_inline(text)
        return format_text_plain(text)

    elif format == FormatType.RST:
        return format_text_rst(text)

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


def format_message_text(text, format=None):
    """
    Format message text, using different formatting types.

    If `format` is not specified, it defaults to PLAIN unless
    `text` has attributes `body` and `format`, in which case those
    are used instead.
    """

    if format is None:
        if hasattr(text, 'body') and hasattr(text, 'format'):
            format = text.format
            text = text.body
        else:
            format = MessageFormatType.PLAIN

    if format == MessageFormatType.PLAIN_FLOWED:
        # Text should have already been line-wrapped in preparation
        # for sending with format=flowed.  Therefore just add <pre> tags.
        return Markup('<pre>') + text + Markup('</pre>')

    elif format == MessageFormatType.PLAIN:
        return format_text_plain(text)

    else:
        raise HTTPError('Unknown message format type.')

pattern_html_tag = re.compile(r'<(SUP|sup|SUB|sub|ASTROBJ)>([-_+A-Za-z0-9() ]+)</\1>')

title_html_tags = {
    'SUB': 'sub',
    'SUP': 'sup',
    'ASTROBJ': 'b',
}

pattern_latex_ss = re.compile(r'\{?([_^])(?:\{([-_+A-Za-z0-9() ]+)\}|([0-9]))\}?')
pattern_latex_fmt = re.compile(r'\{\\(sc|bf|it) ([-_+A-Za-z0-9() ]+)\}|\\text(sc|bf|it)\{([-_+A-Za-z0-9() ]+)\}')
pattern_latex_space = re.compile(r'\\[,:;]')

title_latex_tags = {
    '_': 'sub',
    '^': 'sup',
    'sc': 'span class="smallcaps"',
    'bf': 'b',
    'it': 'i',
}


def format_title_markup(text):
    """
    Apply formatting to markup as might be found in publication titles.

    Uses the `_format_title` function to apply formatting for HTML found
    in titles (SUP, SUB, ASTROBJ), LaTeX subscripts and superscripts
    and basic LaTeX formatting (sc, bf, it).
    """

    # Perform formatting in try-except structure in case of errors from
    # the formatting routine.
    try:
        return Markup('').join(_format_title(text, [
            [pattern_html_tag, _format_title_html],
            [pattern_latex_ss, _format_title_latex],
            [pattern_latex_fmt, _format_title_latex],
            [pattern_latex_space, (lambda: ' ')],
        ]))

    except:
        logger = get_logger()
        logger.exception('Error formatting text: {}', text)

        # In case of error, return the input text as given.
        return text


def _format_title(text, formatters, i=0):
    """
    Recursively apply pattern formatters to the given text.

    Each entry in `formatters` consistes of a splitting regular expression
    (with capture groups) and a function to call for each match.  The function
    will be passed the non-None match groups.  Recursion is only applied
    to the non-matching parts of the given text, so nesting of markup
    is not supported.

    :return: a list of formatted elements
    """

    (pattern, formatter) = formatters[i]

    next_ = i + 1
    apply_next = (
        (lambda x: _format_title(x, formatters, next_))
        if (next_ < len(formatters))
        else (lambda x: [x]))

    parts = pattern.split(text)
    parts.reverse()

    result = apply_next(parts.pop())

    while parts:
        args = []
        for j in range(0, pattern.groups):
            arg = parts.pop()
            if arg is not None:
                args.append(arg)

        result.append(formatter(*args))

        result.extend(apply_next(parts.pop()))

    return result


def _format_title_html(tag, content):
    safetag = title_html_tags.get(tag.upper())

    if safetag is None:
        return Markup('<i>') + tag + Markup('</i>(') + content + ')'

    return Markup('<' + safetag + '>') + content + Markup('</' + safetag + '>')


def _format_title_latex(tag, content):
    safetag = title_latex_tags.get(tag)

    if safetag is None:
        return content

    if ' ' in safetag:
        (elem, attrs) = safetag.split(' ', 1)
    else:
        elem = safetag

    return Markup('<' + safetag + '>') + content + Markup('</' + elem + '>')
