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

import os
from textwrap import wrap

from jinja2 import Environment, FileSystemLoader

from ..config import get_config, get_home

environment = None


def get_environment():
    global environment

    if environment is None:
        environment = Environment(
            autoescape=False,
            loader=FileSystemLoader(os.path.join(get_home(), 'data', 'email')),
            trim_blocks=True,
            lstrip_blocks=True)

        environment.globals['application_name'] = get_config().get(
            'application', 'name')

    return environment


def render_email_template(name, context):
    """
    Render a template and then attempt to line-wrap the output
    sensibly.
    """

    # Apply the template.
    env = get_environment()

    template = env.get_template(name)

    body = template.render(context)

    # Wrap each paragraph and append to the lines list.
    lines = []
    for paragraph in body.replace('\r', '').split('\n\n'):
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

    # Return complete body of message.
    return '\n'.join(lines)