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

import os
import re
from textwrap import TextWrapper

from jinja2 import Environment, FileSystemLoader

from ..config import get_config, get_home
from ..util import lower_except_abbr

environment = None
wrapper = None

line_break = re.compile('\n')
paragraph_break = re.compile('\n\n+')
break_comment = re.compile(r'^\s*{# BR #}\s*$', flags=re.IGNORECASE)
pattern_block_only = re.compile(r'^{% (\w+) [^%]*%}$')
pattern_spaces_non_start = re.compile(r'(?<=[^ \n])  +')


class UnwrapFileSystemLoader(FileSystemLoader):
    """
    Template loader which unwraps lines as the template is read.

    Email templates are stored in text files where long lines are typically
    wrapped at a suitable width using single line breaks.  This class unwraps
    the template by removing such breaks.  This allows single line breaks
    in text substituted into templates to be retained.  Unwrapping after
    rendering the template would remove both (unwanted) line breaks from
    the template file and (presumably intentional) line breaks in substituted
    text.

    Also recognizes a special comment template comment `{# BR #}` to
    indicate where a single line break should be retained.  (This must
    appear on a line by itself.)
    """

    def get_source(self, environment, template):
        (source, filename, uptodate) = super(
            UnwrapFileSystemLoader, self).get_source(environment, template)

        return (_unwrap_email_template(source), filename, uptodate)


def _unwrap_email_template(source):
    """
    Helper function for `UnwrapFileSystemLoader`.

    Attempts to unwrap the lines of an email template.  Performs some
    basic processing:

    * Recognizes the break comment `{# BR #}`.

    * Assumes lines containing only a single `{% ... %}` statement
      do not generate output and so does not add a space before the next
      line.  Records such status before `if-elif-else-endif` structures
      to restore it for each branch (but does not accumulate status from
      the branches, assuming them all to be similar).
    """

    paragraphs = []
    has_output_before = []

    for paragraph in paragraph_break.split(source):
        lines = []
        has_output = False
        for line in line_break.split(paragraph):
            if break_comment.match(line):
                lines.append('\n')
                has_output = False
                continue

            if not line:
                continue

            match = pattern_block_only.match(line)
            if match:
                statement = match.group(1)
                if statement == 'if':
                    has_output_before.append(has_output)
                elif statement in ('else', 'elif'):
                    if has_output_before:
                        has_output = has_output_before[-1]
                elif statement == 'endif':
                    if has_output_before:
                        has_output_before.pop()

            else:
                if has_output:
                    lines.append(' ')

                has_output = True

            lines.append(line)

        paragraphs.append(''.join(lines))

    return '\n\n'.join(paragraphs)


def get_environment():
    """
    Get Jinja environment for processing email templates.

    If an environment has already been constructed, it is stored in the
    `environment` global variable and will be returned.  Otherwise
    a new environment is prepared.  The environment configuration has:

    * The `data/home` directory (within the Hedwig home directory) configured
      as the template loading path.

    * Template globals:
        * From the `application` section of the configuration file:
            * `application_name`
        * From the `email` section of the configuration file:
            * `email_footer_title`
            * `email_footer_url`
            * `email_footer_email`

    * Filters:
        * `format_datetime`
    """

    global environment

    if environment is None:
        environment = Environment(
            autoescape=False,
            loader=UnwrapFileSystemLoader(
                os.path.join(get_home(), 'data', 'email')),
            trim_blocks=False,
            lstrip_blocks=False)

        config = get_config()

        environment.globals.update({
            'application_name': config.get('application', 'name'),
            'email_footer_title': config.get('email', 'footer_title'),
            'email_footer_url': config.get('email', 'footer_url'),
            'email_footer_email': config.get('email', 'footer_email'),
        })

        environment.filters['format_datetime'] = \
            lambda x: x.strftime('%Y-%m-%d %H:%M')

        environment.filters['lower_except_abbr'] = lower_except_abbr

    return environment


def render_email_template(name, context, facility=None):
    """
    Render a template and then adjust paragraph breaks.

    If a `facility` (view class) is given then the template will be loaded
    from a directory of the facility's code, if it exists, otherwise
    from the `generic` directory.  The template context will also be
    extended to include:

    * `facility_name`
    * `facility_definite_name`

    .. note::
        This function no longer line-wraps the email message (using
        :func:`wrap_email_text`) and instead returns plain text
        suitable for use with `MessageFormatType.PLAIN`.  If other
        formats are to be used, it may be necessary to alter the
        return value of this function to include the format type.
    """

    # Apply the template.
    env = get_environment()

    full_context = context.copy()

    if facility is None:
        template = env.get_template(name)

    else:
        template = env.select_template((facility.get_code() + '/' + name,
                                        'generic/' + name))

        full_context.update({
            'facility_name': facility.get_name(),
            'facility_definite_name': facility.get_definite_name(),
        })

    return _tidy_email_text(template.render(full_context))


def _tidy_email_text(text):
    """
    Tidy the spacing of email text generated from a template.

    * Ensures only one blank line between paragraphs.

    * Merges multiple consecutive spaces into one
      except at the start of a line.
    """

    return '\n\n'.join(
        pattern_spaces_non_start.sub(' ', paragraph)
        for paragraph in paragraph_break.split(text))


def wrap_email_text(text):
    """
    Line-wraps email message text.

    * The message is broken into paragraphs, at multiple line breaks.
    * Each line in the paragraph is then line-wrapped.
    * A trailing space is added to each wrapped line, except the last
      (flowed email format).
    * The lines of the email are rejoined, with a blank line between
      paragraphs.

    .. note::
        The behavior of this function has changed to preserve
        single line breaks by individually wrapping each line
        within each paragraph.
    """

    wrp = _get_text_wrapper()

    # Wrap each paragraph and append to the lines list.
    lines = []
    for paragraph in paragraph_break.split(text.replace('\r', '')):
        if lines:
            lines.append('')
        if not paragraph:
            continue

        for line in line_break.split(paragraph):
            wrapped = wrp.wrap(line)

            if not wrapped:
                continue

            lines.extend([x + ' ' for x in wrapped[:-1]])
            lines.append(wrapped[-1])

    # Return complete message.
    return '\n'.join(lines)


def _get_text_wrapper():
    """
    Get TextWrapper object.
    """

    global wrapper

    if wrapper is None:
        # Avoid breaking long "words" in order not to break URLs.
        wrapper = TextWrapper(
            width=70,
            break_long_words=False,
            break_on_hyphens=False)

    return wrapper


def unwrap_email_text(text):
    """
    Unwrap email text, from the style of "format=flowed"
    to paragraphs on single lines.

    This is the inverse of :func:`wrap_email_text`
    and can be used when email text (which has be prepared for
    sending with format=flowed) is to be sent in a different
    style, such as "quoted-printable" content encoding.
    """

    paragraphs = []
    paragraph = []

    for line in text.splitlines():
        paragraph.append(line)
        if not line.endswith(' '):
            paragraphs.append(''.join(paragraph))
            paragraph = []

    if paragraph:
        paragraphs.append(''.join(paragraph))

    return '\n'.join(paragraphs)
