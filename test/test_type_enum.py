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

from collections import OrderedDict
from unittest import TestCase

from hedwig.error import Error, NoSuchValue
from hedwig.type.enum import \
    Assessment, AttachmentState, \
    BaseCallType, BaseReviewerRole, BaseTextRole, \
    CallState, GroupType, \
    MessageState, PersonTitle, ProposalState, ReviewState, SemesterState


class EnumTypeTestCase(TestCase):
    def test_assessment(self):
        self.assertTrue(Assessment.is_valid(Assessment.PROBLEM))
        self.assertFalse(Assessment.is_valid(999))

        name = Assessment.get_name(Assessment.FEASIBLE)
        self.assertIsInstance(name, unicode)

        options = Assessment.get_options()
        self.assertIsInstance(options, OrderedDict)

        for (k, v) in options.items():
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, unicode)

    def test_attachment_state(self):
        # Get list of all states for subsequent tests.
        states = list(AttachmentState._info.keys())

        self.assertFalse(AttachmentState.is_valid(999))

        unready = AttachmentState.unready_states()
        self.assertIsInstance(unready, list)

        for state in states:
            self.assertTrue(AttachmentState.is_valid(state))
            self.assertIsInstance(AttachmentState.get_name(state), unicode)

            if state == AttachmentState.READY:
                self.assertNotIn(state, unready)
                self.assertTrue(AttachmentState.is_ready(state))
            else:
                self.assertIn(state, unready)
                self.assertFalse(AttachmentState.is_ready(state))

            if state == AttachmentState.ERROR:
                self.assertTrue(AttachmentState.is_error(state))
            else:
                self.assertFalse(AttachmentState.is_error(state))

    def test_call_state(self):
        states = [CallState.UNOPENED, CallState.OPEN, CallState.CLOSED]

        self.assertEqual(CallState.get_name(CallState.OPEN), 'Open')

        for state in states:
            self.assertIsInstance(CallState.get_name(state), unicode)

    def test_call_type(self):
        self.assertTrue(BaseCallType.is_valid(BaseCallType.STANDARD))
        self.assertFalse(BaseCallType.is_valid(999))

        options = BaseCallType.get_options()
        self.assertIsInstance(options, OrderedDict)

        self.assertIn(BaseCallType.STANDARD, options)

        for (type_, type_name) in options.items():
            self.assertIsInstance(type_, int)
            self.assertIsInstance(type_name, unicode)

        self.assertIsNone(BaseCallType.get_code(BaseCallType.STANDARD))
        self.assertIsInstance(BaseCallType.get_code(BaseCallType.IMMEDIATE),
                              unicode)

        self.assertEqual(BaseCallType.by_code(None), BaseCallType.STANDARD)
        self.assertEqual(BaseCallType.by_code('I'), BaseCallType.IMMEDIATE)

        with self.assertRaisesRegexp(NoSuchValue, 'Code "X" not recognised'):
            BaseCallType.by_code('X')

        class NoNullCallType(BaseCallType):
            _info = OrderedDict(((
                BaseCallType.IMMEDIATE,
                BaseCallType.get_info(BaseCallType.IMMEDIATE)),))

        self.assertEqual(NoNullCallType.by_code('I'), NoNullCallType.IMMEDIATE)
        with self.assertRaisesRegexp(NoSuchValue, 'Null code not recognised'):
            NoNullCallType.by_code(None)

    def test_message_state(self):
        # Test "get_name" method.
        self.assertEqual(MessageState.get_name(MessageState.UNSENT), 'Unsent')

        # Test "get_info" method.
        state = MessageState.get_info(MessageState.DISCARD)
        self.assertEqual(state.name, 'Discarded')
        self.assertFalse(state.active)
        self.assertTrue(state.settable)

        # Test "is_valid" method.
        self.assertFalse(MessageState.is_valid(999))
        self.assertFalse(MessageState.is_valid(MessageState.SENDING))
        self.assertTrue(MessageState.is_valid(MessageState.SENDING,
                                              allow_unsettable=True))
        self.assertTrue(MessageState.is_valid(MessageState.UNSENT,
                                              allow_unsettable=True))
        self.assertTrue(MessageState.is_valid(MessageState.UNSENT))

        # Test "get_options" method.
        states = MessageState.get_options()
        self.assertIsInstance(states, dict)
        self.assertEqual(set(states.keys()),
                         set((MessageState.UNSENT, MessageState.SENDING,
                              MessageState.SENT, MessageState.DISCARD)))

        states = MessageState.get_options(settable=True)
        self.assertIsInstance(states, dict)
        self.assertEqual(set(states.keys()),
                         set((MessageState.UNSENT, MessageState.DISCARD)))

    def test_person_title(self):
        # Since the PersonTitle class doesn't provide value attributes,
        # assume that Dr. corresponds to the integer 1.
        DR = 1

        self.assertEqual(PersonTitle.get_name(DR), 'Dr.')

        self.assertTrue(PersonTitle.is_valid(DR))

        self.assertFalse(PersonTitle.is_valid(999))

        options = PersonTitle.get_options()

        for (key, title) in options.items():
            self.assertIsInstance(key, int)
            self.assertIsInstance(title, unicode)

        option_values = list(options.values())
        for title in ('Dr. Miss Mr. Mrs. Ms. Prof.'.split(' ')):
            self.assertIn(title, option_values)

    def test_proposal_state(self):
        options = ProposalState.get_options()
        self.assertIsInstance(options, OrderedDict)

        states = set()
        for state in (
                ProposalState.PREPARATION,
                ProposalState.SUBMITTED,
                ProposalState.WITHDRAWN,
                ProposalState.REVIEW,
                ProposalState.ACCEPTED,
                ProposalState.REJECTED,
                ):
            # Check state is an integer.
            self.assertIsInstance(state, int)
            self.assertNotIn(state, states)

            # Check state is unique.
            states.add(state)

            # State should be considered valid.
            self.assertTrue(ProposalState.is_valid(state))

            # State should have a name.
            self.assertIsInstance(ProposalState.get_name(state), unicode)

            # State should have boolean "can_edit" property.
            self.assertIn(ProposalState.can_edit(state), (True, False))

            # State should be in the options list.
            self.assertIn(state, options)
            self.assertIsInstance(options[state], unicode)
            self.assertEqual(options[state], ProposalState.get_name(state))

        self.assertFalse(ProposalState.is_valid(999))

        states = ProposalState.editable_states()
        self.assertIsInstance(states, list)
        self.assertIn(ProposalState.PREPARATION, states)
        self.assertNotIn(ProposalState.REVIEW, states)

        states = ProposalState.submitted_states()
        self.assertIsInstance(states, list)
        self.assertNotIn(ProposalState.PREPARATION, states)
        self.assertIn(ProposalState.REVIEW, states)

        states = ProposalState.review_states()
        self.assertIsInstance(states, list)
        self.assertEqual(
            set(states),
            set((ProposalState.REVIEW, ProposalState.FINAL_REVIEW)))

        states = ProposalState.reviewed_states()
        self.assertIsInstance(states, list)
        self.assertNotIn(ProposalState.PREPARATION, states)
        self.assertNotIn(ProposalState.SUBMITTED, states)
        self.assertNotIn(ProposalState.ABANDONED, states)
        self.assertIn(ProposalState.ACCEPTED, states)
        self.assertIn(ProposalState.REJECTED, states)
        self.assertTrue(ProposalState.is_reviewed(ProposalState.ACCEPTED))
        self.assertTrue(ProposalState.is_reviewed(ProposalState.REJECTED))
        self.assertFalse(ProposalState.is_reviewed(ProposalState.REVIEW))
        self.assertFalse(ProposalState.is_reviewed(ProposalState.ABANDONED))

        self.assertEqual(ProposalState.by_name('accepted'),
                         ProposalState.ACCEPTED)
        with self.assertRaisesRegexp(NoSuchValue, 'not recognised'):
            ProposalState.by_name('not a real state')

    def test_group_type(self):
        options = GroupType.get_options()
        self.assertIsInstance(options, OrderedDict)

        for (k, v) in options.items():
            self.assertIsInstance(k, int)
            self.assertTrue(GroupType.is_valid(k))

            self.assertIsInstance(v, unicode)

            i = GroupType.get_info(k)
            self.assertIsInstance(i, tuple)
            self.assertIsInstance(i.name, unicode)
            self.assertIsInstance(i.view_all_prop, bool)
            self.assertIsInstance(i.private_moc, bool)
            self.assertIsInstance(i.url_path, unicode)
            self.assertEqual(i.name, v)

            self.assertEqual(GroupType.url_path(k), i.url_path)

            self.assertEqual(GroupType.by_url_path(i.url_path), k)

        self.assertFalse(GroupType.is_valid(999999))

        self.assertIsInstance(GroupType.view_all_groups(), list)
        self.assertIsInstance(GroupType.private_moc_groups(), list)
        self.assertIsInstance(GroupType.review_coord_groups(), list)

        url_paths = GroupType.get_url_paths()
        self.assertIsInstance(url_paths, list)
        for url_path in url_paths:
            self.assertIsInstance(url_path, unicode)

    def test_review_state(self):
        self.assertEqual(ReviewState.get_name(ReviewState.NOT_DONE),
                         'Not done')

        self.assertTrue(ReviewState.is_valid(ReviewState.DONE))

        self.assertFalse(ReviewState.is_valid(999))

    def test_reviewer_role(self):
        for role in [
                BaseReviewerRole.TECH,
                BaseReviewerRole.EXTERNAL,
                BaseReviewerRole.CTTEE_PRIMARY,
                BaseReviewerRole.CTTEE_SECONDARY,
                BaseReviewerRole.CTTEE_OTHER]:
            self.assertTrue(BaseReviewerRole.is_valid(role))

            info = BaseReviewerRole.get_info(role)

            self.assertIsInstance(info, tuple)
            self.assertIsInstance(info.name, unicode)
            self.assertIsInstance(info.unique, bool)
            self.assertIsInstance(info.text, bool)
            self.assertIsInstance(info.assessment, bool)
            self.assertIsInstance(info.rating, bool)
            self.assertIsInstance(info.weight, bool)

        self.assertFalse(BaseReviewerRole.is_valid(999999))

        self.assertEqual(BaseReviewerRole.get_cttee_roles(), [
            BaseReviewerRole.CTTEE_PRIMARY,
            BaseReviewerRole.CTTEE_SECONDARY,
            BaseReviewerRole.CTTEE_OTHER,
        ])

        self.assertEqual(BaseReviewerRole.get_feedback_roles(), [
            BaseReviewerRole.CTTEE_PRIMARY,
            BaseReviewerRole.CTTEE_SECONDARY,
        ])

        self.assertEqual(
            BaseReviewerRole.get_editable_states(
                BaseReviewerRole.EXTERNAL),
            [ProposalState.REVIEW])

        self.assertEqual(
            BaseReviewerRole.get_editable_states(
                BaseReviewerRole.CTTEE_PRIMARY),
            [ProposalState.REVIEW, ProposalState.FINAL_REVIEW])

        self.assertEqual(
            BaseReviewerRole.get_editable_states(
                BaseReviewerRole.FEEDBACK),
            [ProposalState.FINAL_REVIEW])

        self.assertEqual(
            BaseReviewerRole.get_editable_roles(ProposalState.PREPARATION), [])

        self.assertEqual(
            BaseReviewerRole.get_editable_roles(ProposalState.REVIEW), [
                BaseReviewerRole.TECH,
                BaseReviewerRole.EXTERNAL,
                BaseReviewerRole.CTTEE_PRIMARY,
                BaseReviewerRole.CTTEE_SECONDARY,
                BaseReviewerRole.CTTEE_OTHER])

        self.assertEqual(
            BaseReviewerRole.get_editable_roles(ProposalState.FINAL_REVIEW), [
                BaseReviewerRole.TECH,
                BaseReviewerRole.CTTEE_PRIMARY,
                BaseReviewerRole.CTTEE_SECONDARY,
                BaseReviewerRole.CTTEE_OTHER,
                BaseReviewerRole.FEEDBACK])

        self.assertEqual(
            BaseReviewerRole.get_editable_roles(ProposalState.ACCEPTED), [])

        self.assertEqual(
            set(BaseReviewerRole.get_rating_viewable_states(
                BaseReviewerRole.EXTERNAL)),
            set((ProposalState.REVIEW, ProposalState.FINAL_REVIEW,
                 ProposalState.ACCEPTED, ProposalState.REJECTED)))

        self.assertEqual(
            set(BaseReviewerRole.get_rating_viewable_states(
                BaseReviewerRole.CTTEE_PRIMARY)),
            set((ProposalState.FINAL_REVIEW,
                 ProposalState.ACCEPTED, ProposalState.REJECTED)))

    def test_semester_state(self):
        states = [SemesterState.FUTURE, SemesterState.CURRENT,
                  SemesterState.PAST]

        self.assertEqual(SemesterState.get_name(SemesterState.FUTURE),
                         'Future')

        for state in states:
            self.assertIsInstance(SemesterState.get_name(state), unicode)

    def test_text_role(self):
        self.assertTrue(BaseTextRole.is_valid(BaseTextRole.ABSTRACT))
        self.assertFalse(BaseTextRole.is_valid(999))

        self.assertIsInstance(
            BaseTextRole.get_name(BaseTextRole.TECHNICAL_CASE),
            unicode)

        self.assertIsInstance(
            BaseTextRole.short_name(BaseTextRole.SCIENCE_CASE),
            unicode)

        self.assertIsInstance(
            BaseTextRole.url_path(BaseTextRole.TECHNICAL_CASE),
            unicode)

        with self.assertRaisesRegexp(Error, 'has no URL path'):
            BaseTextRole.url_path(BaseTextRole.TOOL_NOTE)

        self.assertEqual(
            BaseTextRole.get_url_paths(), ['technical', 'scientific'])

        self.assertEqual(BaseTextRole.by_url_path('scientific'),
                         BaseTextRole.SCIENCE_CASE)
        self.assertEqual(BaseTextRole.by_url_path('technical'),
                         BaseTextRole.TECHNICAL_CASE)

        with self.assertRaisesRegexp(NoSuchValue, 'path .* not recognised'):
            BaseTextRole.by_url_path('something_else')

        self.assertIsNone(BaseTextRole.by_url_path('something_else', None))
