# Copyright (C) 2016-2017 East Asian Observatory
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

from datetime import datetime
import json

from flask import Markup

from hedwig.type.enum import Assessment, AttachmentState, \
    BaseCallType, BaseReviewerRole, CallState, \
    MessageState, MessageThreadType, ProposalState, \
    PublicationType, ReviewState, SemesterState, UserLogEvent
from hedwig.web.template_util import Counter

from .base_app import WebAppTestCase


class TemplateUtilTestCase(WebAppTestCase):
    def test_global_counter(self):
        g = self.app.jinja_env.globals['create_counter']

        c = g(10)
        self.assertIsInstance(c, Counter)
        self.assertEqual(c.value, 10)

        self.assertEqual(c(), 10)
        self.assertEqual(c(), 11)
        self.assertEqual(c(), 12)

        self.assertEqual(c.value, 13)

    def test_global_combined_class(self):
        g = self.app.jinja_env.globals['combined_class']

        self.assertEqual(g(('a', True), ('b', True)), 'class="a b"')
        self.assertEqual(g(('a', False), ('b', True)), 'class="b"')
        self.assertEqual(g(('a', True), ('b', False)), 'class="a"')
        self.assertEqual(g(('a', False), ('b', False)), '')

    def test_filter_assessment(self):
        f = self.app.jinja_env.filters['assessment_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(Assessment.FEASIBLE), 'Feasible')

    def test_filter_attachment(self):
        f = self.app.jinja_env.filters['attachment_state_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(AttachmentState.READY), 'Ready')

    def test_filter_call(self):
        f = self.app.jinja_env.filters['call_state_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(CallState.OPEN), 'Open')

        f = self.app.jinja_env.filters['call_type_name']

        self.assertEqual(f(None, BaseCallType), '')
        self.assertEqual(f(BaseCallType.STANDARD, BaseCallType), 'Standard')

        f = self.app.jinja_env.filters['full_call_type_name']
        self.assertEqual(f(None, BaseCallType), '')
        self.assertEqual(f(BaseCallType.STANDARD, BaseCallType),
                         'standard call for proposals')
        self.assertEqual(f(BaseCallType.STANDARD, BaseCallType, plural=True),
                         'standard calls for proposals')

    def test_filter_chain(self):
        f = self.app.jinja_env.filters['chain']

        self.assertEqual(list(f(([1, 2], [3, 4]))), [1, 2, 3, 4])

    def test_filter_color_scale(self):
        f = self.app.jinja_env.filters['color_scale']

        # Test normal values.
        self.assertEqual(f(0.0), '#FFFFFF')
        self.assertEqual(f(1.0), '#007F00')

        self.assertEqual(f(0.5), '#7FBF7F')

        # Test values beyond the 0.0 - 1.0 range.
        self.assertEqual(f(-1.0), '#FFFFFF')
        self.assertEqual(f(2.0), '#007F00')

        # Test custom scale.
        self.assertEqual(f(0.0, (0.0, 0.75, 0.0), (0.25, 0.0, 0.5)), '#00BF00')
        self.assertEqual(f(1.0, (0.0, 0.75, 0.0), (0.25, 0.0, 0.5)), '#3F007F')

    def test_filter_count_true(self):
        f = self.app.jinja_env.filters['count_true']

        self.assertEqual(f([]), 0)
        self.assertEqual(f([False, False, False, False]), 0)
        self.assertEqual(f([False, True,  False, False]), 1)
        self.assertEqual(f([False, True,  False, True]),  2)
        self.assertEqual(f([True,  True,  False, True]),  3)
        self.assertEqual(f([True,  True,  True,  True]),  4)

    def test_filter_country_name(self):
        f = self.app.jinja_env.filters['country_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f('US'), 'United States')
        self.assertEqual(f('BX'), 'Unknown country')

    def test_filter_fmt(self):
        f = self.app.jinja_env.filters['fmt']

        self.assertEqual(f(None, '<{}>'), '')
        self.assertEqual(f(40, '<{}>'), '<40>')
        self.assertEqual(f((30, 40), '<{}, {}>'), '<30, 40>')

    def test_filter_first_value(self):
        f = self.app.jinja_env.filters['first_value']

        self.assertEqual(f({'lone_key': 'lone_value'}), 'lone_value')

    def test_filter_format_datetime(self):
        fdt = self.app.jinja_env.filters['format_datetime']

        dt = datetime(2016, 4, 1, 15, 0, 0)

        self.assertEqual(fdt(dt), '2016-04-01 15:00')

    def test_filter_format_hours_hms(self):
        f = self.app.jinja_env.filters['format_hours_hms']

        self.assertEqual(f(0.5), '0:30:00')

        self.assertEqual(f(3.755), '3:45:18')

    def test_filter_json(self):
        f = self.app.jinja_env.filters['json']

        d = {'a': 'b'}
        j = f(d)
        self.assertIsInstance(j, str)
        self.assertEqual(json.loads(j), d)

        # Test usage of the "extend" parameter".
        self.assertEqual(json.loads(f({'c': 'd'}, extend=Markup(j))),
                         {'a': 'b', 'c': 'd'})

        # Test usage of the "dynamic" parameter.
        self.assertEqual(
            json.loads(f({'e': 'f'}, dynamic=[
                ('test', [1, 2, 3], False, {1: 'one', 2: 'two'}, 'null')])),
            {'e': 'f', 'test_1': 'one', 'test_2': 'two', 'test_3': 'null'})

    def test_filter_mangle_email(self):
        f = self.app.jinja_env.filters['mangle_email_address']

        self.assertEqual(f('a@b'), '["&#97;", "&#64;", "&#98;"]')

    def test_filter_message_state(self):
        f = self.app.jinja_env.filters['message_state_name']

        self.assertEqual(f(MessageState.UNSENT), 'Unsent')
        self.assertEqual(f(999), 'Unknown state')

    def test_filter_message_thread(self):
        f = self.app.jinja_env.filters['message_thread_type_name']

        self.assertEqual(f(MessageThreadType.REVIEW_INVITATION),
                         'Review invitation')
        self.assertEqual(f(999), 'Unknown thread type')

    def test_filter_proposal_state(self):
        f = self.app.jinja_env.filters['proposal_state_name']

        self.assertEqual(f(ProposalState.SUBMITTED), 'Submitted')
        self.assertEqual(f(999), 'Unknown state')

        f = self.app.jinja_env.filters['proposal_state_short_name']

        self.assertEqual(f(ProposalState.REVIEW), 'Rev')
        self.assertEqual(f(999), '?')

    def test_filter_publication_type(self):
        f = self.app.jinja_env.filters['publication_type_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(PublicationType.ARXIV), 'arXiv article ID')

        f = self.app.jinja_env.filters['publication_type_placeholder']
        self.assertEqual(f(None), '')
        self.assertEqual(f(PublicationType.ARXIV), '0000.00000')

    def test_filter_review_state(self):
        f = self.app.jinja_env.filters['review_state_name']

        self.assertEqual(f(ReviewState.NOT_DONE), 'Not done')

        self.assertEqual(f(999), 'Unknown review state')

        f = self.app.jinja_env.filters['review_state_class']

        self.assertEqual(f(ReviewState.NOT_DONE), 'review_not_done')
        self.assertEqual(f(ReviewState.DONE), 'review_done')
        self.assertEqual(f(999), '')

    def test_filter_reviewer_role(self):
        f = self.app.jinja_env.filters['reviewer_role_name']

        self.assertEqual(f(None, BaseReviewerRole),
                         'Unknown role')
        self.assertEqual(f(BaseReviewerRole.EXTERNAL, BaseReviewerRole),
                         'External')

        self.assertEqual(
            f(None, BaseReviewerRole, with_review=True),
            'Unknown role')

        self.assertEqual(
            f(BaseReviewerRole.TECH, BaseReviewerRole, with_review=True),
            'Technical Review')

        self.assertEqual(
            f(BaseReviewerRole.FEEDBACK, BaseReviewerRole, with_review=True),
            'Feedback')

        f = self.app.jinja_env.filters['reviewer_role_class']

        self.assertEqual(f(999, BaseReviewerRole),
                         '')
        self.assertEqual(f(BaseReviewerRole.EXTERNAL, BaseReviewerRole),
                         'reviewer_ext')

    def test_filter_person_title(self):
        f = self.app.jinja_env.filters['title_name']

        self.assertEqual(f(999), '')
        self.assertEqual(f(1), 'Dr.')

    def test_filter_semester_state(self):
        f = self.app.jinja_env.filters['semester_state_name']

        self.assertEqual(f(999), 'Unknown state')
        self.assertEqual(f(SemesterState.PAST), 'Past')

    def test_filter_user_log_event(self):
        f = self.app.jinja_env.filters['user_log_event_description']

        self.assertEqual(f(999), 'Unknown event')
        self.assertEqual(f(UserLogEvent.CREATE), 'Account created')

    def test_filter_abbr(self):
        f = self.app.jinja_env.filters['abbr']

        self.assertEqual(f(None), '')

        self.assertEqual(f('1234567890', 20), '1234567890')

        self.assertEqual(f('1234567890', 5),
                         '<abbr title="1234567890">12345&hellip;</abbr>')

    def test_test_attachment(self):
        t = self.app.jinja_env.tests['attachment_new']
        self.assertTrue(t(AttachmentState.NEW))
        self.assertFalse(t(AttachmentState.ERROR))
        self.assertFalse(t(AttachmentState.READY))

        t = self.app.jinja_env.tests['attachment_ready']
        self.assertFalse(t(AttachmentState.NEW))
        self.assertFalse(t(AttachmentState.ERROR))
        self.assertTrue(t(AttachmentState.READY))

        t = self.app.jinja_env.tests['attachment_error']
        self.assertFalse(t(AttachmentState.NEW))
        self.assertTrue(t(AttachmentState.ERROR))
        self.assertFalse(t(AttachmentState.READY))

    def test_test_call(self):
        t = self.app.jinja_env.tests['call_type_standard']

        self.assertTrue(t(BaseCallType.STANDARD, BaseCallType))
        self.assertFalse(t(BaseCallType.IMMEDIATE, BaseCallType))

        t = self.app.jinja_env.tests['call_type_immediate']

        self.assertFalse(t(BaseCallType.STANDARD, BaseCallType))
        self.assertTrue(t(BaseCallType.IMMEDIATE, BaseCallType))
        self.assertFalse(t(999, BaseCallType))

    def test_test_none_or_whitespace(self):
        t = self.app.jinja_env.tests['none_or_whitespace']

        self.assertTrue(t(None))
        self.assertTrue(t(''))
        self.assertTrue(t(' \t '))
        self.assertFalse(t('x'))
        self.assertFalse(t(' x'))
        self.assertFalse(t('x '))

    def test_test_message_state(self):
        t = self.app.jinja_env.tests['message_state_resettable']

        self.assertTrue(t(MessageState.SENDING))
        self.assertFalse(t(MessageState.DISCARD))

    def test_test_review_state(self):
        t = self.app.jinja_env.tests['review_state_done']

        self.assertTrue(t(ReviewState.DONE))
        self.assertFalse(t(ReviewState.NOT_DONE))

        t = self.app.jinja_env.tests['review_state_present']

        self.assertTrue(t(ReviewState.DONE))
        self.assertFalse(t(ReviewState.NOT_DONE))

    def test_test_reviewer_role(self):
        t = self.app.jinja_env.tests['reviewer_role_invited']

        self.assertFalse(t(BaseReviewerRole.TECH, BaseReviewerRole))
        self.assertTrue(t(BaseReviewerRole.EXTERNAL, BaseReviewerRole))

        t = self.app.jinja_env.tests['reviewer_role_review']

        self.assertTrue(t(BaseReviewerRole.EXTERNAL, BaseReviewerRole))
        self.assertFalse(t(BaseReviewerRole.FEEDBACK, BaseReviewerRole))

    def test_filter_format_text(self):
        f = self.app.jinja_env.filters['format_text']

        self.assertEqual(f('Hello'), '<p>Hello</p>')
