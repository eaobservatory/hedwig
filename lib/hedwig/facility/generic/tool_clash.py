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

from collections import namedtuple
from math import pi

from healpy import ang2pix

from ...astro.coord import CoordSystem, parse_coord
from ...error import NoSuchRecord, UserError
from ...view.tool import BaseTargetTool
from ...web.util import ErrorPage, HTTPNotFound, session, url_for
from ...type import TargetObject

TargetCoord = namedtuple('TargetCoord', ('x', 'y', 'system'))

TargetClash = namedtuple('TargetClash', ('target', 'mocs'))


class ClashTool(BaseTargetTool):
    @classmethod
    def get_code(cls):
        """
        Get the target tool "code".
        """

        return 'clash'

    def get_name(self):
        """
        Get the target tool's name.
        """

        return 'Clash Tool'

    def get_custom_routes(self):
        return [
            ('generic/moc_view.html',
             '/tool/clash/moc/<int:moc_id>',
             'tool_clash_moc_info',
             self.view_moc_info,
             {})
        ]

    def view_single(self, db, args, form):
        """
        View handler function for stand-alone usage of the clash tool.
        """

        target = TargetCoord('', '', CoordSystem.ICRS)
        message = None
        clashes = None

        if not form:
            self._check_mocs_exist(db)

        else:
            target = target._replace(x=form['x'], y=form['y'],
                                     system=int(form['system']))

            try:
                target_name = 'Input coordinates'
                target_obj = TargetObject(
                    target_name, target.system,
                    parse_coord(target.system, target.x, target.y,
                                target_name))

                clashes = self._do_moc_search(db, [target_obj])

            except UserError as e:
                message = e.message

        return {
            'title': 'Clash Tool',
            'show_input': True,
            'systems': CoordSystem.get_options(),
            'run_button': 'Search',
            'target': target,
            'message': message,
            'clashes': clashes,
            'target_url': url_for('.tool_clash'),
            'target_moc_info': '.tool_clash_moc_info',
            'target_proposal': None,
        }

    def _view_proposal(self, db, proposal, targets, args):
        target_objects = targets.to_object_list()

        if not target_objects:
            raise ErrorPage('The proposal does not appear to have '
                            'any targets with coordinates.')

        self._check_mocs_exist(db)

        clashes = self._do_moc_search(db, target_objects)

        return {
            'title': 'Clash Tool',
            'show_input': False,
            'clashes': clashes,
            'target_moc_info': '.tool_clash_moc_info',
            'target_proposal': url_for('.proposal_view',
                                       proposal_id=proposal.id),
        }

    def _check_mocs_exist(self, db):
        public = True

        if 'user_id' in session and session.get('is_admin', False):
            # If the user has administrative access, remove public
            # constraint.  (Probably not worthwhile to re-validate
            # administrative access here.)
            public = None

        mocs = db.search_moc(facility_id=self.facility.id_, public=public)
        if not mocs:
            raise ErrorPage('No coverage maps have been set up yet.')

    def _do_moc_search(self, db, targets):
        order = self.facility.get_moc_order()
        clashes = []
        public = True

        if 'user_id' in session and session.get('is_admin', False):
            # If the user has administrative access, remove public
            # constraint.  (Probably not worthwhile to re-validate
            # administrative access here.)
            public = None

        for target in targets:
            # If the coordinates weren't entered in ICRS, use the
            # Astropy transformation to convert them.
            if target.system == CoordSystem.ICRS:
                coord = target.coord
            else:
                coord = target.coord.icrs

            ra_rad = coord.spherical.lon.rad
            dec_rad = coord.spherical.lat.rad
            cell = ang2pix(2 ** order, pi / 2 - dec_rad, ra_rad, nest=True)

            target_clashes = db.search_moc_cell(
                facility_id=self.facility.id_, public=public,
                order=order, cell=int(cell))

            if target_clashes:
                clashes.append(TargetClash(target, target_clashes))

        return clashes

    def view_moc_info(self, db, args, form, moc_id):
        public = True
        if 'user_id' in session and session.get('is_admin', False):
            # If the user has administrative access, remove public
            # constraint.  (Probably not worthwhile to re-validate
            # administrative access here.)
            public = None

        try:
            moc = db.search_moc(
                facility_id=self.facility.id_, public=public,
                moc_id=moc_id, with_description=True).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Coverage map not found.')

        return {
            'title': 'Coverage: {}'.format(moc.name),
            'moc': moc,
        }
