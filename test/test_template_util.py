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

from datetime import datetime
import json

from flask import Markup

from hedwig.type.enum import Assessment, AttachmentState, \
    BaseReviewerRole, CallState, \
    MessageState, MessageThreadType, ProposalState, \
    PublicationType, ReviewState, SemesterState
from hedwig.web.template_util import Counter

from .dummy_app import WebAppTestCase


class TemplateUtilTestCase(WebAppTestCase):
    def test_global_counter(self):
        cc = self.app.jinja_env.globals['create_counter']

        c = cc(10)
        self.assertIsInstance(c, Counter)
        self.assertEqual(c.value, 10)

        self.assertEqual(c(), 10)
        self.assertEqual(c(), 11)
        self.assertEqual(c(), 12)

        self.assertEqual(c.value, 13)

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

    def test_filter_format_datetime(self):
        fd = self.app.jinja_env.filters['format_date']
        ft = self.app.jinja_env.filters['format_time']
        fdt = self.app.jinja_env.filters['format_datetime']

        dt = datetime(2016, 4, 1, 15, 0, 0)

        self.assertEqual(fd(dt), '2016-04-01')
        self.assertEqual(ft(dt), '15:00')
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

    def test_test_message_state(self):
        t = self.app.jinja_env.tests['message_state_active']

        self.assertTrue(t(MessageState.SENDING))
        self.assertFalse(t(MessageState.DISCARD))

    def test_test_review_state(self):
        t = self.app.jinja_env.tests['review_state_done']

        self.assertTrue(t(ReviewState.DONE))
        self.assertFalse(t(ReviewState.NOT_DONE))

        t = self.app.jinja_env.tests['review_state_not_done']

        self.assertFalse(t(ReviewState.DONE))
        self.assertTrue(t(ReviewState.NOT_DONE))

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
