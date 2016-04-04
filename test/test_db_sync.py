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

from hedwig.error import UserError
from hedwig.type.collection import ResultCollection
from hedwig.type.simple import Affiliation, Category

from .dummy_db import DBTestCase


class DBSyncTest(DBTestCase):
    def test_sync_affiliation(self):
        """
        Test troublesome sync situations for affiliations.
        """

        facility_id = self.db.ensure_facility('test_tel')
        self.assertIsInstance(facility_id, int)
        queue_id = self.db.add_queue(facility_id, 'Queue1', 'Q1')
        self.assertIsInstance(queue_id, int)

        records = ResultCollection()
        records[0] = Affiliation(
            None, queue_id, 'Aff A', False, False, False, None)
        records[1] = Affiliation(
            None, queue_id, 'Aff B', False, False, False, None)
        records[2] = Affiliation(
            None, queue_id, 'Aff C', False, False, False, None)
        records[3] = Affiliation(
            None, queue_id, 'Aff D', False, False, False, None)
        records[4] = Affiliation(
            None, queue_id, 'Aff E', False, False, False, None)
        records[5] = Affiliation(
            None, queue_id, 'Aff F', False, False, False, None)

        n = self.db.sync_queue_affiliation(queue_id, records)
        self.assertEqual(n, (6, 0, 0))

        records = self.db.search_affiliation(queue_id=queue_id,
                                             order_by_id=True)
        id_ = list(records.keys())

        # Delete an affiliation and rename another affiliation to its old name.
        records[id_[0]] = records[id_[0]]._replace(name='Aff F')
        with self.assertRaisesRegexp(UserError, 'duplicate values'):
            self.db.sync_queue_affiliation(queue_id, records)
        del records[id_[5]]
        n = self.db.sync_queue_affiliation(queue_id, records)
        self.assertEqual(n, (0, 1, 1))

        self.assertEqual(
            [x.name for x in self.db.search_affiliation(
                queue_id=queue_id, order_by_id=True).values()],
            ['Aff F', 'Aff B', 'Aff C', 'Aff D', 'Aff E'])

        # Rename an affiliation and rename another to its previous name.
        records[id_[1]] = records[id_[1]]._replace(name='Aff E')
        records[id_[4]] = records[id_[4]]._replace(name='Aff EE')
        n = self.db.sync_queue_affiliation(queue_id, records)
        self.assertEqual(n, (0, 2, 0))

        self.assertEqual(
            [x.name for x in self.db.search_affiliation(
                queue_id=queue_id, order_by_id=True).values()],
            ['Aff F', 'Aff E', 'Aff C', 'Aff D', 'Aff EE'])

    def test_sync_affiliation_circular(self):
        """
        Test circular sync of affiliations.
        """

        facility_id = self.db.ensure_facility('test_tel')
        self.assertIsInstance(facility_id, int)
        queue_id = self.db.add_queue(facility_id, 'Queue1', 'Q1')
        self.assertIsInstance(queue_id, int)

        records = ResultCollection()
        records[0] = Affiliation(
            None, queue_id, 'Aff A', False, False, False, None)
        records[1] = Affiliation(
            None, queue_id, 'Aff B', False, False, False, None)
        records[2] = Affiliation(
            None, queue_id, 'Aff C', False, False, False, None)
        records[3] = Affiliation(
            None, queue_id, 'Aff D', False, False, False, None)
        records[4] = Affiliation(
            None, queue_id, 'Aff E', False, False, False, None)

        n = self.db.sync_queue_affiliation(queue_id, records)
        self.assertEqual(n, (5, 0, 0))

        records = self.db.search_affiliation(queue_id=queue_id,
                                             order_by_id=True)
        id_ = list(records.keys())

        records[id_[1]] = records[id_[1]]._replace(name='Aff C')
        records[id_[2]] = records[id_[2]]._replace(name='Aff D')
        records[id_[3]] = records[id_[3]]._replace(name='Aff B')

        with self.assertRaisesRegexp(UserError, 'Circular update'):
            self.db.sync_queue_affiliation(queue_id, records)

    def test_sync_category(self):
        """
        Test sync of a facility's categories including uniqueness problems.
        """

        facility_id = self.db.ensure_facility('test_tel')
        self.assertIsInstance(facility_id, int)

        records = ResultCollection()
        records[0] = Category(None, facility_id, 'Cat 1', False)
        records[1] = Category(None, facility_id, 'Cat 2', False)
        records[2] = Category(None, facility_id, 'Cat 3', False)
        records[3] = Category(None, facility_id, 'Cat 4', False)

        n = self.db.sync_facility_category(facility_id, records)
        self.assertEqual(n, (4, 0, 0))

        records = self.db.search_category(facility_id=facility_id,
                                          order_by_id=True)
        self.assertEqual([x.name for x in records.values()],
                         ['Cat 1', 'Cat 2', 'Cat 3', 'Cat 4'])

        id_ = list(records.keys())

        records[id_[1]] = records[id_[1]]._replace(name='Cat 3')
        records[id_[2]] = records[id_[2]]._replace(name='Cat 4')
        records[id_[3]] = records[id_[3]]._replace(name='Cat 5')

        n = self.db.sync_facility_category(facility_id, records)
        self.assertEqual(n, (0, 3, 0))

        records = self.db.search_category(facility_id=facility_id,
                                          order_by_id=True)
        self.assertEqual([x.name for x in records.values()],
                         ['Cat 1', 'Cat 3', 'Cat 4', 'Cat 5'])

    def test_sync_email(self):
        person_id = self.db.add_person('Test Person')
        email_1 = self.db.add_email(person_id, 'a@x', primary=True)
        email_2 = self.db.add_email(person_id, 'b@x')
        email_3 = self.db.add_email(person_id, 'c@x')

        records = self.db.search_email(person_id=person_id)

        self.assertEqual([x.address for x in records.values()],
                         ['a@x', 'b@x', 'c@x'])

        id_ = list(records.keys())

        # Make a circular update.
        records[id_[0]] = records[id_[0]]._replace(address='b@x')
        records[id_[1]] = records[id_[1]]._replace(address='c@x')
        records[id_[2]] = records[id_[2]]._replace(address='a@x')

        n = self.db.sync_person_email(person_id, records)
        self.assertEqual(n, (0, 3, 0))

        records = self.db.search_email(person_id=person_id)

        # Expect first address to have moved to the end due to re-insertion.
        self.assertEqual([x.address for x in records.values()],
                         ['c@x', 'a@x', 'b@x'])
        self.assertEqual([x.primary for x in records.values()],
                         [False, False, True])
