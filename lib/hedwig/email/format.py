# Copyright (C) 2015-2019 East Asian Observatory
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
from textwrap import wrap

from jinja2 import Environment, FileSystemLoader

from ..config import get_config, get_home

environment = None

paragraph_break = re.compile('\n\n+')


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
            loader=FileSystemLoader(os.path.join(get_home(), 'data', 'email')),
            trim_blocks=True,
            lstrip_blocks=True)

        config = get_config()

        environment.globals.update({
            'application_name': config.get('application', 'name'),
            'email_footer_title': config.get('email', 'footer_title'),
            'email_footer_url': config.get('email', 'footer_url'),
            'email_footer_email': config.get('email', 'footer_email'),
        })

        environment.filters['format_datetime'] = \
            lambda x: x.strftime('%Y-%m-%d %H:%M')

    return environment


def render_email_template(name, context, facility=None):
    """
    Render a template and then attempt to line-wrap the output
    sensibly.

    If a `facility` (view class) is given then the template will be loaded
    from a directory of the facility's code, if it exists, otherwise
    from the `generic` directory.  The template context will also be
    extended to include:

    * `facility_name`
    * `facility_definite_name`

    Currently line-wraps the email message, after generating the text
    by applying the template, using :func:`wrap_email_text`.
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

    return wrap_email_text(template.render(full_context))


def wrap_email_text(text):
    """
    Line-wraps email message text.

    * The message is broken into paragraphs, at multiple line breaks.
    * Each paragraph itself is line-wrapped.
    * A trailing space is added to each line of the paragraph, except the last
      (flowed email format).
    * The lines of the email are rejoined, with a blank line between
      paragraphs.

    Note: with the above scheme there is no way to insert a single
    manual line break.  (A single break is considered to be within a
    paragraph and the whole paragraph is re-flowed.)
    """

    # Wrap each paragraph and append to the lines list.
    lines = []
    for paragraph in paragraph_break.split(text.replace('\r', '')):
        if lines:
            lines.append('')
        if not paragraph:
            continue

        # Avoid breaking long "words" in order not to break URLs.
        wrapped = wrap(paragraph, width=70,
                       break_long_words=False,
                       break_on_hyphens=False)

        if not wrapped:
            continue

        lines.extend([x + ' ' for x in wrapped[:-1]])
        lines.append(wrapped[-1])

    # Return complete message.
    return '\n'.join(lines)
