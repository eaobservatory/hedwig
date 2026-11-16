# Copyright (C) 2026 East Asian Observatory
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

from pymoc import MOC

from hedwig.astro.catalog import parse_source_list
from hedwig.facility.generic.view import Generic
from hedwig.facility.generic.tool_clash import ClashTool
from hedwig.type.enum import FormatType
from hedwig.view.tool import BaseTargetTool

from .dummy_db import DBTestCase


class ClashToolTest(DBTestCase):
    def test_search(self):
        # Create a level 0 MOC with just one cell.
        moc = MOC(order=0, cells=(0,))

        facility_id = self.db.ensure_facility('test')
        moc_id = self.db.add_moc(
            facility_id, 'test',
            'Test', FormatType.PLAIN,
            True, moc)
        self.db.update_moc_cell(moc_id, moc, block_pause=0)

        facility = DummyFacility(id_=facility_id)
        tool = ClashTool(facility=facility, id_=None)
        self.assertIsInstance(tool, BaseTargetTool)

        (clashes, non_clashes) = tool._do_moc_search(
            db=self.db,
            targets=parse_source_list(
                # Sources in the middle of the MOC's cell
                # and the opposing cell.
                b'\n'.join([
                    b'In 45.0 41.8 ICRS',
                    b'Out 225.0 41.8 ICRS',
                ]),
                as_object_list=True,
            ),
            public=None,
            radius=60,
        )

        # Check each source was returned in the correct list.
        self.assertEqual([x.target.name for x in clashes], ['In'])
        self.assertEqual([x.target.name for x in non_clashes], ['Out'])


class DummyFacility(Generic):
    def get_moc_order(self):
        return 0
