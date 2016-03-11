# Copyright (C) 2015-2016 East Asian Observatory
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

import json as json_module

from flask import Markup
from jinja2.runtime import Undefined

from ..type.enum import Assessment, AttachmentState, CallState, \
    ProposalState, PublicationType, ReviewerRole, TextRole

from .format import format_text


def register_template_utils(app):
    """
    Register all of the template utilities with the given Flask app.

    These utilities consist of:

    * Global functions.
    * Filters.
    * Tests.
    """

    @app.template_global()
    def create_counter(start_value=1):
        return Counter(start_value)

    @app.template_filter()
    def assessment_name(value):
        if value is None:
            return ''
        return Assessment.get_name(value)

    @app.template_filter()
    def attachment_state_name(value):
        if value is None:
            return ''
        return AttachmentState.get_name(value)

    @app.template_filter()
    def call_state_name(value):
        if value is None:
            return ''
        return CallState.get_name(value)

    @app.template_filter()
    def count_true(list_):
        return len(filter(None, list_))

    @app.template_filter()
    def fmt(value, format_):
        """
        Similar to the Jinja built in filter "format" but the other way
        round and using new-style formatting.
        """

        if value is None or isinstance(value, Undefined):
            return ''

        if isinstance(value, tuple):
            return format_.format(*value)

        return format_.format(value)

    @app.template_filter()
    def format_date(value):
        if value is None:
            return ''
        return value.strftime('%Y-%m-%d')

    @app.template_filter()
    def format_time(value):
        if value is None:
            return ''
        return value.strftime('%H:%M')

    @app.template_filter()
    def format_datetime(value):
        if value is None:
            return ''
        return value.strftime('%Y-%m-%d %H:%M')

    @app.template_filter()
    def format_hours_hms(hours):
        (m, s) = divmod(int(3600 * hours), 60)
        (h, m) = divmod(m, 60)
        return '{:d}:{:02d}:{:02d}'.format(h, m, s)

    @app.template_filter()
    def json(value, extend=None, dynamic=None):
        """
        Convert given "value" dictionary to JSON representation.

        If an "extend" option is given, it should be an existing JSON
        representation via markupsafe, e.g. from the parent template.
        The given values will be added to it.

        If a "dynamic" option is given, extra so-called dynamic elements
        will be added to the dictionary.  This option is a list of tuples,
        one for each set of dynamic elements, containing:
        * The element prefix.
        * The list of elements to generate.
        * A true value if we need to use the "id" attribute of the elements.
        * A dictionary in which to look up the elements.
        * The default value to supply for undefined entries.
        """

        if extend is not None:
            extend = json_module.loads(extend.unescape())
            extend.update(value)
            value = extend

        if dynamic is not None:
            for (prefix, elements, use_id, values, default) in dynamic:
                for element in elements:
                    if use_id:
                        element = element.id
                    value['{}_{}'.format(prefix, element)] = \
                        values.get(element, default)

        return json_module.dumps(value)

    @app.template_filter()
    def proposal_state_name(value):
        try:
            return ProposalState.get_name(value)
        except KeyError:
            return 'Unknown state'

    @app.template_filter()
    def proposal_state_short_name(value):
        try:
            return ProposalState.get_short_name(value)
        except KeyError:
            return '?'

    @app.template_filter()
    def publication_type_name(value):
        if value is None:
            return ''
        return PublicationType.get_info(value).name

    @app.template_filter()
    def reviewer_role_name(value):
        try:
            return ReviewerRole.get_name(value)
        except KeyError:
            return 'Unknown role'

    @app.template_filter()
    def reviewer_role_class(value):
        try:
            return 'reviewer_{}'.format(
                ReviewerRole.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def text_role_short_name(value):
        return TextRole.short_name(value)

    @app.template_filter()
    def abbr(value, length=20):
        """
        Filter to truncate the text to the given length and return
        it as an "abbr" element.  If the text is already shorter than
        specified then it is simply returned as is.
        """

        if value is None:
            return ''

        if len(value) <= length:
            return value

        return Markup('<abbr title="') + value + Markup('">') + \
            value[:length] + Markup('&hellip;</abbr>')

    @app.template_test()
    def attachment_new(value):
        return (value == AttachmentState.NEW)

    @app.template_test()
    def attachment_ready(value):
        return AttachmentState.is_ready(value)

    @app.template_test()
    def attachment_error(value):
        return AttachmentState.is_error(value)

    @app.template_test()
    def proposal_state_review(value):
        return (value == ProposalState.REVIEW)

    @app.template_test()
    def reviewer_role_external(value):
        return (value == ReviewerRole.EXTERNAL)

    @app.template_test()
    def reviewer_role_review(value):
        return ReviewerRole.is_name_review(value)

    app.add_template_filter(format_text)


class Counter(object):
    def __init__(self, start_value):
        self.value = start_value

    def __call__(self):
        current_value = self.value
        self.value += 1
        return current_value
