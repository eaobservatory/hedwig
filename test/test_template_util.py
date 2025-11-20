# Copyright (C) 2016-2024 East Asian Observatory
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

from jinja2.runtime import Undefined
from markupsafe import Markup

from hedwig.astro.coord import CoordSystem
from hedwig.type.collection import MemberCollection
from hedwig.type.enum import AnnotationType, Assessment, AttachmentState, \
    BaseCallType, BaseReviewerRole, BaseTextRole, CallState, \
    MessageState, MessageThreadType, ProposalState, ProposalType, \
    PublicationType, RequestState, ReviewState, \
    SemesterState, SyncOperation, UserLogEvent
from hedwig.type.simple import Member
from hedwig.type.util import null_tuple
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

    def test_global_concatenate_lists(self):
        g = self.app.jinja_env.globals['concatenate_lists']

        self.assertEqual(g(), [])
        self.assertEqual(g(None, Undefined(), None), [])
        self.assertEqual(g([1, 2], [3, 4]), [1, 2, 3, 4])
        self.assertEqual(g([1, 2], Undefined()), [1, 2])
        self.assertEqual(g(Undefined(), [3, 4]), [3, 4])

    def test_filter_assessment(self):
        f = self.app.jinja_env.filters['assessment_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(Assessment.FEASIBLE), 'Feasible')

    def test_filter_attachment(self):
        f = self.app.jinja_env.filters['attachment_state_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(AttachmentState.READY), 'Ready')

        f = self.app.jinja_env.filters['attachment_state_class']

        self.assertEqual(f(None), '')
        self.assertEqual(f(AttachmentState.READY), 'att_req_ready')

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

    def test_filter_coord_system(self):
        f = self.app.jinja_env.filters['coord_system_name']

        self.assertEqual(f(None), '')
        self.assertEqual(f(CoordSystem.ICRS), 'ICRS')

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

    def test_filter_fmt_neg(self):
        f = self.app.jinja_env.filters['fmt_neg']

        self.assertEqual(f(None, '{}'), '')
        self.assertEqual(f(123.45, '{:.1f}'), '123.5')
        self.assertEqual(
            f(-123.45, '{:.1f}'),
            '<span class="negative">&minus;123.5</span>')

    def test_filter_fmt_max_dp(self):
        f = self.app.jinja_env.filters['fmt_max_dp']

        self.assertEqual(f(None, 3), '')
        self.assertEqual(f(150, 3), '150')

    def test_filter_fmt_sig_fig(self):
        f = self.app.jinja_env.filters['fmt_sig_fig']

        self.assertEqual(f(None, 3), '')
        self.assertEqual(f(15, 3), '15.0')

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

        c = MemberCollection()
        c[101] = null_tuple(Member)._replace(
            id=101, person_id=201, pi=True, person_name='Person One')
        c[102] = null_tuple(Member)._replace(
            id=102, person_id=202, pi=False, person_name='Person Two')

        self.assertEqual(
            json.loads(f({}, dynamic=[(
                'test', [201, 202, 203], False,
                (c, 'has_person', 'person_id', None), None)])),
            {'test_201': True, 'test_202': True, 'test_203': False})

        self.assertEqual(
            json.loads(f({}, dynamic=[(
                'test', [201, 202, 203], False,
                (c, 'get_person', 'person_id', 'person_name'), 'Unknown')])),
            {'test_201': 'Person One', 'test_202': 'Person Two',
             'test_203': 'Unknown'})

    def test_filter_mangle_email(self):
        f = self.app.jinja_env.filters['mangle_email_address']

        self.assertEqual(f('a@b'), '["&#97;", "&#64;", "&#98;"]')

    def test_filter_message_state(self):
        f = self.app.jinja_env.filters['message_state_name']

        self.assertEqual(f(MessageState.UNSENT), 'Unsent')
        self.assertEqual(f(999), 'Unknown state')

        f = self.app.jinja_env.filters['message_state_class']

        self.assertEqual(f(MessageState.UNSENT), 'att_req_new')
        self.assertEqual(f(999), '')

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

    def test_filter_request_state(self):
        f = self.app.jinja_env.filters['request_state_name']

        self.assertEqual(f(RequestState.NEW), 'Queued')
        self.assertEqual(f(999), 'Unknown state')

        f = self.app.jinja_env.filters['request_state_class']

        self.assertEqual(f(RequestState.NEW), 'att_req_new')
        self.assertEqual(f(999), '')

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

    def test_filter_sync_operation(self):
        f = self.app.jinja_env.filters['sync_operation_name']

        self.assertEqual(f(999), 'Unknown operation')
        self.assertEqual(f(SyncOperation.DELETE), 'Delete')

        f = self.app.jinja_env.filters['sync_operation_class']

        self.assertEqual(f(999), '')
        self.assertEqual(f(SyncOperation.INSERT), 'sync_op_ins')

    def test_filter_text_role(self):
        f = self.app.jinja_env.filters['text_role_name']

        self.assertEqual(f(999, BaseTextRole), 'Unknown role')
        self.assertEqual(f(BaseTextRole.ABSTRACT, BaseTextRole), 'Abstract')

    def test_filter_user_log_event(self):
        f = self.app.jinja_env.filters['user_log_event_description']

        self.assertEqual(f(999), 'Unknown event')
        self.assertEqual(f(UserLogEvent.CREATE), 'Account created')

    def test_filter_abbr(self):
        f = self.app.jinja_env.filters['abbr']

        self.assertEqual(f(None), '')

        self.assertEqual(f('1234567890', 20), '1234567890')

        self.assertEqual(f('1234567890', 5),
                         '<abbr title="1234567890">1234&hellip;</abbr>')

        # Truncates to 3 because of space at position 4 (5 - 1).
        self.assertEqual(f('aaa bbb ccc', 5),
                         '<abbr title="aaa bbb ccc">aaa&hellip;</abbr>')

        self.assertEqual(
            f('999999999', 3, abbreviation=None),
            '<abbr title="999999999">99&hellip;</abbr>')
        self.assertEqual(
            f('999999999', 3, abbreviation='1E10-1'),
            '<abbr title="999999999">1E10-1</abbr>')

    def test_test_annotation(self):
        t = self.app.jinja_env.tests['annotation_proposal_copy']
        self.assertTrue(t(AnnotationType.PROPOSAL_COPY))
        self.assertFalse(t(AnnotationType.PROPOSAL_CONTINUATION))

        t = self.app.jinja_env.tests['annotation_proposal_continuation']
        self.assertFalse(t(AnnotationType.PROPOSAL_COPY))
        self.assertTrue(t(AnnotationType.PROPOSAL_CONTINUATION))

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

    def test_test_request_state(self):
        t = self.app.jinja_env.tests['request_state_ready']

        self.assertTrue(t(RequestState.READY))
        self.assertFalse(t(RequestState.PROCESSING))

        t = self.app.jinja_env.tests['request_state_resettable']

        self.assertTrue(t(RequestState.PROCESSING))
        self.assertTrue(t(RequestState.ERROR))
        self.assertTrue(t(RequestState.EXPIRING))
        self.assertTrue(t(RequestState.EXPIRE_ERROR))
        self.assertFalse(t(RequestState.NEW))
        self.assertFalse(t(RequestState.READY))
        self.assertFalse(t(RequestState.DISCARD))
        self.assertFalse(t(RequestState.EXPIRED))

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

    def test_filter_proposal_type(self):
        f = self.app.jinja_env.filters['proposal_type_name']

        self.assertEqual(f(ProposalType.STANDARD), 'Standard')
        self.assertEqual(f(ProposalType.CONTINUATION), 'Continuation request')
        self.assertEqual(f(999), 'Unknown type')

        f = self.app.jinja_env.filters['proposal_type_short_name']

        self.assertEqual(f(ProposalType.STANDARD), 'Std')
        self.assertEqual(f(ProposalType.CONTINUATION), 'CR')
        self.assertEqual(f(999), '?')

    def test_test_proposal_type(self):
        t = self.app.jinja_env.tests['proposal_type_standard']

        self.assertTrue(t(ProposalType.STANDARD))
        self.assertFalse(t(ProposalType.CONTINUATION))

        t = self.app.jinja_env.tests['proposal_type_continuation']

        self.assertFalse(t(ProposalType.STANDARD))
        self.assertTrue(t(ProposalType.CONTINUATION))
