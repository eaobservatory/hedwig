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

from itertools import groupby
from itertools import chain as _chain
import json as json_module
from operator import attrgetter
import re

from jinja2.runtime import Undefined
from markupsafe import Markup

from ..astro.coord import CoordSystem
from ..compat import first_value as _first_value
from ..config import get_countries
from ..type.enum import AnnotationType, Assessment, \
    AttachmentState, CallState, FigureType, GroupType, \
    MessageState, MessageThreadType, \
    PersonLogEvent, PersonTitle, \
    ProposalState, ProposalType, PublicationType, \
    RequestState, ReviewState, SemesterState, SiteGroupType, UserLogEvent
from ..util import FormatMaxDP, FormatSigFig
from .format import format_message_text, format_text, format_title_markup
from .util import mangle_email_address as _mangle_email_address


def register_template_utils(app):
    """
    Register all of the template utilities with the given Flask app.

    These utilities consist of:

    * Global functions.
    * Filters.
    * Tests.

    :param app: Flask application in which to register the utilities.
    """

    @app.template_global()
    def create_counter(start_value=1):
        return Counter(start_value)

    @app.template_global()
    def combined_class(*classes):
        """
        Takes a sequence of (class, condition) pairs.  Returns a class
        attribute containing a space-separated class list, if any of the
        conditions are true, or an empty string otherwise.
        """

        true_classes = [class_ for (class_, condition) in classes if condition]

        if true_classes:
            return 'class="{}"'.format(' '.join(true_classes))

        return ''

    @app.template_global()
    def concatenate_lists(*lists):
        """
        Takes a sequence of lists.  Returns a concatenated list,
        skipping any entries which are undefined or none.
        """

        result = []

        for value in lists:
            if not (value is None or isinstance(value, Undefined)):
                result.extend(value)

        return result

    @app.template_filter()
    def affiliation_type_name(value, type_class):
        if value is None:
            return ''
        return type_class.get_name(value)

    @app.template_filter()
    def affiliation_type_description(value, type_class):
        if value is None:
            return ''
        return type_class.get_description(value)

    @app.template_filter()
    def assessment_name(value):
        if value is None:
            return ''
        return Assessment.get_name(value)

    @app.template_filter()
    def attachment_state_class(value):
        try:
            return 'att_req_{}'.format(
                AttachmentState.get_display_class(value))
        except KeyError:
            return ''

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
    def call_state_class(value):
        try:
            return 'call_{}'.format(
                CallState.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def call_type_name(value, type_class):
        if value is None:
            return ''
        return type_class.get_name(value)

    @app.template_filter()
    def chain(sequences):
        return _chain(*sequences)

    @app.template_filter()
    def color_scale(value,
                    color_start=(1.0, 1.0, 1.0), color_end=(0.0, 0.5, 0.0)):
        """
        Convert a fractional value (0.0 - 1.0) to an HTML-style color
        by interpolating between `color_start` and `color_end`.
        """

        value = min(max(value, 0.0), 1.0)

        color = [
            int(255 * (start + value * (end - start)))
            for (start, end) in zip(color_start, color_end)]

        return '#{:02X}{:02X}{:02X}'.format(*color)

    @app.template_filter()
    def coord_system_name(value):
        if value is None:
            return ''
        return CoordSystem.get_name(value)

    @app.template_filter()
    def count_true(list_):
        return sum(1 for x in list_ if x)

    @app.template_filter()
    def country_name(value):
        if value is None:
            return ''

        return get_countries().get(value, 'Unknown country')

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
    def fmt_neg(value, format_):
        """
        Format the value using the given format, as `fmt` for a single
        value, but if the value is negative, wrap in a span.negative element
        and add a minus entity.
        """

        if value is None or isinstance(value, Undefined):
            return ''

        if value < 0:
            return Markup('<span class="negative">&minus;') \
                + format_.format(- value) \
                + Markup('</span>')

        return format_.format(value)

    @app.template_filter()
    def title_markup(text):
        """
        Apply possible formatting to "markup" elements found in text
        such as publication titles.
        """

        if text is None or isinstance(text, Undefined):
            return ''

        return format_title_markup(text)

    @app.template_filter()
    def fmt_max_dp(value, digits):
        """
        Format a number using :class:`~hedwig.util.FormatMaxDP`.
        """

        if value is None or isinstance(value, Undefined):
            return ''

        return FormatMaxDP(digits).format(value)

    @app.template_filter()
    def fmt_sig_fig(value, digits):
        """
        Format a number using :class:`~hedwig.util.FormatSigFig`.
        """

        if value is None or isinstance(value, Undefined):
            return ''

        return FormatSigFig(digits).format(value)

    @app.template_filter()
    def first_value(dictionary):
        """
        Extract the first value from a dictionary.

        Similar to the Jinja built in filter "first" but operates on
        the values, using the hedwig.compat.first_value function.
        """

        return _first_value(dictionary)

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
    def full_call_type_name(value, type_class, **kwargs):
        if value is None:
            return ''
        return type_class.get_full_call_name(value, **kwargs)

    @app.template_filter()
    def group_type_name(value):
        if value is None:
            return ''
        return GroupType.get_name(value)

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
                    value['{}_{}'.format(prefix, ('none' if element is None
                                                  else element))] = \
                        values.get(element, default)

        return json_module.dumps(value)

    @app.template_filter()
    def mangle_email_address(value):
        return _mangle_email_address(value)

    @app.template_filter()
    def message_state_class(value):
        try:
            return 'att_req_{}'.format(
                MessageState.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def message_state_name(value):
        try:
            return MessageState.get_name(value)
        except KeyError:
            return 'Unknown state'

    @app.template_filter()
    def message_thread_type_name(value):
        try:
            return MessageThreadType.get_name(value)
        except KeyError:
            return 'Unknown thread type'

    @app.template_filter()
    def person_log_event_description(value):
        try:
            return PersonLogEvent.get_info(value).description
        except KeyError:
            return 'Unknown event'

    @app.template_filter()
    def plain_group_by(value, attr):
        """
        Simple grouping filter.

        This filter is an alternative to the Jinja built-in `groupby`
        filter which does not sort by the grouping key.  The data
        should already be sorted, as for the standard Python
        `itertools.groupby` method` (which this filter is based on).
        """

        for (group_id, group_iter) in groupby(value, attrgetter(attr)):
            yield list(group_iter)

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
    def proposal_type_name(value):
        try:
            return ProposalType.get_name(value)
        except KeyError:
            return 'Unknown type'

    @app.template_filter()
    def proposal_type_short_name(value):
        try:
            return ProposalType.get_short_name(value)
        except KeyError:
            return '?'

    @app.template_filter()
    def publication_type_name(value):
        try:
            return PublicationType.get_name(value)
        except KeyError:
            return ''

    @app.template_filter()
    def publication_type_placeholder(value):
        try:
            return PublicationType.get_info(value).placeholder
        except KeyError:
            return ''

    @app.template_filter()
    def request_state_class(value):
        try:
            return 'att_req_{}'.format(
                RequestState.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def request_state_name(value):
        try:
            return RequestState.get_name(value)
        except KeyError:
            return 'Unknown state'

    @app.template_filter()
    def review_state_name(value):
        try:
            return ReviewState.get_name(value)
        except KeyError:
            return 'Unknown review state'

    @app.template_filter()
    def review_state_class(value):
        try:
            return 'review_{}'.format(
                ReviewState.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def reviewer_role_name(value, role_class, with_review=False):
        try:
            if with_review:
                return role_class.get_name_with_review(value)
            else:
                return role_class.get_name(value)
        except KeyError:
            return 'Unknown role'

    @app.template_filter()
    def reviewer_role_class(value, role_class):
        try:
            return 'reviewer_{}'.format(
                role_class.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def semester_state_name(value):
        try:
            return SemesterState.get_name(value)
        except KeyError:
            return 'Unknown state'

    @app.template_filter()
    def semester_state_class(value):
        try:
            return 'semester_{}'.format(
                SemesterState.get_display_class(value))
        except KeyError:
            return ''

    @app.template_filter()
    def site_group_type_name(value):
        if value is None:
            return ''
        return SiteGroupType.get_name(value)

    @app.template_filter()
    def text_role_name(value, role_class):
        try:
            return role_class.get_name(value)
        except KeyError:
            return 'Unknown role'

    @app.template_filter()
    def title_name(value):
        try:
            return PersonTitle.get_name(value)
        except KeyError:
            return ''

    @app.template_filter()
    def user_log_event_description(value):
        try:
            return UserLogEvent.get_info(value).description
        except KeyError:
            return 'Unknown event'

    @app.template_filter()
    def abbr(value, length=20, abbreviation=None):
        """
        Filter to truncate the text to the given length and return
        it as an "abbr" element.  If the text is already shorter than
        specified then it is simply returned as is.
        """

        if value is None:
            return ''

        if len(value) <= length:
            return value

        if abbreviation is None:
            # Remove 1 from length to allow space for ellipsis.
            length -= 1
            abbreviation = value[:length].rstrip() + Markup('&hellip;')

        return Markup('<abbr title="') + value + Markup('">') + \
            abbreviation + Markup('</abbr>')

    @app.template_test()
    def affiliation_type_standard(value, type_class):
        return (value == type_class.STANDARD)

    @app.template_test()
    def annotation_proposal_copy(value):
        return value == AnnotationType.PROPOSAL_COPY

    @app.template_test()
    def annotation_proposal_continuation(value):
        return value == AnnotationType.PROPOSAL_CONTINUATION

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
    def call_type_standard(value, type_class):
        return (value == type_class.STANDARD)

    @app.template_test()
    def call_type_immediate(value, type_class):
        try:
            return type_class.has_immediate_review(value)
        except KeyError:
            return False

    @app.template_test()
    def figure_type_pdf(value):
        return (value == FigureType.PDF)

    @app.template_test()
    def message_state_resettable(value):
        try:
            return MessageState.get_info(value).resettable
        except KeyError:
            return False

    @app.template_test()
    def none_or_whitespace(value):
        if value is None:
            return True

        return re.match(r'^\s*$', value) is not None

    @app.template_test()
    def proposal_type_standard(value):
        return value == ProposalType.STANDARD

    @app.template_test()
    def proposal_type_continuation(value):
        return value == ProposalType.CONTINUATION

    @app.template_test()
    def request_state_ready(value):
        return RequestState.is_ready(value)

    @app.template_test()
    def request_state_resettable(value):
        return RequestState.is_resettable(value)

    @app.template_test()
    def review_state_done(value):
        return (value == ReviewState.DONE)

    @app.template_test()
    def review_state_present(value):
        return ReviewState.is_present(value)

    @app.template_test()
    def reviewer_role_accepted(value, role_class):
        return role_class.is_accepted_review(value)

    @app.template_test()
    def reviewer_role_assigned(value, role_class):
        return role_class.is_assigned_review(value)

    @app.template_test()
    def reviewer_role_invited(value, role_class):
        return role_class.is_invited_review(value)

    @app.template_test()
    def reviewer_role_review(value, role_class):
        return role_class.is_name_review(value)

    app.add_template_filter(format_text)
    app.add_template_filter(format_message_text)


class Counter(object):
    """
    Counter object for use in Jinja templates.
    """

    def __init__(self, start_value):
        """
        Initialize the counter with a given start value.

        This value will be the first value returned by the counter.
        """

        self.value = start_value

    def __call__(self):
        """
        Get the next counter value.

        The current value is returned and the internal counter incremented.
        This ensures that the given starting value is returned first and
        subsequent calls return values increasing by one each time.
        """

        current_value = self.value
        self.value += 1
        return current_value
