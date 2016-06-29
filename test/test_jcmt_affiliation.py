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

from unittest import TestCase

from hedwig.facility.jcmt.view import JCMT
from hedwig.type.collection import AffiliationCollection, MemberCollection
from hedwig.type.enum import AffiliationType
from hedwig.type.simple import Affiliation, Member
from hedwig.type.util import null_tuple


class JCMTAffiliationTestCase(TestCase):
    def test_affiliation_assignment(self):
        # Set up "constants" for test affiliation IDs.
        UNKNOWN = 0  # Returned by Hedwig.
        AFF_1 = 1
        AFF_2 = 2
        AFF_3 = 3
        STAFF = 5
        OTHER = 6
        MISSING = 7  # Used to test behavior with invalid input values.

        # Prepare affiliations.
        affiliations = AffiliationCollection()

        affiliations[AFF_1] = Affiliation(
            AFF_1, None, 'Aff 1',
            hidden=False, type=AffiliationType.STANDARD, weight=50)
        affiliations[AFF_2] = Affiliation(
            AFF_2, None, 'Aff 2',
            hidden=False, type=AffiliationType.STANDARD, weight=20)
        affiliations[AFF_3] = Affiliation(
            AFF_3, None, 'Aff 3',
            hidden=False, type=AffiliationType.STANDARD, weight=20)
        affiliations[STAFF] = Affiliation(
            STAFF, None, 'Staff',
            hidden=False, type=AffiliationType.SHARED, weight=None)
        affiliations[OTHER] = Affiliation(
            OTHER, None, 'Other',
            hidden=False, type=AffiliationType.EXCLUDED, weight=None)

        # Perform test: no members at all.
        self._test_affiliation_assignment(
            'No members',
            affiliations, None, [],
            {UNKNOWN: 1.0})

        # Perform tests: PI only.
        self._test_affiliation_assignment(
            'Simple PI only',
            affiliations, AFF_1, [],
            {AFF_1: 1.0})

        self._test_affiliation_assignment(
            'Excluded PI only',
            affiliations, OTHER, [],
            {UNKNOWN: 1.0})

        self._test_affiliation_assignment(
            'Invalid PI only',
            affiliations, MISSING, [],
            {UNKNOWN: 1.0})

        # Perform tests: CoIs only.
        self._test_affiliation_assignment(
            '1 simple CoI only',
            affiliations, None, [AFF_2],
            {AFF_2: 1.0})

        self._test_affiliation_assignment(
            '1 invalid CoI only',
            affiliations, None, [MISSING],
            {UNKNOWN: 1.0})

        self._test_affiliation_assignment(
            '2 simple CoIs only',
            affiliations, None, [AFF_2, AFF_3],
            {AFF_2: 0.5, AFF_3: 0.5})

        self._test_affiliation_assignment(
            '2 simple CoIs only (incl. invalid)',
            affiliations, None, [AFF_1, MISSING],
            {AFF_1: 0.5, UNKNOWN: 0.5})

        self._test_affiliation_assignment(
            '2 simple CoIs only (incl. invalid higher weight)',
            affiliations, None, [AFF_2, MISSING],
            {AFF_2: 20 / 70, UNKNOWN: 50 / 70})

        self._test_affiliation_assignment(
            '3 simple CoIs only',
            affiliations, None, [AFF_2, AFF_3, AFF_3],
            {AFF_2: 1 / 3, AFF_3: 2 / 3})

        self._test_affiliation_assignment(
            '2 simple CoIs with weighting',
            affiliations, None, [AFF_1, AFF_2],
            {AFF_1: 50 / 70, AFF_2: 20 / 70})

        self._test_affiliation_assignment(
            '4 simple CoIs with weighting',
            affiliations, None, [AFF_1, AFF_2, AFF_2, AFF_3],
            {AFF_1: 50 / 110, AFF_2: 40 / 110, AFF_3: 20 / 110})

        self._test_affiliation_assignment(
            '1 excluded CoI only',
            affiliations, None, [OTHER],
            {UNKNOWN: 1.0})

        self._test_affiliation_assignment(
            '2 CoIs only with excluded (equal weight)',
            affiliations, None, [AFF_1, OTHER],
            {AFF_1: 0.5, 0: 0.5})

        self._test_affiliation_assignment(
            '2 CoIs only with excluded (higher weight)',
            affiliations, None, [AFF_2, OTHER],
            {AFF_2: 20 / 70, UNKNOWN: 50 / 70})

        # Perform tests: PI and CoIs (simple).
        self._test_affiliation_assignment(
            'Complete simple (equal weight)',
            affiliations, AFF_1, [AFF_2, AFF_3],
            {AFF_1: 0.5, AFF_2: 0.25, AFF_3: 0.25})

        self._test_affiliation_assignment(
            'Complete simple (different weight)',
            affiliations, AFF_2, [AFF_1, AFF_3],
            {AFF_2: 0.5, AFF_1: 0.5 * 50 / 70, AFF_3: 0.5 * 20 / 70})

        self._test_affiliation_assignment(
            'Complete simple (multiple equal weight)',
            affiliations, AFF_1, [AFF_2, AFF_2, AFF_3, AFF_3, AFF_3],
            {AFF_1: 0.5, AFF_2: 0.5 * 2 / 5, AFF_3: 0.5 * 3 / 5})

        self._test_affiliation_assignment(
            'Complete simple (multiple different weight)',
            affiliations, AFF_2, [AFF_1, AFF_1, AFF_3, AFF_3, AFF_3],
            {AFF_2: 0.5,
             AFF_1: 0.5 * ((2 * 50) / (2 * 50 + 3 * 20)),
             AFF_3: 0.5 * ((3 * 20) / (2 * 50 + 3 * 20))})

        # Perform tests: PI and CoIs (with excluded).
        self._test_affiliation_assignment(
            'Complete with excluded PI',
            affiliations, OTHER, [AFF_2, AFF_2],
            {UNKNOWN: 0.5, AFF_2: 0.5})

        self._test_affiliation_assignment(
            'Complete with excluded CoI',
            affiliations, AFF_1, [AFF_2, OTHER],
            {AFF_1: 0.5 + 0.5 * (50 / 70), AFF_2: 0.5 * (20 / 70)})

        self._test_affiliation_assignment(
            'Complete with excluded CoI (lower weight PI)',
            affiliations, AFF_2, [AFF_1, OTHER],
            {AFF_2: 0.5 + 0.5 * (20 / 70), AFF_1: 0.5 * (50 / 70)})

        self._test_affiliation_assignment(
            'Complete with excluded PI and CoI (equal weight)',
            affiliations, OTHER, [AFF_1, OTHER],
            {UNKNOWN: 0.5 + 0.25, AFF_1: 0.25})

        self._test_affiliation_assignment(
            'Complete with excluded PI and CoI (higher weight)',
            affiliations, OTHER, [AFF_2, OTHER],
            {UNKNOWN: 0.5 + 0.5 * (50 / 70), AFF_2: 0.5 * (20 / 70)})

        # Perform tests: shared affiliations.
        self._test_affiliation_assignment(
            'Shared PI only',
            affiliations, STAFF, [],
            {AFF_1: 50 / 90, AFF_2: 20 / 90, AFF_3: 20 / 90})

        self._test_affiliation_assignment(
            'Shared PI and 1 CoI',
            affiliations, STAFF, [AFF_1],
            {AFF_1: 0.5 * (50 / 90) + 0.5,
             AFF_2: 0.5 * (20 / 90),
             AFF_3: 0.5 * (20 / 90)})

        self._test_affiliation_assignment(
            'Shared PI and 2 CoIs',
            affiliations, STAFF, [AFF_1, AFF_2],
            {AFF_1: 0.5 * (50 / 90) + 0.5 * (50 / 70),
             AFF_2: 0.5 * (20 / 90) + 0.5 * (20 / 70),
             AFF_3: 0.5 * (20 / 90)})

        self._test_affiliation_assignment(
            'Shared PI and 3 CoIs',
            affiliations, STAFF, [AFF_1, AFF_2, AFF_2],
            {AFF_1: 0.5 * (50 / 90) + 0.5 * (50 / 90),
             AFF_2: 0.5 * (20 / 90) + 0.5 * (40 / 90),
             AFF_3: 0.5 * (20 / 90)})

        self._test_affiliation_assignment(
            'Simple PI and shared CoI',
            affiliations, AFF_1, [STAFF],
            {AFF_1: 1.0})

        self._test_affiliation_assignment(
            'Simple PI and 2 shared CoIs',
            affiliations, AFF_1, [STAFF, STAFF],
            {AFF_1: 1.0})

        self._test_affiliation_assignment(
            'Simple PI and shared and normal (low weight) CoIs',
            affiliations, AFF_1, [AFF_2, STAFF],
            {AFF_1: 0.5 + 0.5 * (50 / (50 + 20)),
             AFF_2: 0.5 * (20 / (50 + 20))})

        self._test_affiliation_assignment(
            'Simple PI and shared and normal (high weight) CoIs',
            affiliations, AFF_1, [AFF_1, STAFF],
            {AFF_1: 1.0})

        self._test_affiliation_assignment(
            'Simple PI and shared and missing CoIs',
            affiliations, AFF_1, [UNKNOWN, STAFF],
            {AFF_1: 0.5 + 0.5 * (50 / (50 + 50)),
             UNKNOWN: 0.5 * (50 / (50 + 50))})

        self._test_affiliation_assignment(
            'Shared PI and excluded CoI',
            affiliations, STAFF, [OTHER],
            {AFF_1: 0.5 * (50 / 90),
             AFF_2: 0.5 * (20 / 90),
             AFF_3: 0.5 * (20 / 90),
             UNKNOWN: 0.5})

        self._test_affiliation_assignment(
            'Shared PI and shared CoI',
            affiliations, STAFF, [STAFF],
            {AFF_1: 0.5 * (50 / 90),
             AFF_2: 0.5 * (20 / 90),
             AFF_3: 0.5 * (20 / 90),
             UNKNOWN: 0.5})

        self._test_affiliation_assignment(
            'Shared PI and shared and normal CoI',
            affiliations, STAFF, [STAFF, AFF_2],
            {AFF_1: 0.5 * (50 / 90),
             AFF_2: 0.5 * (20 / 90) +
                0.5 * (20 / (50 + 20)),
             AFF_3: 0.5 * (20 / 90),
             UNKNOWN: 0.5 * 50 / (50 + 20)})

        self._test_affiliation_assignment(
            'Shared PI and multiple CoIs',
            affiliations, STAFF, [AFF_1, AFF_2, AFF_2, STAFF, OTHER],
            {AFF_1: 0.5 * (50 / 90) +
                0.5 * (50 / 190),
             AFF_2: 0.5 * (20 / 90) +
                0.5 * (2 * 20 / 190),
             AFF_3: 0.5 * (20 / 90),
             UNKNOWN: 0.5 * 2 * (50 / 190)})

    def _test_affiliation_assignment(self, title, affiliations, pi, cois,
                                     ref_assignment):
        view = JCMT(1)

        # Prepare member collection.
        members = MemberCollection()

        i = 0

        if pi is not None:
            i += 1
            members[i] = null_tuple(Member)._replace(
                id=i, affiliation_id=pi, pi=True)

        for coi in cois:
            i += 1
            members[i] = null_tuple(Member)._replace(
                id=i, affiliation_id=coi, pi=False)

        # Compute assignment, make set of affiliations and check total.
        assignment = view.calculate_affiliation_assignment(
            db=None, members=members, affiliations=affiliations)

        assigned_affiliations = set(assignment.keys())
        assigned_total = sum(assignment.values())

        self.assertAlmostEqual(
            assigned_total, 1.0,
            msg='{}: total assignment not equal to 1'.format(title))

        # Check that the assignmenets match those specified.
        for (aff_id, aff_frac) in ref_assignment.items():
            self.assertIn(
                aff_id, assignment,
                msg='{}: affiliation {} missing'.format(title, aff_id))
            self.assertAlmostEqual(
                assignment[aff_id], aff_frac,
                msg='{}: affiliation {}: {} (should be {})'.format(
                    title, aff_id, assignment[aff_id], aff_frac),
                places=5)
            assigned_affiliations.remove(aff_id)

        # There should be no other un-matched assignments.
        self.assertFalse(
            assigned_affiliations,
            msg='{}: extra affiliations present: {!r}'.format(
                title, list(assigned_affiliations)))
