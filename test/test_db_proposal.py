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

from datetime import datetime

from hedwig.compat import first_value
from hedwig.db.meta import member
from hedwig.error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord, NoSuchValue, UserError
from hedwig.type.collection import AffiliationCollection, AnnotationCollection, \
    CallCollection, CallMidCloseCollection, MemberCollection, \
    PrevProposalCollection, \
    ProposalCollection, ProposalCategoryCollection, \
    ProposalFigureCollection, ProposalTextCollection, \
    ResultCollection, TargetCollection
from hedwig.type.enum import BaseAffiliationType, AnnotationType, \
    AttachmentState, \
    BaseCallType, BaseTextRole, \
    CallState, FigureType, \
    FormatType, PublicationType, ProposalState, ProposalType, RequestState
from hedwig.type.simple import Affiliation, Annotation, \
    Call, CallMidClose, CallPreamble, Category, \
    Member, MemberInfo, MemberInstitution, \
    PrevProposal, PrevProposalPub, \
    Proposal, ProposalCategory, ProposalFigureInfo, ProposalPDFInfo, \
    ProposalText, RequestPropCopy, RequestPropPDF, Target
from hedwig.type.util import null_tuple
from .dummy_db import DBTestCase


class DBProposalTest(DBTestCase):
    def test_facility(self):
        # Test the ensure_facility method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        facility_id_copy = self.db.ensure_facility('my_tel')
        facility_id_diff = self.db.ensure_facility('my_other_tel')

        self.assertEqual(facility_id_copy, facility_id)
        self.assertNotEqual(facility_id_diff, facility_id)

    def test_affiliation(self):
        # Get test facility ID.
        facility_id = self.db.ensure_facility('test_tel')
        self.assertIsInstance(facility_id, int)
        queue_id = self.db.add_queue(facility_id, 'Queue1', 'Q1')
        self.assertIsInstance(queue_id, int)

        # Check we have no affiliations to start.
        result = self.db.search_affiliation(queue_id=queue_id)
        self.assertIsInstance(result, AffiliationCollection)
        self.assertEqual(len(result), 0)

        # Generate a collection of 2 records and sync it.
        records = AffiliationCollection()
        records[0] = Affiliation(
            None, queue_id, 'Aff 1', True, BaseAffiliationType.STANDARD, None)
        records[1] = Affiliation(
            None, queue_id, 'Aff 2', False, BaseAffiliationType.STANDARD, None)

        n = self.db.sync_queue_affiliation(
            BaseAffiliationType, queue_id, records)
        self.assertEqual(n, (2, 0, 0))

        # Check that we now have the expected 2 records.
        result = self.db.search_affiliation(queue_id=queue_id)
        self.assertIsInstance(result, AffiliationCollection)
        self.assertEqual(len(result), 2)
        for (row, expect_name, expect_hidden) in zip(
                result.values(), ('Aff 1', 'Aff 2'), (True, False)):
            self.assertIsInstance(row.id, int)
            self.assertEqual(row.name, expect_name)
            self.assertEqual(row.hidden, expect_hidden)

        # Check we can't remove an affiliation once it is in use.
        semester_id = self.db.add_semester(
            facility_id, 'Sem1', 'S1',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        call_id = self.db.add_call(
            BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            1, 1, 1, 1, 1, 1, 1, 1, 1, '', '', '',
            FormatType.PLAIN, False, False, None, None, False, False,
            '', 500, 4, 1, 366)
        person_id = self.db.add_person('Person1')
        (affiliation_id, affiliation_record) = result.popitem()
        self.db.add_proposal(call_id, person_id, affiliation_id, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.sync_queue_affiliation(
                BaseAffiliationType, queue_id, result)

        # Test affiliation weights: first make a second call.
        semester_id_2 = self.db.add_semester(
            facility_id, 'Sem2', 'S2',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        call_id_2 = self.db.add_call(
            BaseCallType, semester_id_2, queue_id, BaseCallType.STANDARD,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            1, 1, 1, 1, 1, 1, 1, 1, 1, '', '', '',
            FormatType.PLAIN, False, False, None, None, False, False,
            '', 500, 4, 1, 366)

        # Store different sets of weights for the two calls.
        result = self.db.search_affiliation(queue_id=queue_id,
                                            with_weight_call_id=call_id)

        self.assertEqual(len(result), 2)

        weights_1 = [1.2, 7.8]
        weights_2 = [3.4, 6.7]

        records_1 = AffiliationCollection()
        records_2 = AffiliationCollection()

        for (row, weight_1, weight_2) in zip(result.values(),
                                             weights_1, weights_2):
            self.assertIsNone(row.weight)
            records_1[row.id] = row._replace(weight=weight_1)
            records_2[row.id] = row._replace(weight=weight_2)

        self.db.sync_affiliation_weight(
            BaseAffiliationType, call_id, records_1)
        self.db.sync_affiliation_weight(
            BaseAffiliationType, call_id_2, records_2)

        # Check we can recover the two sets of weights.
        result = self.db.search_affiliation(queue_id=queue_id,
                                            with_weight_call_id=call_id)

        self.assertEqual(len(result), 2)

        for (row, weight) in zip(result.values(), weights_1):
            self.assertEqual(row.weight, weight)

        result = self.db.search_affiliation(queue_id=queue_id,
                                            with_weight_call_id=call_id_2)

        self.assertEqual(len(result), 2)

        for (row, weight) in zip(result.values(), weights_2):
            self.assertEqual(row.weight, weight)

    def test_semester(self):
        # Test add_semeseter method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        date_start = datetime(2002, 2, 2)
        date_end = datetime(2002, 8, 1)

        with self.assertRaisesRegex(UserError, 'end date is before start'):
            self.db.add_semester(facility_id, '99A', '99A',
                                 date_end, date_start)

        with self.assertRaisesRegex(ConsistencyError, 'facility does not'):
            self.db.add_semester(1999999, '99A', '99A', date_start, date_end)

        semester_id = self.db.add_semester(facility_id, '99A', '99A',
                                           date_start, date_end)
        self.assertIsInstance(semester_id, int)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_semester(facility_id, '99A', '99A2',
                                 date_start, date_end)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_semester(facility_id, '99A2', '99A',
                                 date_start, date_end)

        semester_id_2 = self.db.add_semester(facility_id, '99B', '99B',
                                             date_start, date_end)
        self.assertIsInstance(semester_id_2, int)
        self.assertNotEqual(semester_id_2, semester_id)

        semesters = self.db.search_semester(facility_id=facility_id)
        self.assertIsInstance(semesters, ResultCollection)
        self.assertEqual(len(semesters), 2)

        # Try updating a record.
        self.assertEqual(self.db.get_semester(facility_id, semester_id).name,
                         '99A')
        self.db.update_semester(semester_id, name='99 (a)')
        self.assertEqual(self.db.get_semester(facility_id, semester_id).name,
                         '99 (a)')
        with self.assertRaisesRegex(ConsistencyError, 'semester does not ex'):
            self.db.update_semester(1999999, name='bad semester')
        with self.assertRaisesRegex(UserError, 'end date is before start'):
            self.db.update_semester(semester_id,
                                    date_start=date_end, date_end=date_start)

        # Check for semesters which don't exist or have wrong facility.
        with self.assertRaises(NoSuchRecord):
            self.db.get_semester(facility_id, 1999999)
        with self.assertRaises(NoSuchRecord):
            self.db.get_semester(1999999, semester_id)

    def test_queue(self):
        # Test add_queue method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        with self.assertRaisesRegex(ConsistencyError, 'facility does not'):
            self.db.add_queue(1999999, 'INT', 'I')

        queue_id = self.db.add_queue(facility_id, 'INT', 'I')
        self.assertIsInstance(queue_id, int)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_queue(facility_id, 'INT', 'I2')

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_queue(facility_id, 'INT2', 'I')

        queue_id_2 = self.db.add_queue(facility_id, 'XYZ', 'XYZ')
        self.assertIsInstance(queue_id_2, int)
        self.assertNotEqual(queue_id_2, queue_id)

        # Try searching: add a queue for another facility first.
        facility_id_2 = self.db.ensure_facility('my_other_tel')
        queue_id_3 = self.db.add_queue(facility_id_2, '???', '?')
        self.assertIsInstance(queue_id_3, int)
        queues = self.db.search_queue(facility_id=facility_id)
        self.assertIsInstance(queues, ResultCollection)
        self.assertEqual(list(queues.keys()), [queue_id, queue_id_2])
        queues = self.db.search_queue(facility_id=facility_id_2)
        self.assertEqual(list(queues.keys()), [queue_id_3])

        # Test affiliation constraint of search.
        self.assertEqual(
            list(self.db.search_queue(
                facility_id=facility_id, has_affiliation=False).keys()),
            [queue_id, queue_id_2])
        self.assertEqual(
            list(self.db.search_queue(
                facility_id=facility_id, has_affiliation=True).keys()),
            [])

        self.db.add_affiliation(
            BaseAffiliationType, queue_id, 'Test affiliation')

        self.assertEqual(
            list(self.db.search_queue(
                facility_id=facility_id, has_affiliation=None).keys()),
            [queue_id, queue_id_2])
        self.assertEqual(
            list(self.db.search_queue(
                facility_id=facility_id, has_affiliation=True).keys()),
            [queue_id])
        self.assertEqual(
            list(self.db.search_queue(
                facility_id=facility_id, has_affiliation=False).keys()),
            [queue_id_2])

        # Try updating a record.
        queue = self.db.get_queue(facility_id_2, queue_id_3)
        self.assertEqual(queue.name, '???')
        self.db.update_queue(queue_id_3, name='!!!')
        queue = self.db.get_queue(facility_id_2, queue_id_3)
        self.assertEqual(queue.name, '!!!')

        # Check test for non-existant queue or facility.
        with self.assertRaises(NoSuchRecord):
            self.db.get_queue(facility_id_2, 1999999)
        with self.assertRaises(NoSuchRecord):
            self.db.get_queue(1999999, queue_id_3)

    def test_call(self):
        # Check that we can create a call for proposals.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)
        semester_id = self.db.add_semester(
            facility_id, 'My Semester', 'MS',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        self.assertIsInstance(semester_id, int)
        queue_id = self.db.add_queue(facility_id, 'My Queue', 'MQ')
        self.assertIsInstance(queue_id, int)

        date_open = datetime(1999, 9, 1)
        date_close = datetime(1999, 9, 30)

        call_id = self.db.add_call(
            BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
            date_open, date_close,
            abst_word_lim=1,
            tech_word_lim=2, tech_fig_lim=7, tech_page_lim=3,
            sci_word_lim=4, sci_fig_lim=5, sci_page_lim=6,
            capt_word_lim=8, expl_word_lim=9,
            tech_note='technical note', sci_note='scientific note',
            prev_prop_note='previous proposal note',
            note_format=FormatType.PLAIN, multi_semester=False, separate=False,
            preamble='preamble text', preamble_format=FormatType.RST,
            hidden=False, allow_continuation=False, cnrq_note='con req note',
            cnrq_word_lim=500, cnrq_fig_lim=4, cnrq_page_lim=1,
            cnrq_max_age=366)
        self.assertIsInstance(call_id, int)

        # Check tests for bad values.
        with self.assertRaisesRegex(ConsistencyError, 'semester does not'):
            self.db.add_call(
                BaseCallType, 1999999, queue_id, BaseCallType.STANDARD,
                date_open, date_close,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, None, None, False,
                False, '', 500, 4, 1, 366)
        with self.assertRaisesRegex(ConsistencyError, 'queue does not'):
            self.db.add_call(
                BaseCallType, semester_id, 1999999, BaseCallType.STANDARD,
                date_open, date_close,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, None, None, False,
                False, '', 500, 4, 1, 366)
        with self.assertRaisesRegex(UserError, 'Closing date is before open'):
            self.db.add_call(
                BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
                date_close, date_open,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, None, None, False,
                False, '', 500, 4, 1, 366)
        with self.assertRaisesRegex(Error, 'Preamble text .* specified'):
            self.db.add_call(
                BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
                date_open, date_close,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, '', None, False,
                False, '', 500, 4, 1, 366)
        with self.assertRaisesRegex(Error, 'Preamble text .* recognised'):
            self.db.add_call(
                BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
                date_open, date_close,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, '', 999999, False,
                False, '', 500, 4, 1, 366)

        # Check uniqueness constraint.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_call(
                BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
                date_open, date_close,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, None, None, False,
                False, '', 500, 4, 1, 366)

        # Check facility consistency check.
        facility_id_2 = self.db.ensure_facility('my_other_tel')
        semester_id_2 = self.db.add_semester(
            facility_id_2, 'My Semester', 'MS',
            datetime(2000, 2, 1), datetime(2000, 7, 31))
        with self.assertRaisesRegex(ConsistencyError,
                                    'inconsistent facility references'):
            self.db.add_call(
                BaseCallType, semester_id_2, queue_id, BaseCallType.STANDARD,
                date_open, date_close,
                1, 1, 1, 1, 1, 1, 1, 1, 1,
                '', '', '', FormatType.PLAIN, False, False, None, None, False,
                False, '', 500, 4, 1, 366)

        # Try the search_call method.
        result = self.db.search_call(call_id=call_id, with_preamble=True)
        self.assertIsInstance(result, CallCollection)
        self.assertEqual(list(result.keys()), [call_id])
        expected = Call(id=call_id, semester_id=semester_id, queue_id=queue_id,
                        type=BaseCallType.STANDARD,
                        date_open=date_open, date_close=date_close,
                        state=CallState.CLOSED,
                        facility_id=facility_id,
                        semester_name='My Semester', queue_name='My Queue',
                        queue_description=None, queue_description_format=None,
                        abst_word_lim=1,
                        tech_word_lim=2, tech_fig_lim=7, tech_page_lim=3,
                        sci_word_lim=4, sci_fig_lim=5, sci_page_lim=6,
                        capt_word_lim=8, expl_word_lim=9,
                        tech_note='technical note', sci_note='scientific note',
                        prev_prop_note='previous proposal note',
                        note_format=FormatType.PLAIN,
                        proposal_count=None,
                        multi_semester=False, separate=False,
                        preamble='preamble text', preamble_format=FormatType.RST,
                        hidden=False, allow_continuation=False,
                        cnrq_note='con req note',
                        cnrq_word_lim=500, cnrq_fig_lim=4, cnrq_page_lim=1,
                        cnrq_max_age=366)
        self.assertEqual(result[call_id], expected._replace(
            tech_note=None, sci_note=None,
            prev_prop_note=None, cnrq_note=None))
        self.assertEqual(self.db.get_call(facility_id, call_id), expected)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(facility_id, 1999999)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(1999999, call_id)

        self.assertEqual(self.db.search_call(
            call_id=call_id, separate=False,
            with_case_notes=True, with_preamble=True).get_single(), expected)

        with self.assertRaises(NoSuchRecord):
            self.db.search_call(call_id=call_id, separate=True).get_single()

        self.assertEqual(self.db.search_call(
            call_id=call_id, hidden=False,
            with_case_notes=True, with_preamble=True).get_single(), expected)

        with self.assertRaises(NoSuchRecord):
            self.db.search_call(call_id=call_id, hidden=True).get_single()

        # Try updating the call.
        with self.assertRaisesRegex(ConsistencyError, 'call does not exist'):
            self.db.update_call(1999999, date_open=date_open)
        with self.assertRaisesRegex(UserError, 'Closing date is before open'):
            self.db.update_call(call_id,
                                date_close=date_open, date_open=date_close)
        with self.assertRaisesRegex(Error, 'Preamble .* not specified'):
            self.db.update_call(call_id, preamble='new preamble')
        with self.assertRaisesRegex(Error, 'Preamble .* not specified'):
            self.db.update_call(call_id, preamble='new preamble',
                                preamble_format=None)
        with self.assertRaisesRegex(Error, 'Preamble .* not recognised'):
            self.db.update_call(call_id, preamble='new preamble',
                                preamble_format=999999)
        with self.assertRaisesRegex(Error, 'format specified without pre'):
            self.db.update_call(call_id, preamble_format=FormatType.PLAIN)

        self.db.update_call(
            call_id, date_close=datetime(1999, 10, 1), separate=True,
            preamble=None)
        call = self.db.get_call(facility_id, call_id)
        self.assertEqual(call.date_close.month, 10)
        self.assertTrue(call.separate)
        self.assertIsNone(call.preamble)
        self.assertIsNone(call.preamble_format)
        self.assertFalse(call.hidden)

        self.db.update_call(
            call_id, preamble='new preamble', preamble_format=FormatType.PLAIN,
            hidden=True)
        call = self.db.get_call(facility_id, call_id)
        self.assertTrue(call.separate)
        self.assertEqual(call.preamble, 'new preamble')
        self.assertEqual(call.preamble_format, FormatType.PLAIN)
        self.assertTrue(call.hidden)

        self.assertEqual(
            set(self.db.search_call(call_id=call_id, separate=False).keys()),
            set(()))
        self.assertEqual(
            set(self.db.search_call(call_id=call_id, separate=True).keys()),
            set((call_id,)))

        self.assertEqual(
            set(self.db.search_call(call_id=call_id, hidden=False).keys()),
            set(()))
        self.assertEqual(
            set(self.db.search_call(call_id=call_id, hidden=True).keys()),
            set((call_id,)))

        # Test the get_call method's facility_id results.
        queue_id_2 = self.db.add_queue(facility_id_2, 'Another Queue', 'AQ')
        call_id_2 = self.db.add_call(
            BaseCallType, semester_id_2, queue_id_2, BaseCallType.STANDARD,
            date_open, date_close,
            1, 1, 1, 1, 1, 1, 1, 1, 1, '', '', '', FormatType.PLAIN,
            False, False, None, None, False, False, '', 500, 4, 1, 366)

        result = self.db.get_call(facility_id=None, call_id=call_id)
        self.assertIsInstance(result, Call)
        self.assertEqual(result.facility_id, facility_id)

        result = self.db.get_call(facility_id=None, call_id=call_id_2)
        self.assertIsInstance(result, Call)
        self.assertEqual(result.facility_id, facility_id_2)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(facility_id=None, call_id=1999999)

        # Test the call state filtering.
        result = self.db.search_call()
        self.assertEqual(set(result.keys()), set((call_id, call_id_2)))
        for value in result.values():
            self.assertEqual(value.state, CallState.CLOSED)

        result = self.db.search_call(state=CallState.CLOSED)
        self.assertEqual(set(result.keys()), set((call_id, call_id_2)))

        result = self.db.search_call(state=CallState.UNOPENED)
        self.assertEqual(set(result.keys()), set())

        self.db.update_call(call_id, date_close=datetime(2099, 1, 1))
        result = self.db.search_call(state=CallState.CLOSED)
        self.assertEqual(set(result.keys()), set((call_id_2,)))

        result = self.db.search_call(state=CallState.OPEN)
        self.assertEqual(set(result.keys()), set((call_id,)))
        for value in result.values():
            self.assertEqual(value.state, CallState.OPEN)

        self.db.update_call(call_id, date_open=datetime(2099, 1, 1))
        result = self.db.search_call(state=CallState.OPEN)
        self.assertEqual(set(result.keys()), set(()))

        result = self.db.search_call(state=CallState.UNOPENED)
        self.assertEqual(set(result.keys()), set((call_id,)))
        for value in result.values():
            self.assertEqual(value.state, CallState.UNOPENED)

    def test_call_mid_close(self):
        (call_id_1, affiliation_id) = self._create_test_call('s1', 'q1')
        (call_id_2, affiliation_id) = self._create_test_call('s2', 'q2')

        result = self.db.search_call_mid_close(call_id_1)
        self.assertIsInstance(result, CallMidCloseCollection)
        self.assertFalse(result)

        record = null_tuple(CallMidClose)

        (n_insert, n_update, n_delete) = self.db.sync_call_call_mid_close(
            call_id_1, CallMidCloseCollection((
                ('new1', record._replace(date=datetime(2020, 1, 1))),
                ('new2', record._replace(date=datetime(2020, 2, 1))),
            )))

        self.assertEqual(n_insert, 2)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        (n_insert, n_update, n_delete) = self.db.sync_call_call_mid_close(
            call_id_2, CallMidCloseCollection((
                ('new1', record._replace(date=datetime(2021, 1, 1))),
                ('new2', record._replace(date=datetime(2021, 2, 1))),
            )))

        self.assertEqual(n_insert, 2)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        result = self.db.search_call_mid_close(call_id=[
            call_id_1, call_id_2])
        self.assertIsInstance(result, CallMidCloseCollection)
        self.assertEqual(len(result), 4)

        for (item, call_id, date) in zip(
                result.items(),
                [call_id_1, call_id_1, call_id_2, call_id_2],
                [datetime(2020, 1, 1), datetime(2020, 2, 1),
                 datetime(2021, 1, 1), datetime(2021, 2, 1)]):
            (id_, entry) = item

            self.assertIsInstance(id_, int)
            self.assertEqual(entry.id, id_)
            self.assertEqual(entry.call_id, call_id)
            self.assertEqual(entry.date, date)
            self.assertEqual(entry.closed, False)

        self.assertEqual(len(self.db.search_call_mid_close(closed=True)), 0)
        self.assertEqual(len(self.db.search_call_mid_close(closed=False)), 4)

        id_ = list(result.keys())[0]

        with self.assertRaisesRegex(ConsistencyError, 'does not exist'):
            self.db.update_call_mid_close(1999999, closed=True)

        with self.assertRaisesRegex(ConsistencyError, 'no rows matched'):
            self.db.update_call_mid_close(
                1999999, closed=True, _test_skip_check=True)

        self.db.update_call_mid_close(id_, closed=True)

        self.assertEqual(len(self.db.search_call_mid_close(
            closed=False, date_before=datetime(2020, 1, 15))), 0)

        self.assertEqual(len(self.db.search_call_mid_close(closed=True)), 1)
        self.assertEqual(len(self.db.search_call_mid_close(closed=False)), 3)

        self.assertEqual(len(self.db.search_call_mid_close(
            closed=False, date_before=datetime(2021, 1, 15))), 2)

    def test_call_preamble(self):
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)
        semester_id = self.db.add_semester(
            facility_id, 'My Semester', 'MS',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        self.assertIsInstance(semester_id, int)

        with self.assertRaisesRegex(NoSuchRecord, 'no results$'):
            self.db.get_call_preamble(semester_id, BaseCallType.STANDARD)

        with self.assertRaisesRegex(UserError, 'call type is not recognised'):
            self.db.set_call_preamble(
                BaseCallType, semester_id, 999,
                '', FormatType.PLAIN)

        with self.assertRaisesRegex(UserError, 'format not recognised'):
            self.db.set_call_preamble(
                BaseCallType, semester_id, BaseCallType.STANDARD,
                '', 999)

        with self.assertRaisesRegex(ConsistencyError, 'semester does not'):
            self.db.set_call_preamble(
                BaseCallType, 1999999, BaseCallType.STANDARD,
                '', FormatType.PLAIN)

        preamble_id_orig = self.db.set_call_preamble(
            BaseCallType, semester_id, BaseCallType.STANDARD,
            'We invite proposals...', FormatType.PLAIN)
        self.assertIsInstance(preamble_id_orig, int)

        preamble = self.db.get_call_preamble(
            semester_id, BaseCallType.STANDARD)

        self.assertIsInstance(preamble, CallPreamble)
        self.assertEqual(preamble.id, preamble_id_orig)
        self.assertEqual(preamble.description, 'We invite proposals...')
        self.assertEqual(preamble.description_format, FormatType.PLAIN)

        preamble_id = self.db.set_call_preamble(
            BaseCallType, semester_id, BaseCallType.STANDARD,
            'Proposals are invited...', FormatType.RST)
        self.assertEqual(preamble_id, preamble_id_orig)

        preamble = self.db.get_call_preamble(
            semester_id, BaseCallType.STANDARD)

        self.assertIsInstance(preamble, CallPreamble)
        self.assertEqual(preamble.id, preamble_id_orig)
        self.assertEqual(preamble.description, 'Proposals are invited...')
        self.assertEqual(preamble.description_format, FormatType.RST)

    def test_add_proposal(self):
        (call_id_1, affiliation_id_1) = self._create_test_call(
            'semester1', 'queue1')
        self.assertIsInstance(call_id_1, int)
        (call_id_2, affiliation_id_2) = self._create_test_call(
            'semester2', 'queue2')
        self.assertIsInstance(call_id_2, int)

        person_id = self.db.add_person('Person 1')
        self.assertIsInstance(person_id, int)

        # Create proposals and check the numbers are as expected.
        for (call_id, affiliation_id) in ((call_id_1, affiliation_id_1),
                                          (call_id_2, affiliation_id_2)):
            for i in range(1, 11):
                title = 'Proposal {}'.format(i)
                proposal_id = self.db.add_proposal(call_id, person_id,
                                                   affiliation_id, title)
                self.assertIsInstance(proposal_id, int)

                proposal = self.db.get_proposal(None, proposal_id,
                                                with_members=True)
                self.assertIsInstance(proposal, Proposal)

                self.assertEqual(proposal.number, i)

                # Check remaining proposal records.
                self.assertEqual(proposal.id, proposal_id)
                self.assertEqual(proposal.title, title)
                self.assertEqual(proposal.call_id, call_id)
                self.assertEqual(proposal.state, ProposalState.PREPARATION)
                self.assertIsInstance(proposal.members, MemberCollection)
                self.assertEqual(len(proposal.members), 1)
                member = proposal.members.get_single()
                self.assertIsInstance(member, Member)
                self.assertEqual(member.person_id, person_id)
                self.assertEqual(member.proposal_id, proposal_id)
                self.assertTrue(member.pi)
                self.assertTrue(member.editor)
                self.assertFalse(member.observer)

                # Try updating the proposal.
                with self.assertRaisesRegex(ConsistencyError,
                                            '^no rows matched'):
                    self.db.update_proposal(
                        proposal_id, state=ProposalState.SUBMITTED,
                        state_prev=ProposalState.REVIEW)

                proposal_updated = self.db.get_proposal(None, proposal_id)
                self.assertEqual(proposal_updated, proposal._replace(
                    state=ProposalState.PREPARATION,
                    members=None))

                self.db.update_proposal(proposal_id,
                                        state=ProposalState.SUBMITTED,
                                        state_prev=ProposalState.PREPARATION)
                proposal_updated = self.db.get_proposal(None, proposal_id)
                self.assertEqual(proposal_updated, proposal._replace(
                    state=ProposalState.SUBMITTED,
                    members=None))

                # Try searching for proposals.
                result = self.db.search_proposal(call_id=call_id)
                self.assertIsInstance(result, ProposalCollection)
                self.assertEqual(len(result), i)
                self.assertIn(proposal_id, result)
                proposal = result[proposal_id]
                self.assertIsInstance(proposal, Proposal)
                self.assertEqual(proposal.id, proposal_id)
                self.assertEqual(proposal.call_id, call_id)
                self.assertEqual(proposal.number, i)
                self.assertEqual(proposal.state, ProposalState.SUBMITTED)
                self.assertEqual(proposal.title, title)
                self.assertIsNone(proposal.members)

        # The proposal must have a title.
        with self.assertRaisesRegex(UserError, 'blank'):
            self.db.add_proposal(call_id_1, person_id, affiliation_id_1, '')

        # The type and state must be valid.
        with self.assertRaisesRegex(Error, 'Invalid state'):
            self.db.add_proposal(
                call_id_1, person_id, affiliation_id_1, 'Title', state=999)

        with self.assertRaisesRegex(Error, 'Invalid proposal type'):
            self.db.add_proposal(
                call_id_1, person_id, affiliation_id_1, 'Title', type_=999)

        # Check for error raised when the call or person doesn't exist.
        with self.assertRaisesRegex(ConsistencyError, '^call does not'):
            self.db.add_proposal(1999999, person_id, affiliation_id_1, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(1999999, person_id, affiliation_id_1, 'Title',
                                 _test_skip_check=True)

        with self.assertRaisesRegex(ConsistencyError, '^person does not'):
            self.db.add_proposal(call_id_1, 1999999, affiliation_id_1, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(call_id_1, 1999999, affiliation_id_1, 'Title',
                                 _test_skip_check=True)

        # Check for error raised when the affiliation is for the wrong
        # queue.
        other_facility_id = self.db.ensure_facility('another_tel')
        other_queue_id = self.db.add_queue(other_facility_id, 'another queue',
                                           'aq')
        other_affiliation_id = self.db.add_affiliation(
            BaseAffiliationType, other_queue_id, 'another aff/n')
        with self.assertRaisesRegex(ConsistencyError, 'affiliation does not'):
            self.db.add_proposal(call_id_1, person_id, other_affiliation_id,
                                 'title')

        # Check that the "with_proposals" option of "get_user" works.
        result = self.db.get_person(person_id, with_proposals=True)
        self.assertIsInstance(result.proposals, ResultCollection)
        self.assertEqual(len(result.proposals), 20)

    def test_add_member(self):
        # Create test records and check we have integer identifiers for all.
        (call_id, affiliation_id) = self._create_test_call(
            'semester1', 'queue1')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        proposal_id = self.db.add_proposal(call_id, person_id_1,
                                           affiliation_id, 'Proposal 1')

        for id_ in (call_id, person_id_1, person_id_2, person_id_3,
                    proposal_id):
            self.assertIsInstance(id_, int)

        # Check the member list as we add members one at a time.
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result), [person_id_1])
        member_id_1 = first_value(result).id

        member_id_2 = self.db.add_member(
            proposal_id, person_id_2, affiliation_id, False, False, True)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result),
                         [person_id_1, person_id_2])

        member_id_3 = self.db.add_member(
            proposal_id, person_id_3, affiliation_id, False, True, True)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result),
                         [person_id_1, person_id_2, person_id_3])

        self.assertEqual(result.get_pi().person_id, person_id_1)

        # Ensure we can't add a member twice.
        with self.assertRaisesRegex(UserError, 'already a member'):
            self.db.add_member(proposal_id, person_id_2, affiliation_id,
                               False, False, False)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_member(proposal_id, person_id_2, affiliation_id,
                               False, False, False, _test_skip_check=True)

        # Ensure we can't add a member with an affiliation for the wrong
        # facility.
        person_id_4 = self.db.add_person('Person 4')
        other_facility = self.db.ensure_facility('another_tel')
        other_queue = self.db.add_queue(other_facility, 'another queue', 'aq')
        other_affiliation = self.db.add_affiliation(
            BaseAffiliationType, other_queue, 'Aff/n')
        with self.assertRaisesRegex(ConsistencyError, 'affiliation does not'):
            self.db.add_member(proposal_id, person_id_4, other_affiliation)

        # Try searching instead by person_id.
        result = self.db.search_member(person_id=person_id_2)
        member = result.get_single()
        self.assertEqual(member.proposal_id, proposal_id)
        self.assertEqual(member.person_id, person_id_2)

        # Check results of proposal by person_id search.
        result = self.db.search_proposal(person_id=person_id_1)
        self.assertIsInstance(result, ProposalCollection)
        self.assertEqual(list(result.keys()), [proposal_id])
        self.assertEqual(result[proposal_id].member, MemberInfo(
            id=member_id_1, pi=True, editor=True, observer=False,
            person_id=person_id_1))

        result = self.db.search_proposal(person_id=person_id_2)
        self.assertIsInstance(result, ProposalCollection)
        self.assertEqual(list(result.keys()), [proposal_id])
        self.assertEqual(result[proposal_id].member, MemberInfo(
            id=member_id_2, pi=False, editor=False, observer=True,
            person_id=person_id_2))

        result = self.db.search_proposal(person_id=person_id_3)
        self.assertIsInstance(result, ProposalCollection)
        self.assertEqual(list(result.keys()), [proposal_id])
        self.assertEqual(result[proposal_id].member, MemberInfo(
            id=member_id_3, pi=False, editor=True, observer=True,
            person_id=person_id_3))

    def test_search_co_member(self):
        (call_id, aff_id) = self._create_test_call('s1', 'q1')

        # Set of test person records.  The numbers indicate the proposals
        # that each person is a member of.  Each person is the PI (and
        # editor) of on proposal, in order.
        person_1234__ = self.db.add_person('Test Person')
        person_12____ = self.db.add_person('Test Person')
        person__234__ = self.db.add_person('Test Person')
        person____45_ = self.db.add_person('Test Person')
        person_____5_ = self.db.add_person('Test Person')
        person____456 = self.db.add_person('Test Person')

        proposal_1 = self.db.add_proposal(call_id, person_1234__, aff_id, 'X')
        proposal_2 = self.db.add_proposal(call_id, person_12____, aff_id, 'X')
        proposal_3 = self.db.add_proposal(call_id, person__234__, aff_id, 'X')
        proposal_4 = self.db.add_proposal(call_id, person____45_, aff_id, 'X')
        proposal_5 = self.db.add_proposal(call_id, person_____5_, aff_id, 'X')
        proposal_6 = self.db.add_proposal(call_id, person____456, aff_id, 'X')

        # Set up the additional proposal membership records.
        args = (aff_id, False, False, False)
        self.db.add_member(proposal_2, person_1234__, *args)
        self.db.add_member(proposal_3, person_1234__, *args)
        self.db.add_member(proposal_4, person_1234__, *args)
        self.db.add_member(proposal_1, person_12____, *args)
        self.db.add_member(proposal_2, person__234__, *args)
        self.db.add_member(proposal_4, person__234__, *args)
        self.db.add_member(proposal_5, person____45_, *args)
        self.db.add_member(proposal_4, person____456, *args)
        self.db.add_member(proposal_5, person____456, *args)

        # Check co-membership results are as expected.
        self.assertEqual(
            _co_member_person_ed(self.db.search_co_member(person_1234__)), [
                (person_12____, False),
                (person_12____, True),
                (person__234__, False),
                (person__234__, False),
                (person__234__, False),
                (person____45_, False),
                (person____456, False),
            ])

        self.assertEqual(
            _co_member_person_ed(self.db.search_co_member(person_12____)), [
                (person_1234__, False),
                (person_1234__, True),
                (person__234__, True),
            ])

        self.assertEqual(
            _co_member_person_ed(self.db.search_co_member(person__234__)), [
                (person_1234__, False),
                (person_1234__, False),
                (person_1234__, True),
                (person_12____, False),
                (person____45_, False),
                (person____456, False),
            ])

        self.assertEqual(
            _co_member_person_ed(self.db.search_co_member(person____45_)), [
                (person_1234__, True),
                (person__234__, True),
                (person_____5_, False),
                (person____456, False),
                (person____456, True),
            ])

        self.assertEqual(
            _co_member_person_ed(self.db.search_co_member(person_____5_)), [
                (person____45_, True),
                (person____456, True),
            ])

        self.assertEqual(
            _co_member_person_ed(self.db.search_co_member(person____456)), [
                (person_1234__, False),
                (person__234__, False),
                (person____45_, False),
                (person____45_, False),
                (person_____5_, False),
            ])

    def test_sync_proposal_member(self):
        (call_id, affiliation_id) = self._create_test_call('s1', 'q1')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        proposal_id = self.db.add_proposal(
            call_id, person_id_1, affiliation_id, 'Proposal Title')
        self.assertIsInstance(proposal_id, int)

        self.db.add_member(proposal_id, person_id_2, affiliation_id)

        members = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(members), 2)

        (member_id_1, member_id_2) = members.keys()
        self.assertEqual(members[member_id_1].person_id, person_id_1)
        self.assertEqual(members[member_id_2].person_id, person_id_2)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_member(
            proposal_id, members, person_id_1)
        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        with self.assertRaisesRegex(UserError, 'no specified editors'):
            mem_c = members.copy()
            mem_c[member_id_1] = mem_c[member_id_1]._replace(editor=False)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        with self.assertRaisesRegex(UserError, 'no PI specified'):
            mem_c = members.copy()
            mem_c[member_id_1] = mem_c[member_id_1]._replace(pi=False)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        with self.assertRaisesRegex(UserError, 'more than one PI specified'):
            mem_c = members.copy()
            mem_c[member_id_2] = mem_c[member_id_2]._replace(pi=True)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        with self.assertRaisesRegex(UserError, 'yourself as an editor'):
            mem_c = members.copy()
            mem_c[member_id_1] = mem_c[member_id_1]._replace(editor=False)
            mem_c[member_id_2] = mem_c[member_id_2]._replace(editor=True)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        del members[member_id_1]
        members[member_id_2] = members[member_id_2]._replace(
            editor=True, pi=True)

        with self.assertRaisesRegex(UserError, 'can not remove yourself'):
            self.db.sync_proposal_member(proposal_id, members, person_id_1)

        with self.assertRaisesRegex(UserError, 'can not be deleted'):
            self.db.sync_proposal_member(
                proposal_id, members, None, forbid_delete=True)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_member(
            proposal_id, members, None)

        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 1)
        self.assertEqual(n_delete, 1)

        members = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(list(members.keys()), [member_id_2])

    def test_sync_member_institution(self):
        (call_id, affiliation_id) = self._create_test_call(
            'semester1', 'queue1')
        institution_id_1 = self.db.add_institution('Inst 1', '', '', '', 'AX')
        institution_id_2 = self.db.add_institution('Inst 2', '', '', '', 'CX')
        institution_id_3 = self.db.add_institution('Inst 3', '', '', '', 'AX')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        self.db.update_person(person_id_3, institution_id=institution_id_3)
        proposal_id = self.db.add_proposal(call_id, person_id_1,
                                           affiliation_id, 'Proposal 1')

        member_id_2 = self.db.add_member(
            proposal_id, person_id_2, affiliation_id, False, False, False)
        member_id_3 = self.db.add_member(
            proposal_id, person_id_3, affiliation_id, False, False, False)

        # Institutions should be undefined at first except person 3.
        expect_ref = (institution_id_3, None, None)
        expect = list(expect_ref)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, expect.pop())

        # Create set of member institution records to sync.
        records = ResultCollection()
        inst_ref = (institution_id_3, institution_id_2, institution_id_1)
        institutions = list(inst_ref)
        with self.db._engine.begin() as conn:
            for row in conn.execute(
                    member.select().order_by(member.c.id.asc())):
                self.assertIsNone(row.institution_id)

                records[row.id] = MemberInstitution(row.id, institutions.pop())

        self.assertEqual(len(records), 3)
        result = self.db.sync_proposal_member_institution(proposal_id, records)
        self.assertEqual(result, (0, 3, 0))

        # Institutions should now be defined.
        institutions = list(inst_ref)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, institutions.pop())

        # Check also by manual query.
        institutions = list(inst_ref)
        records = ResultCollection()
        with self.db._engine.begin() as conn:
            for row in conn.execute(
                    member.select().order_by(member.c.id.asc())):
                self.assertEqual(row.institution_id, institutions.pop())
                records[row.id] = MemberInstitution(row.id, None)
        self.assertEqual(institutions, [])

        # Sync all the records back to null.
        self.assertEqual(len(records), 3)
        result = self.db.sync_proposal_member_institution(proposal_id, records)
        self.assertEqual(result, (0, 3, 0))
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)
        expect = list(expect_ref)
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, expect.pop())

        # Try basic set_member_institution method.
        with self.assertRaisesRegex(ConsistencyError, 'institution does'):
            self.db.set_member_institution(member_id_2, 1999999)

        with self.assertRaisesRegex(ConsistencyError, 'no rows matched'):
            self.db.set_member_institution(1999999, institution_id_2)

        self.db.set_member_institution(member_id_2, institution_id_2)
        result = self.db.search_member(proposal_id=proposal_id)
        expect = list(expect_ref)
        expect[1] = institution_id_2
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, expect.pop())

    def test_delete_member_person(self):
        (call_id, affiliation_id) = self._create_test_call('s1', 'q1')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        proposal_id = self.db.add_proposal(
            call_id, person_id_1, affiliation_id, 'Proposal Title')
        self.assertIsInstance(proposal_id, int)

        self.db.add_member(proposal_id, person_id_2, affiliation_id)

        with self.assertRaisesRegex(ConsistencyError,
                                    'would leave no editors'):
            self.db.delete_member_person(proposal_id, person_id_1)

        self.db.add_member(proposal_id, person_id_3, affiliation_id,
                           editor=True)

        self.db.delete_member_person(proposal_id, person_id_1)

        self.assertEqual(
            [x.person_id for x in
             self.db.search_member(proposal_id=proposal_id).values()],
            [person_id_2, person_id_3])

    def test_prev_proposal(self):
        proposal_id = self._create_test_proposal()
        old_proposal_id = self._create_test_proposal(
            semester_code='old', queue_code='old')
        old_proposal = self.db.get_proposal(
            facility_id=None, proposal_id=old_proposal_id)

        result = self.db.search_prev_proposal(proposal_id=proposal_id)
        self.assertIsInstance(result, PrevProposalCollection)
        self.assertEqual(len(result), 0)

        records = PrevProposalCollection([
            (1, null_tuple(PrevProposal)._replace(
                this_proposal_id=proposal_id, proposal_code='OLD1',
                continuation=False, publications=[
                    null_tuple(PrevProposalPub)._replace(
                        description='Pub 11', type=PublicationType.PLAIN),
                    null_tuple(PrevProposalPub)._replace(
                        description='Pub 12', type=PublicationType.PLAIN),
                ])),
            (2, null_tuple(PrevProposal)._replace(
                this_proposal_id=proposal_id, proposal_code='OLD2',
                continuation=True, publications=[
                    null_tuple(PrevProposalPub)._replace(
                        description='Pub 21', type=PublicationType.PLAIN),
                    null_tuple(PrevProposalPub)._replace(
                        description='Pub 22', type=PublicationType.PLAIN),
                ])),
            (3, null_tuple(PrevProposal)._replace(
                this_proposal_id=proposal_id, proposal_id=old_proposal_id,
                proposal_code='OLD3', continuation=False, publications=[
                    null_tuple(PrevProposalPub)._replace(
                        description='Pub 31', type=PublicationType.PLAIN),
                    null_tuple(PrevProposalPub)._replace(
                        description='Pub 32', type=PublicationType.PLAIN),
                ])),
        ])

        (n_insert, n_update, n_delete) = self.db.sync_proposal_prev_proposal(
            proposal_id, records)
        self.assertEqual(n_insert, 3)
        self.assertEqual(n_update, 6)
        self.assertEqual(n_delete, 0)

        for with_proposal_info in [False, True]:
            result = self.db.search_prev_proposal(
                proposal_id=proposal_id, with_proposal_info=with_proposal_info)
            self.assertIsInstance(result, PrevProposalCollection)
            self.assertEqual(len(result), 3)

            for (row, expect_continuation, expect_code, expect_pub,
                 proposal) in zip(
                    result.values(),
                    [False, True, False],
                    ['OLD1', 'OLD2', 'OLD3'],
                    [
                        ['Pub 11', 'Pub 12'],
                        ['Pub 21', 'Pub 22'],
                        ['Pub 31', 'Pub 32'],
                    ],
                    [None, None, old_proposal]):
                self.assertIsInstance(row, PrevProposal)
                self.assertEqual(row.this_proposal_id, proposal_id)
                self.assertEqual(row.continuation, expect_continuation)
                self.assertIsInstance(row.publications, list)
                self.assertEqual(len(row.publications), len(expect_pub))
                if proposal is None:
                    self.assertIsNone(row.proposal_id)
                else:
                    self.assertEqual(row.proposal_id, proposal.id)
                if with_proposal_info and proposal is not None:
                    self.assertEqual(row.proposal_state, proposal.state)
                    self.assertEqual(row.proposal_type, proposal.type)
                    self.assertEqual(row.proposal_call_id, proposal.call_id)
                    self.assertEqual(
                        row.proposal_call_type, proposal.call_type)
                    self.assertEqual(
                        row.proposal_semester_id, proposal.semester_id)
                    self.assertEqual(
                        row.proposal_queue_id, proposal.queue_id)
                else:
                    self.assertIsNone(row.proposal_state)
                    self.assertIsNone(row.proposal_type)
                    self.assertIsNone(row.proposal_call_id)
                    self.assertIsNone(row.proposal_call_type)
                    self.assertIsNone(row.proposal_semester_id)
                    self.assertIsNone(row.proposal_queue_id)
                for (pub, expect) in zip(row.publications, expect_pub):
                    self.assertIsInstance(pub, PrevProposalPub)
                    self.assertEqual(pub.type, PublicationType.PLAIN)
                    self.assertEqual(pub.description, expect)

        result = self.db.search_prev_proposal(
            proposal_id=proposal_id, continuation=False,
            with_publications=True)
        self.assertIsInstance(result, PrevProposalCollection)
        self.assertEqual(len(result), 2)
        self.assertEqual(
            [x.proposal_code for x in result.values()],
            ['OLD1', 'OLD3'])
        for row in result.values():
            self.assertIsInstance(row.publications, list)
            self.assertEqual(len(row.publications), 2)

        result = self.db.search_prev_proposal(
            proposal_id=proposal_id, continuation=True,
            with_publications=False)
        self.assertIsInstance(result, PrevProposalCollection)
        self.assertEqual(len(result), 1)
        value = result.get_single()

        self.assertEqual(value.proposal_code, 'OLD2')
        self.assertIs(value.publications, None)

        result = self.db.search_prev_proposal(
            proposal_id=proposal_id, resolved=True, with_publications=False)
        self.assertIsInstance(result, PrevProposalCollection)
        self.assertEqual(
            [x.proposal_code for x in result.values()],
            ['OLD3'])

        result = self.db.search_prev_proposal(
            proposal_id=proposal_id, resolved=False, with_publications=False)
        self.assertIsInstance(result, PrevProposalCollection)
        self.assertEqual(
            [x.proposal_code for x in result.values()],
            ['OLD1', 'OLD2'])

    def test_proposal_annotation(self):
        proposal_id = self._create_test_proposal()

        result = self.db.search_proposal_annotation(proposal_id=proposal_id)
        self.assertIsInstance(result, AnnotationCollection)
        self.assertEqual(len(result), 0)

        annotation_id = self.db.add_proposal_annotation(
            proposal_id, AnnotationType.PROPOSAL_COPY, {'test': 1234})
        self.assertIsInstance(annotation_id, int)

        result = self.db.search_proposal_annotation(proposal_id=proposal_id)
        self.assertEqual(list(result.keys()), [annotation_id])

        value = result.get_single()
        self.assertIsInstance(value, Annotation)
        self.assertEqual(value.id, annotation_id)
        self.assertEqual(value.proposal_id, proposal_id)
        self.assertEqual(value.type, AnnotationType.PROPOSAL_COPY)
        self.assertIsInstance(value.date, datetime)
        self.assertEqual(value.annotation, {'test': 1234})

        result = self.db.search_proposal_annotation(
            proposal_id=proposal_id, type_=999999)
        self.assertEqual(len(result), 0)

        result = self.db.search_proposal_annotation(
            proposal_id=proposal_id, type_=AnnotationType.PROPOSAL_COPY)
        self.assertEqual(len(result), 1)

    def test_proposal_text(self):
        # "Define" extra text roles for the purpose of testing this
        # method before multiple roles are implemented.
        BaseTextRole._info[40] = BaseTextRole.RoleInfo(
            'Role 40', 'r40', None, None)
        BaseTextRole._info[41] = BaseTextRole.RoleInfo(
            'Role 41', 'r41', None, None)

        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        person_id = self.db.add_person('Person 1')
        proposal_id_1 = self.db.add_proposal(call_id, person_id,
                                             affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id_1, int)
        proposal_id_2 = self.db.add_proposal(call_id, person_id,
                                             affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id_2, int)

        # Searching now should return nothing.
        self.assertEqual(len(self.db.search_proposal_text()), 0)

        # Test we can't use an invalid format code or role number.
        with self.assertRaisesRegex(UserError, 'format not recognised'):
            self.db.set_proposal_text(
                BaseTextRole, proposal_id_1, BaseTextRole.ABSTRACT,
                'test', 999, 1, person_id)
        with self.assertRaisesRegex(Error, 'text role not recognised'):
            self.db.set_proposal_text(
                BaseTextRole, proposal_id_1, 999, 'test',
                FormatType.PLAIN, 1, person_id)

        # Test we can't get or delete a non-existant record.
        with self.assertRaisesRegex(NoSuchRecord, 'no results$'):
            self.db.get_proposal_text(
                proposal_id_1, BaseTextRole.ABSTRACT)

        with self.assertRaisesRegex(ConsistencyError, '^text does not exist'):
            self.db.delete_proposal_text(proposal_id_1,
                                         BaseTextRole.ABSTRACT)

        with self.assertRaisesRegex(ConsistencyError, '^mismatch deleting'):
            self.db.delete_proposal_text(proposal_id_1,
                                         BaseTextRole.ABSTRACT,
                                         _skip_check=True)

        # Test that we can't reference a non-existant person as editor.
        with self.assertRaisesRegex(ConsistencyError, '^person does not'):
            self.db.set_proposal_text(
                BaseTextRole, proposal_id_1, BaseTextRole.SCIENCE_CASE, 'test',
                FormatType.PLAIN, 1, 1999999)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.set_proposal_text(
                BaseTextRole, proposal_id_1, BaseTextRole.SCIENCE_CASE, 'test',
                FormatType.PLAIN, 1, 1999999, _test_skip_check=True)

        # Add a PDF file -- this should be deleted when we add the text.
        (link_id, pdf_id) = self.db.set_proposal_pdf(
            BaseTextRole, proposal_id_1, BaseTextRole.SCIENCE_CASE,
            b'dummy PDF file', 2, 'test.pdf', person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(pdf_id, int)
        self.db.set_proposal_pdf_preview(
            pdf_id, [b'dummy PNG 1', b'dummy PNG 2'])
        self.db.get_proposal_pdf(
            proposal_id_1, BaseTextRole.SCIENCE_CASE)
        self.db.get_proposal_pdf_preview(
            proposal_id_1, BaseTextRole.SCIENCE_CASE, 1)
        self.db.get_proposal_pdf_preview(
            proposal_id_1, BaseTextRole.SCIENCE_CASE, 2)

        # Try creating and updating some text.
        (link_id_orig, text_id_orig) = self.db.set_proposal_text(
            BaseTextRole, proposal_id_1, BaseTextRole.SCIENCE_CASE, 'test',
            FormatType.PLAIN, 1, person_id)
        self.assertIsInstance(link_id_orig, int)
        self.assertIsInstance(text_id_orig, int)
        result = self.db.get_proposal_text(
            proposal_id_1, BaseTextRole.SCIENCE_CASE)
        self.assertIsInstance(result, ProposalText)
        self.assertEqual(result.text, 'test')
        self.assertEqual(result.format, FormatType.PLAIN)

        (link_id, text_id) = self.db.set_proposal_text(
            BaseTextRole, proposal_id_1, BaseTextRole.SCIENCE_CASE, 'change',
            FormatType.PLAIN, 1, person_id)
        self.assertEqual(link_id, link_id_orig)
        self.assertNotEqual(text_id, text_id_orig)
        result = self.db.get_proposal_text(
            proposal_id_1, BaseTextRole.SCIENCE_CASE)
        self.assertIsInstance(result, ProposalText)
        self.assertEqual(result.text, 'change')
        self.assertEqual(result.format, FormatType.PLAIN)

        # Check that the PDF was deleted, along with its preview pages.
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf(
                proposal_id_1, BaseTextRole.SCIENCE_CASE)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(
                proposal_id_1, BaseTextRole.SCIENCE_CASE, 1)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(
                proposal_id_1, BaseTextRole.SCIENCE_CASE, 2)

        # Now delete the record.
        self.db.delete_proposal_text(
            proposal_id_1, BaseTextRole.SCIENCE_CASE)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_text(
                proposal_id_1, BaseTextRole.SCIENCE_CASE)

        # "Define" some extra format types just for the purpose of testing
        # this method before multiple formats have been implemented.
        FormatType._info[991] = FormatType.FormatTypeInfo('MD', True)
        FormatType._info[992] = FormatType.FormatTypeInfo('DocBook', True)
        FormatType._info[993] = FormatType.FormatTypeInfo('RST', True)

        # Add and change multiple records.
        self.db.set_proposal_text(
            BaseTextRole, proposal_id_1, 40, 'a',
            FormatType.PLAIN, 1, person_id)
        self.db.set_proposal_text(
            BaseTextRole, proposal_id_1, 41, 'b',
            FormatType.PLAIN, 1, person_id)
        (link_id_orig, text_id_orig) = self.db.set_proposal_text(
            BaseTextRole, proposal_id_2, 40, 'c',
            991, 1, person_id)
        self.db.set_proposal_text(
            BaseTextRole, proposal_id_2, 41, 'd',
            992, 1, person_id)

        (link_id, text_id) = self.db.set_proposal_text(
            BaseTextRole, proposal_id_2, 40, 'cc', 993,
            1, person_id)

        self.db.delete_proposal_text(proposal_id_1, 41)

        self.assertIsInstance(link_id_orig, int)
        self.assertIsInstance(text_id_orig, int)
        self.assertEqual(link_id, link_id_orig)
        self.assertNotEqual(text_id, text_id_orig)

        result = self.db.get_proposal_text(proposal_id_1, 40)
        self.assertIsInstance(result, ProposalText)
        self.assertEqual(result.text, 'a')
        self.assertEqual(result.format, FormatType.PLAIN)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_text(proposal_id_1, 41)

        result = self.db.get_proposal_text(proposal_id_2, 40)
        self.assertEqual(result.text, 'cc')
        self.assertEqual(result.format, 993)

        result = self.db.get_proposal_text(proposal_id_2, 41)
        self.assertEqual(result.text, 'd')
        self.assertEqual(result.format, 992)

        # Try searching for text.
        result = self.db.search_proposal_text(proposal_id=proposal_id_2)
        self.assertIsInstance(result, ProposalTextCollection)
        self.assertEqual(len(result), 2)
        info = result.get_role(40)
        self.assertIsInstance(info, ProposalText)
        self.assertEqual(info.format, 993)
        self.assertEqual(info.words, 1)
        self.assertIsInstance(info.edited, datetime)
        self.assertEqual(info.editor, person_id)
        self.assertEqual(info.editor_name, 'Person 1')
        info = result.get_role(41)
        self.assertIsInstance(info, ProposalText)
        self.assertEqual(info.format, 992)
        with self.assertRaises(NoSuchValue):
            result.get_role(43)

    def test_proposal_pdf(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        pdf = b'dummy PDF file'
        role = BaseTextRole.TECHNICAL_CASE

        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        # Add text and figures -- these should be removed automatically.
        self.db.set_proposal_text(
            BaseTextRole, proposal_id, role, 'test', FormatType.PLAIN,
            1, person_id)
        (link_id, fig_id) = self.db.add_proposal_figure(
            BaseTextRole, proposal_id, role, FigureType.PNG,
            b'dummy figure', 'Caption', 'test.png', person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(fig_id, int)
        self.db.set_proposal_figure_preview(fig_id, b'dummy preview')
        self.db.set_proposal_figure_thumbnail(fig_id, b'dummy thumbnail')

        self.db.get_proposal_text(proposal_id, role)
        self.db.get_proposal_figure(None, None, link_id)
        self.db.get_proposal_figure_preview(None, None, link_id)
        self.db.get_proposal_figure_thumbnail(None, None, link_id)

        # Try adding a PDF to the proposal.
        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

        (link_id, pdf_id) = self.db.set_proposal_pdf(
            BaseTextRole, proposal_id, role, pdf, 4,
            'test.pdf', person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(pdf_id, int)

        self.assertEqual(
            self.db.get_proposal_pdf(proposal_id, role).data,
            pdf)
        self.assertEqual(
            self.db.get_proposal_pdf(
                None, None, pdf_id=pdf_id).data,
            pdf)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(len(result), 1)
        self.assertIn(link_id, result)
        pdf_info = result[link_id]
        self.assertIsInstance(pdf_info, ProposalPDFInfo)
        self.assertEqual(pdf_info.id, link_id)
        self.assertEqual(pdf_info.pdf_id, pdf_id)
        self.assertEqual(pdf_info.proposal_id, proposal_id)
        self.assertEqual(pdf_info.role, role)
        self.assertEqual(pdf_info.md5sum, '46ee5ebd71065c1d4caa83e4c943c70a')
        self.assertEqual(pdf_info.state, AttachmentState.NEW, 4)
        self.assertEqual(pdf_info.filename, 'test.pdf')
        self.assertIsInstance(pdf_info.uploaded, datetime)
        self.assertEqual(pdf_info.uploader, person_id)
        self.assertEqual(pdf_info.uploader_name, None)

        # Check that the text and figures were removed.
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_text(proposal_id, role)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure(None, None, link_id)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(None, None, link_id)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(None, None, link_id)

        # Try changing proposal state.
        self.db.update_proposal_pdf(
            pdf_id=pdf_id, state=AttachmentState.READY, state_is_system=True)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(result[link_id].state, AttachmentState.READY)

        # Check that the "state_prev" constraint works.
        with self.assertRaisesRegex(ConsistencyError, 'no rows matched'):
            self.db.update_proposal_pdf(
                pdf_id=pdf_id, state=AttachmentState.READY,
                state_prev=AttachmentState.ERROR, state_is_system=True)

        self.db.update_proposal_pdf(
            pdf_id=pdf_id, state=AttachmentState.ERROR,
            state_prev=AttachmentState.READY, state_is_system=True)

        # Test setting preview images.
        self.db.set_proposal_pdf_preview(pdf_id, [b'dummy 1', b'dummy 2'])

        self.assertEqual(
            self.db.get_proposal_pdf_preview(proposal_id, role, 1),
            b'dummy 1')

        self.assertEqual(
            self.db.get_proposal_pdf_preview(proposal_id, role, 2),
            b'dummy 2')

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(proposal_id, role, 3)

        # Test deleting the PDF.
        self.db.delete_proposal_pdf(proposal_id, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf(proposal_id, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(proposal_id, role, 1)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

    def test_proposal_fig(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        fig = b'dummy figure'
        role = BaseTextRole.TECHNICAL_CASE
        type_ = FigureType.PNG

        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        result = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

        (link_id, fig_id) = self.db.add_proposal_figure(
            BaseTextRole, proposal_id, role, type_, fig,
            'Figure caption.', 'test.png', person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(fig_id, int)

        result = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(len(result), 1)
        self.assertIn(link_id, result)
        fig_info = result[link_id]
        self.assertIsInstance(fig_info, ProposalFigureInfo)
        self.assertEqual(fig_info.id, link_id)
        self.assertEqual(fig_info.fig_id, fig_id)
        self.assertEqual(fig_info.proposal_id, proposal_id)
        self.assertEqual(fig_info.sort_order, 1)
        self.assertEqual(fig_info.role, role)
        self.assertEqual(fig_info.md5sum, 'b41faa148ef23d1ddfa46debb3b66f35')
        self.assertEqual(fig_info.type, type_)
        self.assertEqual(fig_info.state, AttachmentState.NEW)
        self.assertEqual(fig_info.caption, None)
        self.assertEqual(fig_info.filename, 'test.png')
        self.assertIsInstance(fig_info.uploaded, datetime)
        self.assertEqual(fig_info.uploader, person_id)
        self.assertEqual(fig_info.uploader_name, None)
        self.assertEqual(fig_info.has_preview, None)

        result = self.db.search_proposal_figure(
            fig_id=fig_id, with_has_preview=True).get_single()
        self.assertEqual(result.has_preview, False)

        with self.assertRaises(NoSuchRecord):
            self.db.search_proposal_figure(fig_id=1999999).get_single()

        self.assertEqual(
            self.db.search_proposal_figure(link_id=link_id).get_single().id,
            link_id)

        with self.assertRaises(NoSuchRecord):
            self.db.search_proposal_figure(link_id=1999999).get_single()

        self.assertEqual(
            self.db.get_proposal_figure(proposal_id, role, link_id).data,
            fig)

        # Try previews and thumbnails.
        preview = b'dummy preview'
        thumbnail = b'dummy thumbnail'

        self.db.set_proposal_figure_preview(fig_id, preview)
        self.db.set_proposal_figure_thumbnail(fig_id, thumbnail)

        self.assertEqual(
            self.db.get_proposal_figure_preview(proposal_id, role, link_id),
            preview)

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(proposal_id, role, link_id),
            thumbnail)

        preview = b'dummy preview updated'
        thumbnail = b'dummy thumbnail updated'

        self.db.set_proposal_figure_preview(fig_id, preview)
        self.db.set_proposal_figure_thumbnail(fig_id, thumbnail)

        self.assertEqual(
            self.db.get_proposal_figure_preview(proposal_id, role, link_id),
            preview)

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(proposal_id, role, link_id),
            thumbnail)

        # Try updating the figure...
        # ... change figure state.
        result = self.db.update_proposal_figure(
            None, None, None, fig_id, state=AttachmentState.ERROR,
            state_prev=AttachmentState.NEW, state_is_system=True)
        self.assertIsNone(result)

        result = self.db.search_proposal_figure(proposal_id=proposal_id,
                                                with_has_preview=True)
        fig_info = result[link_id]
        self.assertEqual(fig_info.state, AttachmentState.ERROR)
        self.assertEqual(fig_info.has_preview, True)
        self.assertEqual(fig_info.fig_id, fig_id)

        # (Should still be able to retrieve preview/thumbnails via link or ID)
        self.assertEqual(
            self.db.get_proposal_figure_preview(proposal_id, role, link_id),
            preview)

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(proposal_id, role, link_id),
            thumbnail)

        self.assertEqual(
            self.db.get_proposal_figure_preview(
                proposal_id, role, None, fig_id=fig_id),
            preview)

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(
                proposal_id, role, None, fig_id=fig_id),
            thumbnail)

        # ... change figure image.
        fig = b'dummy figure updated'
        new_fig_id = self.db.update_proposal_figure(
            proposal_id, role, link_id,
            figure=fig, type_=type_, filename='test2.png',
            uploader_person_id=person_id)
        self.assertIsInstance(new_fig_id, int)
        self.assertNotEqual(new_fig_id, fig_id)

        result = self.db.search_proposal_figure(proposal_id=proposal_id,
                                                with_caption=True)
        fig_info = result[link_id]
        self.assertEqual(fig_info.md5sum, 'b9e7dfbc36883c26e5d2aff8c80f34db')
        self.assertEqual(fig_info.state, AttachmentState.NEW)
        self.assertEqual(fig_info.filename, 'test2.png')
        self.assertEqual(fig_info.caption, 'Figure caption.')
        self.assertEqual(fig_info.fig_id, new_fig_id)

        # (Should be able to retrieve the figure by link or ID but not old ID)
        self.assertEqual(
            self.db.get_proposal_figure(proposal_id, role, link_id).data,
            fig)

        self.assertEqual(
            self.db.get_proposal_figure(
                proposal_id, role, None, fig_id=new_fig_id).data,
            fig)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure(proposal_id, role, None, fig_id=fig_id)

        # ... changing the image should have removed the preview/thumbnail.
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(
                proposal_id, role, None, new_fig_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(
                proposal_id, role, None, new_fig_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(
                proposal_id, role, None, fig_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(
                proposal_id, role, None, fig_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(proposal_id, role, link_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(proposal_id, role, link_id)

        fig_id = new_fig_id

        # ... change the figure caption.
        result = self.db.update_proposal_figure(
            proposal_id, role, link_id, caption='!')
        self.assertIsNone(result)

        result = self.db.search_proposal_figure(proposal_id=proposal_id,
                                                with_caption=True)
        fig_info = result[link_id]
        self.assertEqual(fig_info.caption, '!')
        self.assertEqual(fig_info.fig_id, fig_id)

        # Try deleting the figure.
        self.db.delete_proposal_figure(proposal_id, role, fig_id)

        result = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

    def test_proposal_pdf_link(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        pdf = b'dummy PDF file'
        preview = b'dummy PNG preview'
        role = BaseTextRole.TECHNICAL_CASE

        person_id = self.db.add_person('Test Person')
        proposal_id_1 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 1')
        proposal_id_2 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 2')
        proposal_id_3 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 3')

        (link_id, pdf_id) = self.db.set_proposal_pdf(
            BaseTextRole, proposal_id_1, role, pdf, 1, 'test.pdf', person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(pdf_id, int)

        self.db.set_proposal_pdf_preview(pdf_id, [preview])

        result = self.db.search_proposal_pdf(proposal_id=proposal_id_1)
        self.assertEqual(list(result.keys()), [link_id])
        pdf_info = result[link_id]
        self.assertEqual(pdf_info.id, link_id)
        self.assertEqual(pdf_info.pdf_id, pdf_id)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id_2)
        self.assertEqual(list(result.keys()), [])

        result = self.db.get_proposal_pdf(proposal_id_1, role)
        self.assertEqual(result.data, pdf)

        result = self.db.get_proposal_pdf_preview(proposal_id_1, role, 1)
        self.assertEqual(result, preview)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf(proposal_id_2, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(proposal_id_2, role, 1)

        # Check we can't link to a non-existent PDF.
        with self.assertRaisesRegex(
                ConsistencyError, 'does not exist'):
            self.db.link_proposal_pdf(
                BaseTextRole, proposal_id_2, role, 1999999)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.link_proposal_pdf(
                BaseTextRole, proposal_id_2, role, 1999999,
                _test_skip_check=True)

        # Check we can't link a PDF when we already have one.
        with self.assertRaisesRegex(
                ConsistencyError, 'already has a proposal_pdf link'):
            self.db.link_proposal_pdf(
                BaseTextRole, proposal_id_1, role, pdf_id)

        # Create a link.
        link_id2 = self.db.link_proposal_pdf(
            BaseTextRole, proposal_id_2, role, pdf_id)
        self.assertIsInstance(link_id, int)
        self.assertNotEqual(link_id2, link_id)

        result = self.db.get_proposal_pdf(proposal_id_2, role)
        self.assertEqual(result.data, pdf)
        self.assertEqual(result.type, FigureType.PDF)
        self.assertEqual(result.filename, 'test.pdf')

        result = self.db.get_proposal_pdf_preview(proposal_id_2, role, 1)
        self.assertEqual(result, preview)

        result = self.db.search_proposal_pdf(
            proposal_id=proposal_id_2)
        self.assertEqual(list(result.keys()), [link_id2])
        pdf_info = result[link_id2]
        self.assertIsInstance(pdf_info, ProposalPDFInfo)
        self.assertEqual(pdf_info.id, link_id2)
        self.assertEqual(pdf_info.pdf_id, pdf_id)

        # Delete the link.
        self.db.delete_proposal_pdf(proposal_id_2, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf(proposal_id_2, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(proposal_id_2, role, 1)

        result = self.db.search_proposal_pdf(
            proposal_id=proposal_id_2)
        self.assertEqual(list(result.keys()), [])

        # Create a link to a third proposal.
        link_id_3 = self.db.link_proposal_pdf(
            BaseTextRole, proposal_id_3, role, pdf_id)
        self.assertIsInstance(link_id, int)
        self.assertNotEqual(link_id_3, link_id)

        result = self.db.get_proposal_pdf(proposal_id_3, role)
        self.assertEqual(result.data, pdf)

        result = self.db.get_proposal_pdf_preview(proposal_id_3, role, 1)
        self.assertEqual(result, preview)

        # Update the PDF in the third proposal.
        (new_link_id, pdf_id_3) = self.db.set_proposal_pdf(
            BaseTextRole, proposal_id_3, role,
            b'edited PDF', 1, 'edited.pdf', person_id)
        self.assertEqual(new_link_id, link_id_3)
        self.assertIsInstance(pdf_id_3, int)
        self.assertNotEqual(pdf_id_3, pdf_id)

        self.db.set_proposal_pdf_preview(pdf_id, [preview])

        result = self.db.get_proposal_pdf(proposal_id_3, role)
        self.assertEqual(result.data, b'edited PDF')

        with self.assertRaises(NoSuchRecord):
            result = self.db.get_proposal_pdf_preview(proposal_id_3, role, 1)

        self.db.set_proposal_pdf_preview(pdf_id_3, [b'edited PNG'])

        result = self.db.get_proposal_pdf_preview(proposal_id_3, role, 1)
        self.assertEqual(result, b'edited PNG')

        # The original proposal should still link to the original PDF.
        result = self.db.search_proposal_pdf(proposal_id=proposal_id_1)
        self.assertEqual(list(result.keys()), [link_id])
        result = result.get_single()
        self.assertEqual(result.id, link_id)
        self.assertEqual(result.pdf_id, pdf_id)

        result = self.db.get_proposal_pdf(proposal_id_1, role)
        self.assertEqual(result.data, pdf)

        result = self.db.get_proposal_pdf_preview(proposal_id_1, role, 1)
        self.assertEqual(result, preview)

    def test_proposal_text_link(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        role = BaseTextRole.TECHNICAL_CASE
        text = 'dummy text'
        format = FormatType.PLAIN

        person_id = self.db.add_person('Test Person')
        proposal_id_1 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 1')
        proposal_id_2 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 2')
        proposal_id_3 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 3')

        (link_id, text_id) = self.db.set_proposal_text(
            BaseTextRole, proposal_id_1, role, text, format, 2, person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(text_id, int)

        result = self.db.search_proposal_text(proposal_id=proposal_id_1)
        self.assertEqual(list(result.keys()), [link_id])
        text_info = result[link_id]
        self.assertEqual(text_info.id, link_id)
        self.assertEqual(text_info.text_id, text_id)

        result = self.db.search_proposal_text(proposal_id=proposal_id_2)
        self.assertEqual(list(result.keys()), [])

        # Check we can't link to a non-existent text attachment.
        with self.assertRaisesRegex(
                ConsistencyError, 'does not exist'):
            self.db.link_proposal_text(
                BaseTextRole, proposal_id_2, role, 1999999)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.link_proposal_text(
                BaseTextRole, proposal_id_2, role, 1999999,
                _test_skip_check=True)

        # Check we can't link to a text attachment if we already have one.
        with self.assertRaisesRegex(
                ConsistencyError, 'already has a proposal_text link'):
            self.db.link_proposal_text(
                BaseTextRole, proposal_id_1, role, text_id)

        # Create a link.
        link_id_2 = self.db.link_proposal_text(
            BaseTextRole, proposal_id_2, role, text_id)
        self.assertIsInstance(link_id_2, int)
        self.assertNotEqual(link_id_2, link_id)

        result = self.db.search_proposal_text(
            proposal_id_2, role, with_text=True)
        self.assertIsInstance(result, ProposalTextCollection)
        self.assertEqual(list(result.keys()), [link_id_2])
        result = result.get_single()
        self.assertIsInstance(result, ProposalText)
        self.assertEqual(result.id, link_id_2)
        self.assertEqual(result.text_id, text_id)
        self.assertEqual(result.text, text)
        self.assertEqual(result.format, format)

        # Delete the link.
        self.db.delete_proposal_text(proposal_id_2, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_text(proposal_id_2, role)

        # Create a link to a third proposal.
        link_id_3 = self.db.link_proposal_text(
            BaseTextRole, proposal_id_3, role, text_id)
        self.assertIsInstance(link_id_3, int)
        self.assertNotEqual(link_id_3, link_id)

        result = self.db.search_proposal_text(
            proposal_id_3, role, with_text=True)
        self.assertIsInstance(result, ProposalTextCollection)
        self.assertEqual(list(result.keys()), [link_id_3])
        result = result.get_single()
        self.assertIsInstance(result, ProposalText)
        self.assertEqual(result.id, link_id_3)
        self.assertEqual(result.text_id, text_id)
        self.assertEqual(result.text, text)
        self.assertEqual(result.format, format)

        # Edit the text in the third proposal.
        (new_link_id, text_id_3) = self.db.set_proposal_text(
            BaseTextRole, proposal_id_3, role, 'edited', format, 1, person_id)
        self.assertEqual(new_link_id, link_id_3)
        self.assertIsInstance(text_id_3, int)
        self.assertNotEqual(text_id_3, text_id)

        result = self.db.search_proposal_text(
            proposal_id_3, role, with_text=True)
        self.assertIsInstance(result, ProposalTextCollection)
        self.assertEqual(list(result.keys()), [new_link_id])
        result = result.get_single()
        self.assertIsInstance(result, ProposalText)
        self.assertEqual(result.id, new_link_id)
        self.assertEqual(result.text_id, text_id_3)
        self.assertEqual(result.text, 'edited')
        self.assertEqual(result.format, format)
        self.assertEqual(result.words, 1)

        # The original proposal should still have the original text.
        result = self.db.search_proposal_text(
            proposal_id=proposal_id_1, with_text=True)
        self.assertEqual(list(result.keys()), [link_id])
        result = result.get_single()
        self.assertEqual(result.id, link_id)
        self.assertEqual(result.text_id, text_id)
        self.assertEqual(result.text, text)
        self.assertEqual(result.format, format)
        self.assertEqual(result.words, 2)

    def test_proposal_figure_link(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        role = BaseTextRole.SCIENCE_CASE

        person_id = self.db.add_person('Test Person')
        proposal_id_1 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 1')
        proposal_id_2 = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Proposal 2')

        # Add a figure to proposal 1.
        (link_id_1, fig_id_1) = self.db.add_proposal_figure(
            BaseTextRole, proposal_id_1, role,
            FigureType.PNG, b'PNG1', 'Figure 1 in Proposal 1',
            'fig1.png', person_id)
        self.assertIsInstance(link_id_1, int)
        self.assertIsInstance(fig_id_1, int)

        result = self.db.get_proposal_figure(proposal_id_1, role, link_id_1)
        self.assertEqual(result.data, b'PNG1')
        self.assertEqual(result.type, FigureType.PNG)
        self.assertEqual(result.filename, 'fig1.png')

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(
                proposal_id_1, role, link_id_1)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(
                proposal_id_1, role, link_id_1)

        self.db.set_proposal_figure_preview(fig_id_1, b'PREV1')
        self.db.set_proposal_figure_thumbnail(fig_id_1, b'THUMB1')

        self.assertEqual(
            self.db.get_proposal_figure_preview(
                proposal_id_1, role, link_id_1),
            b'PREV1')

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(
                proposal_id_1, role, link_id_1),
            b'THUMB1')

        # Link the figure to proposal 2.
        link_id_2 = self.db.link_proposal_figure(
            BaseTextRole, proposal_id_2, role, fig_id_1,
            55, 'Figure 1 in Proposal 2')

        self.assertIsInstance(link_id_2, int)
        self.assertNotEqual(link_id_2, link_id_1)

        result = self.db.get_proposal_figure(proposal_id_2, role, link_id_2)
        self.assertEqual(result.data, b'PNG1')
        self.assertEqual(result.type, FigureType.PNG)
        self.assertEqual(result.filename, 'fig1.png')

        self.assertEqual(
            self.db.get_proposal_figure_preview(
                proposal_id_2, role, link_id_2),
            b'PREV1')

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(
                proposal_id_2, role, link_id_2),
            b'THUMB1')

        # Check result of a figure search.
        result = self.db.search_proposal_figure(with_caption=True)
        self.assertEqual(
            sorted(result.keys()),
            sorted([link_id_1, link_id_2]))

        fig = result[link_id_1]
        self.assertEqual(fig.id, link_id_1)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.filename, 'fig1.png')
        self.assertEqual(fig.state, AttachmentState.NEW)
        self.assertEqual(fig.sort_order, 1)
        self.assertEqual(fig.caption, 'Figure 1 in Proposal 1')

        fig = result[link_id_2]
        self.assertEqual(fig.id, link_id_2)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.filename, 'fig1.png')
        self.assertEqual(fig.state, AttachmentState.NEW)
        self.assertEqual(fig.sort_order, 55)
        self.assertEqual(fig.caption, 'Figure 1 in Proposal 2')

        # Try updating the figure.
        with self.assertRaisesRegex(Error, 'main-table constraints'):
            # Can't apply constraints from edited main table
            # after explicit update.
            self.db.update_proposal_figure(
                None, None, link_id_1, fig_id=fig_id_1,
                state=AttachmentState.ERROR, state_prev=AttachmentState.NEW,
                caption='Modified caption', state_is_system=True)

        with self.assertRaisesRegex(Error, 'main-table constraints'):
            # Can't apply constraints from edited main table
            # after implicit link update.
            self.db.update_proposal_figure(
                None, None, link_id_1, state_prev=AttachmentState.NEW,
                figure=b'PNG1E', type_=FigureType.PNG, filename='fig1e.png',
                uploader_person_id=person_id)

        with self.assertRaisesRegex(Error, 'link_id not specified'):
            # Can't update a figure without saying which link to update.
            self.db.update_proposal_figure(
                None, None, None, fig_id=fig_id_1,
                figure=b'PNG1E', type_=FigureType.PNG, filename='fig1e.png',
                uploader_person_id=person_id)

        with self.assertRaisesRegex(Error, 'No link_id specified'):
            # Can't update a caption without saying which link to update.
            self.db.update_proposal_figure(
                None, None, None, fig_id=fig_id_1,
                caption='Modified caption')

        result = self.db.update_proposal_figure(
            None, None, link_id_1, caption='Modified caption in Proposal 1')
        self.assertEqual(result, None)

        result = self.db.update_proposal_figure(
            None, None, link_id_2, caption='Modified caption in Proposal 2')
        self.assertEqual(result, None)

        result = self.db.search_proposal_figure(with_caption=True)

        fig = result[link_id_1]
        self.assertEqual(fig.id, link_id_1)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.sort_order, 1)
        self.assertEqual(fig.caption, 'Modified caption in Proposal 1')

        fig = result[link_id_2]
        self.assertEqual(fig.id, link_id_2)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.sort_order, 55)
        self.assertEqual(fig.caption, 'Modified caption in Proposal 2')

        result_1 = result.subset_by_proposal(proposal_id_1)
        result_1[link_id_1] = result_1[link_id_1]._replace(sort_order=2)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_figure(
            proposal_id_1, role, result_1)

        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 1)
        self.assertEqual(n_delete, 0)

        result_2 = result.subset_by_proposal(proposal_id_2)
        result_2[link_id_2] = result_2[link_id_2]._replace(sort_order=5555)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_figure(
            proposal_id_2, role, result_2)

        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 1)
        self.assertEqual(n_delete, 0)

        result = self.db.search_proposal_figure(with_caption=True)

        fig = result[link_id_1]
        self.assertEqual(fig.id, link_id_1)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.sort_order, 2)
        self.assertEqual(fig.caption, 'Modified caption in Proposal 1')

        fig = result[link_id_2]
        self.assertEqual(fig.id, link_id_2)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.sort_order, 5555)
        self.assertEqual(fig.caption, 'Modified caption in Proposal 2')

        result = self.db.update_proposal_figure(
            None, None, None, fig_id=fig_id_1,
            state=AttachmentState.ERROR, state_prev=AttachmentState.NEW,
            state_is_system=True)
        self.assertEqual(result, None)

        result = self.db.search_proposal_figure(with_caption=True)

        fig = result[link_id_1]
        self.assertEqual(fig.id, link_id_1)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.state, AttachmentState.ERROR)

        fig = result[link_id_2]
        self.assertEqual(fig.id, link_id_2)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.state, AttachmentState.ERROR)

        fig_id_2 = self.db.update_proposal_figure(
            None, None, link_id_2,
            figure=b'PNG1E', type_=FigureType.PNG, filename='fig1e.png',
            uploader_person_id=person_id)
        self.assertIsInstance(fig_id_2, int)
        self.assertNotEqual(fig_id_2, fig_id_1)

        result = self.db.search_proposal_figure(with_caption=True)

        self.assertEqual(
            sorted(result.keys()),
            sorted([link_id_1, link_id_2]))

        fig = result[link_id_1]
        self.assertEqual(fig.id, link_id_1)
        self.assertEqual(fig.fig_id, fig_id_1)
        self.assertEqual(fig.state, AttachmentState.ERROR)
        self.assertEqual(fig.filename, 'fig1.png')
        self.assertEqual(fig.sort_order, 2)
        self.assertEqual(fig.caption, 'Modified caption in Proposal 1')

        fig = result[link_id_2]
        self.assertEqual(fig.id, link_id_2)
        self.assertEqual(fig.fig_id, fig_id_2)
        self.assertEqual(fig.state, AttachmentState.NEW)
        self.assertEqual(fig.filename, 'fig1e.png')
        self.assertEqual(fig.sort_order, 5555)
        self.assertEqual(fig.caption, 'Modified caption in Proposal 2')

        result = self.db.get_proposal_figure(proposal_id_1, role, link_id_1)
        self.assertEqual(result.data, b'PNG1')
        self.assertEqual(result.type, FigureType.PNG)
        self.assertEqual(result.filename, 'fig1.png')

        self.assertEqual(
            self.db.get_proposal_figure_preview(
                proposal_id_1, role, link_id_1),
            b'PREV1')

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(
                proposal_id_1, role, link_id_1),
            b'THUMB1')

        result = self.db.get_proposal_figure(proposal_id_2, role, link_id_2)
        self.assertEqual(result.data, b'PNG1E')
        self.assertEqual(result.type, FigureType.PNG)
        self.assertEqual(result.filename, 'fig1e.png')

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(
                proposal_id_2, role, link_id_2)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(
                proposal_id_2, role, link_id_2)

        result = self.db.search_proposal_figure(no_link=True)
        self.assertEqual(
            set(result.keys()),
            set((fig_id_1, fig_id_2)))

        # Remove first figure by sync.
        (n_insert, n_update, n_delete) = self.db.sync_proposal_figure(
            proposal_id_1, role, ProposalFigureCollection())

        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 1)

        result = self.db.search_proposal_figure(no_link=True)
        self.assertEqual(
            set(result.keys()),
            set((fig_id_2,)))

        with self.assertRaises(NoSuchRecord):
            result = self.db.get_proposal_figure(
                proposal_id_1, role, link_id_1)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(
                proposal_id_1, role, link_id_1)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(
                proposal_id_1, role, link_id_1)

        result = self.db.get_proposal_figure(proposal_id_2, role, link_id_2)
        self.assertEqual(result.data, b'PNG1E')
        self.assertEqual(result.type, FigureType.PNG)
        self.assertEqual(result.filename, 'fig1e.png')

        # Remove second figure via delete method.
        self.db.delete_proposal_figure(proposal_id_2, role, fig_id_2)

        result = self.db.search_proposal_figure(no_link=True)
        self.assertEqual(len(result), 0)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure(proposal_id_2, role, link_id_2)

    def test_proposal_target(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        result = self.db.search_target(proposal_id=proposal_id)
        self.assertIsInstance(result, TargetCollection)
        self.assertFalse(result)

        records = TargetCollection([
            (1, Target(1, proposal_id, 1, 'Obj 1', 1, 0.5, -0.5, 15.5, 1, "Note 1")),
            (2, Target(2, proposal_id, 2, 'Obj 2', None, None, None, 13.5, 2, "Note 2")),
            (3, Target(3, proposal_id, 3, 'Obj 3', 2, 335, 1.5, None, None, "Note 3")),
        ])

        n = self.db.sync_proposal_target(proposal_id, records)
        self.assertEqual(n, (3, 0, 0))

        result = self.db.search_target(proposal_id=proposal_id)
        self.assertIsInstance(result, TargetCollection)
        self.assertEqual(len(result), 3)

        i = 1
        for t in result.values():
            self.assertIsInstance(t, Target)
            self.assertEqual(t.proposal_id, proposal_id)
            self.assertEqual(t.sort_order, i)
            self.assertEqual(t.name, 'Obj {}'.format(i))
            self.assertEqual(t.note, 'Note {}'.format(i))
            i += 1

    def test_request_prop_copy(self):
        (call_id, affiliation_id) = self._create_test_call()
        person_id = self.db.add_person('Requester')
        proposal_id = self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Test Title')

        (copy_call_id, copy_affiliation_id) = self._create_test_call(
            semester_name='copy', queue_name='copy')

        request_id = self.db.add_request_prop_copy(
            proposal_id, person_id, call_id=copy_call_id,
            affiliation_id=copy_affiliation_id,
            copy_members=True, continuation=False)

        self.assertIsInstance(request_id, int)

        with self.assertRaises(NoSuchRecord):
            request = self.db.search_request_prop_copy(
                request_id=request_id, continuation=True).get_single()

        request = self.db.search_request_prop_copy(
            request_id=request_id).get_single()

        self.assertIsInstance(request, RequestPropCopy)

        self.assertEqual(request.id, request_id)
        self.assertEqual(request.proposal_id, proposal_id)
        self.assertEqual(request.state, RequestState.NEW)
        self.assertEqual(request.requester, person_id)
        self.assertEqual(request.call_id, copy_call_id)
        self.assertEqual(request.affiliation_id, copy_affiliation_id)
        self.assertTrue(request.copy_members)
        self.assertFalse(request.continuation)
        self.assertIsNone(request.copy_proposal_id)
        self.assertIsNone(request.requester_name)

        copy_proposal_id = self.db.add_proposal(
            copy_call_id, person_id, copy_affiliation_id, 'Copy Title')

        self.db.update_request_prop_copy(
            request_id, state=RequestState.READY,
            copy_proposal_id=copy_proposal_id,
            state_is_system=True)

        request = self.db.search_request_prop_copy(
            request_id=request_id, with_requester_name=True).get_single()

        self.assertIsInstance(request, RequestPropCopy)

        self.assertEqual(request.id, request_id)
        self.assertEqual(request.state, RequestState.READY)
        self.assertEqual(request.copy_proposal_id, copy_proposal_id)
        self.assertEqual(request.requester_name, 'Requester')

        # Create a continuation request to test the search method.
        request_id = self.db.add_request_prop_copy(
            proposal_id, person_id, call_id=copy_call_id,
            affiliation_id=copy_affiliation_id,
            copy_members=False, continuation=True)

        self.assertIsInstance(request_id, int)
        self.assertFalse(request.continuation)

        with self.assertRaises(NoSuchRecord):
            request = self.db.search_request_prop_copy(
                request_id=request_id, continuation=False).get_single()

        request = self.db.search_request_prop_copy(
            request_id=request_id, continuation=True).get_single()

        self.assertEqual(request.id, request_id)

    def test_request_prop_pdf(self):
        proposal_id = self._create_test_proposal()
        person_id = self.db.add_person('Requester')

        request_id = self.db.add_request_prop_pdf(proposal_id, person_id)

        request = self.db.search_request_prop_pdf().get_single()
        self.assertEqual(request.id, request_id)
        self.assertEqual(request.proposal_id, proposal_id)
        self.assertEqual(request.state, RequestState.NEW)
        self.assertEqual(request.requester, person_id)

        self.db.update_request_prop_pdf(
            request_id=request_id, state=RequestState.ERROR,
            state_is_system=True)

        request = self.db.search_request_prop_pdf(
            proposal_id=proposal_id).get_single()
        self.assertEqual(request.id, request_id)
        self.assertEqual(request.proposal_id, proposal_id)
        self.assertEqual(request.state, RequestState.ERROR)
        self.assertEqual(request.requester, person_id)

        with self.assertRaises(NoSuchRecord):
            self.db.search_request_prop_pdf(
                state=RequestState.READY).get_single()

        with self.assertRaises(NoSuchRecord):
            self.db.search_request_prop_pdf(
                state=[RequestState.READY]).get_single()

        with self.assertRaises(NoSuchRecord):
            self.db.search_request_prop_pdf(
                proposal_id=[1999999]).get_single()

        with self.assertRaisesRegex(Error, 'invalid request state'):
            self.db.update_request_prop_pdf(
                request_id=request_id, state=999)

        with self.assertRaisesRegex(ConsistencyError, '^request does not'):
            self.db.update_request_prop_pdf(
                request_id=1999999, state=RequestState.READY)

        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.update_request_prop_pdf(
                request_id=1999999, state=RequestState.READY,
                _test_skip_check=True)

        self.db.delete_request_prop_pdf(request_id=request_id)

        self.assertEqual(len(self.db.search_request_prop_pdf()), 0)

        with self.assertRaisesRegex(ConsistencyError, '^request does not'):
            self.db.delete_request_prop_pdf(request_id=request_id)

        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.delete_request_prop_pdf(
                request_id=request_id, _test_skip_check=True)

    def test_category(self):
        facility_id = self.db.ensure_facility('cat test facility')
        records = ResultCollection()
        records[1] = Category(1, None, 'Category A', 'A', False)
        records[2] = Category(2, None, 'Category B', 'B', True)

        (n_insert, n_update, n_delete) = self.db.sync_facility_category(
            facility_id, records)

        self.assertEqual(n_insert, 2)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        result = self.db.search_category(facility_id=facility_id, hidden=False)
        self.assertIsInstance(result, ResultCollection)

        self.assertEqual([x.name for x in result.values()], ['Category A'])
        self.assertEqual([x.name_abbr for x in result.values()], ['A'])
        category_id_a = list(result.keys())[0]
        self.assertIsInstance(category_id_a, int)

        result = self.db.search_category(facility_id=facility_id, hidden=True)
        self.assertIsInstance(result, ResultCollection)

        self.assertEqual([x.name for x in result.values()], ['Category B'])
        self.assertEqual([x.name_abbr for x in result.values()], ['B'])
        category_id_b = list(result.keys())[0]
        self.assertIsInstance(category_id_b, int)
        self.assertNotEqual(category_id_a, category_id_b)

        (call_id, affiliation_id) = self._create_test_call(
            's 1', 'q 1', facility_id=facility_id)

        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        proposal_categories = ResultCollection()
        proposal_categories[1] = ProposalCategory(1, proposal_id,
                                                  category_id_a, None, None)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_category(
            proposal_id, proposal_categories)

        self.assertEqual(n_insert, 1)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        result = self.db.search_proposal_category(proposal_id=proposal_id)
        self.assertIsInstance(result, ProposalCategoryCollection)
        self.assertEqual(len(result), 1)
        proposal_cat = list(result.values())[0]
        self.assertIsInstance(proposal_cat, ProposalCategory)
        self.assertEqual(proposal_cat.category_name, 'Category A')
        self.assertEqual(proposal_cat.category_name_abbr, 'A')

        proposal_categories = ResultCollection()
        proposal_categories[2] = ProposalCategory(2, proposal_id,
                                                  category_id_b, None, None)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_category(
            proposal_id, proposal_categories)

        self.assertEqual(n_insert, 1)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 1)

        result = self.db.search_proposal_category(proposal_id=proposal_id)
        self.assertIsInstance(result, ProposalCategoryCollection)
        self.assertEqual(len(result), 1)
        proposal_cat = list(result.values())[0]
        self.assertIsInstance(proposal_cat, ProposalCategory)
        self.assertEqual(proposal_cat.category_name, 'Category B')
        self.assertEqual(proposal_cat.category_name_abbr, 'B')

        # Test category parameter of search_proposal.
        result = self.db.search_proposal(category=category_id_a)
        self.assertEqual(list(result.keys()), [])
        result = self.db.search_proposal(category=category_id_b)
        self.assertEqual(list(result.keys()), [proposal_id])
        result = self.db.search_proposal(category=[category_id_a, category_id_b])
        self.assertEqual(list(result.keys()), [proposal_id])
        result = self.db.search_proposal(category=[1999999, 2999999])
        self.assertEqual(list(result.keys()), [])


def _member_person_set(member_collection):
    return [x.person_id for x in member_collection.values()]


def _co_member_person_ed(co_member_collection):
    return sorted(((x.co_member_person_id, x.editor)
                   for x in co_member_collection.values()))
