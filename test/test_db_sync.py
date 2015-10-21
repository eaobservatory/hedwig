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
from hedwig.type import Affiliation, ResultCollection

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
        records[0] = Affiliation(None, queue_id, 'Aff A', False, False, None)
        records[1] = Affiliation(None, queue_id, 'Aff B', False, False, None)
        records[2] = Affiliation(None, queue_id, 'Aff C', False, False, None)
        records[3] = Affiliation(None, queue_id, 'Aff D', False, False, None)
        records[4] = Affiliation(None, queue_id, 'Aff E', False, False, None)
        records[5] = Affiliation(None, queue_id, 'Aff F', False, False, None)

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
        records[0] = Affiliation(None, queue_id, 'Aff A', False, False, None)
        records[1] = Affiliation(None, queue_id, 'Aff B', False, False, None)
        records[2] = Affiliation(None, queue_id, 'Aff C', False, False, None)
        records[3] = Affiliation(None, queue_id, 'Aff D', False, False, None)
        records[4] = Affiliation(None, queue_id, 'Aff E', False, False, None)

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
