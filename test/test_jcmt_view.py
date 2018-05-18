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

from hedwig.compat import string_type
from hedwig.error import NoSuchRecord, ParseError
from hedwig.facility.jcmt.type import JCMTAncillary, JCMTInstrument, \
    JCMTRequest, JCMTRequestCollection, \
    JCMTReview, JCMTReviewerExpertise, \
    JCMTWeather
from hedwig.type.collection import ProposalCollection, ReviewerCollection
from hedwig.type.enum import FormatType, ReviewState
from hedwig.type.simple import Link, Proposal, Reviewer
from hedwig.type.util import null_tuple

from .dummy_facility import FacilityTestCase


class JCMTFacilityTestCase(FacilityTestCase):
    facility_spec = 'JCMT'

    def test_basic_info(self):
        self._test_basic_info(expect_code='jcmt')

    def test_proposal_code(self):
        types = self.view.get_call_types()

        proposal_1 = self._create_test_proposal('20A', 'P', types.STANDARD)
        proposal_2 = self._create_test_proposal('20A', 'P', types.STANDARD)
        proposal_3 = self._create_test_proposal('20B', 'P', types.STANDARD)
        proposal_4 = self._create_test_proposal('20B', 'L', types.STANDARD)
        proposal_5 = self._create_test_proposal('20A', 'P', types.IMMEDIATE)

        def check_code(proposal_id, proposal_code):
            self.assertEqual(self.view.make_proposal_code(
                self.db, self.db.get_proposal(self.facility_id, proposal_id)),
                proposal_code)

            self.assertEqual(
                self.view.parse_proposal_code(self.db, proposal_code),
                proposal_id)

        check_code(proposal_1, 'M20AP001')
        check_code(proposal_2, 'M20AP002')
        check_code(proposal_3, 'M20BP001')
        check_code(proposal_4, 'M20BL001')
        check_code(proposal_5, 'S20AP001')

        with self.assertRaisesRegex(
                ParseError, "^Proposal code did not match expected pattern"):
            self.view.parse_proposal_code(self.db, 'ABCDEF')

        with self.assertRaisesRegex(
                ParseError, "^Did not recognise call type code"):
            self.view.parse_proposal_code(self.db, 'X11AP111')

        with self.assertRaises(NoSuchRecord):
            self.view.parse_proposal_code(self.db, 'M20AP999')

    def test_overall_rating(self):
        role_class = self.view.get_reviewer_roles()

        c = ReviewerCollection()

        self.assertIsNone(self.view.calculate_overall_rating(c))

        def make_review(id, role, rating, expertise):
            return null_tuple(Reviewer)._replace(
                id=101, role=role, review_rating=rating,
                review_state=ReviewState.DONE,
                review_extra=null_tuple(JCMTReview)._replace(
                    expertise=expertise))

        # Add reviews without ratings included in the calculation.
        c[101] = make_review(101, role_class.TECH, None, None)
        c[102] = make_review(102, role_class.EXTERNAL, 100, None)

        self.assertIsNone(self.view.calculate_overall_rating(c))

        (r, s) = self.view.calculate_overall_rating(c, with_std_dev=True)
        self.assertIsNone(r)
        self.assertIsNone(s)

        # Add some equally-weighted reviews.
        c[201] = make_review(
            201, role_class.CTTEE_OTHER, 20, JCMTReviewerExpertise.NON_EXPERT)
        c[202] = make_review(
            202, role_class.CTTEE_OTHER, 40, JCMTReviewerExpertise.NON_EXPERT)

        self.assertAlmostEqual(self.view.calculate_overall_rating(c), 30)

        (r, s) = self.view.calculate_overall_rating(c, with_std_dev=True)
        self.assertAlmostEqual(r, 30)
        self.assertIsNotNone(s)

        # Add a higher-weighted review.
        c[301] = make_review(
            301, role_class.CTTEE_PRIMARY, 70, JCMTReviewerExpertise.EXPERT)

        self.assertAlmostEqual(self.view.calculate_overall_rating(c), 50)

        (r, s) = self.view.calculate_overall_rating(c, with_std_dev=True)
        self.assertAlmostEqual(r, 50)
        self.assertIsNotNone(s)

    def test_archive_url(self):
        url = self.view.make_archive_search_url(180.0, 45.0)
        self.assertIsInstance(url, string_type)
        self.assertTrue(url.startswith('http://www.cadc-ccda'))

    def test_proposal_urls(self):
        urls = self.view.make_proposal_info_urls('M99XY001')
        self.assertIsInstance(urls, list)
        self.assertEqual(len(urls), 2)
        for (url, expect) in zip(urls, ('OMP', 'CADC')):
            self.assertIsInstance(url, Link)
            self.assertEqual(url.text, expect)
            self.assertIsInstance(url.url, string_type)

        # Check URL generation with unusual characters in project code.
        urls = self.view.make_proposal_info_urls('M99\u201cZZZ\u201d001')
        urls = {url.text: url.url for url in urls}
        self.assertEqual(sorted(urls.keys()), ['CADC', 'OMP'])
        url_omp = urls['OMP']
        self.assertIsInstance(url_omp, string_type)
        self.assertEqual(
            url_omp, 'http://omp.eao.hawaii.edu/cgi-bin/'
            'projecthome.pl?urlprojid=M99%E2%80%9CZZZ%E2%80%9D001')

    def test_attach_review(self):
        types = self.view.get_call_types()
        roles = self.view.get_reviewer_roles()

        # Create test proposals and reviews.
        proposal_1 = self._create_test_proposal('20A', 'P', types.STANDARD)
        proposal_2 = self._create_test_proposal('20A', 'P', types.STANDARD)

        person_id = self.db.add_person('Test Reviewer')

        review_1a = self.db.add_reviewer(
            roles, proposal_1, person_id, roles.CTTEE_PRIMARY)
        self.db.set_review(
            roles, review_1a, text='test', format_=FormatType.PLAIN,
            assessment=None, rating=30, weight=None,
            note='', note_format=FormatType.PLAIN, note_public=False,
            state=ReviewState.DONE, is_update=False)
        self.db.set_jcmt_review(
            roles, review_1a, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.EXPERT), is_update=False)

        review_1b = self.db.add_reviewer(
            roles, proposal_1, person_id, roles.CTTEE_SECONDARY)
        self.db.set_review(
            roles, review_1b, text='test', format_=FormatType.PLAIN,
            assessment=None, rating=40, weight=None,
            note='', note_format=FormatType.PLAIN, note_public=False,
            state=ReviewState.DONE, is_update=False)
        self.db.set_jcmt_review(
            roles, review_1b, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.INTERMEDIATE), is_update=False)

        review_2a = self.db.add_reviewer(
            roles, proposal_2, person_id, roles.CTTEE_PRIMARY)
        self.db.set_review(
            roles, review_2a, text='test', format_=FormatType.PLAIN,
            assessment=None, rating=50, weight=None,
            note='', note_format=FormatType.PLAIN, note_public=False,
            state=ReviewState.DONE, is_update=False)
        self.db.set_jcmt_review(
            roles, review_2a, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.NON_EXPERT), is_update=False)

        review_2b = self.db.add_reviewer(
            roles, proposal_2, person_id, roles.CTTEE_SECONDARY)
        self.db.set_review(
            roles, review_2b, text='test', format_=FormatType.PLAIN,
            assessment=None, rating=60, weight=None,
            note='', note_format=FormatType.PLAIN, note_public=False,
            state=ReviewState.DONE, is_update=False)
        self.db.set_jcmt_review(
            roles, review_2b, review_state=ReviewState.DONE,
            review=null_tuple(JCMTReview)._replace(
                expertise=JCMTReviewerExpertise.NON_EXPERT), is_update=False)

        # Expected data for tests.
        expect = {
            proposal_1: {
                review_1a: {'r': 30, 'e': JCMTReviewerExpertise.EXPERT},
                review_1b: {'r': 40, 'e': JCMTReviewerExpertise.INTERMEDIATE},
            },
            proposal_2: {
                review_2a: {'r': 50, 'e': JCMTReviewerExpertise.NON_EXPERT},
                review_2b: {'r': 60, 'e': JCMTReviewerExpertise.NON_EXPERT},
            }
        }

        # Original proposal collection should not have JCMT review info.
        c = self.db.search_proposal(with_reviewers=True, with_review_info=True)
        self.assertIsInstance(c, ProposalCollection)

        self.assertEqual(set(c.keys()), set(expect.keys()))

        for proposal in c.values():
            proposal_expect = expect[proposal.id]

            rc = proposal.reviewers
            self.assertIsInstance(rc, ReviewerCollection)
            self.assertEqual(set(rc.keys()), set(proposal_expect.keys()))

            for reviewer in rc.values():
                reviewer_expect = proposal_expect[reviewer.id]

                self.assertEqual(reviewer.review_rating, reviewer_expect['r'])
                self.assertIsNone(reviewer.review_extra)

        # Attach the JCMT information.
        self.view.attach_review_extra(self.db, c)

        # Check that the collection has been updated correctly.
        self.assertEqual(set(c.keys()), set(expect.keys()))

        for proposal in c.values():
            proposal_expect = expect[proposal.id]

            rc = proposal.reviewers
            self.assertIsInstance(rc, ReviewerCollection)
            self.assertEqual(set(rc.keys()), set(proposal_expect.keys()))

            for reviewer in rc.values():
                reviewer_expect = proposal_expect[reviewer.id]

                self.assertEqual(reviewer.review_rating, reviewer_expect['r'])
                self.assertIsInstance(reviewer.review_extra, JCMTReview)
                self.assertEqual(reviewer.review_extra.expertise,
                                 reviewer_expect['e'])

    def test_feedback_extra(self):
        # Set up test proposal with a JCMT allocation.
        types = self.view.get_call_types()
        proposal_id = self._create_test_proposal('20A', 'P', types.STANDARD)
        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id)

        rc = JCMTRequestCollection()
        rc[1] = null_tuple(JCMTRequest)._replace(
            instrument=JCMTInstrument.HARP, ancillary=JCMTAncillary.NONE,
            weather=JCMTWeather.BAND5, time=4.5)

        self.db.sync_jcmt_proposal_allocation(proposal_id, rc)

        # Test the get_feedback_extra method.
        extra = self.view.get_feedback_extra(self.db, proposal)

        self.assertIsInstance(extra, dict)

        self.assertEqual(set(extra.keys()), set(('jcmt_allocation',)))

        alloc = extra['jcmt_allocation']

        self.assertIsInstance(alloc, list)

        self.assertEqual(len(alloc), 1)

        a = alloc[0]

        self.assertEqual(a.instrument, 'HARP')
        self.assertEqual(a.weather, 'Band 5')
        self.assertEqual(a.time, 4.5)
        self.assertIsNone(a.ancillary)
