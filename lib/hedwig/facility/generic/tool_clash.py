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

TargetCoord = namedtuple('TargetCoord', ('x', 'y', 'system'))


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
             '/tool/clash/<int:moc_id>',
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
        public = True

        if 'user_id' in session and session.get('is_admin', False):
            # If the user has administrative access, remove public
            # constraint.  (Probably not worthwhile to re-validate
            # administrative access here.)
            public = None

        if not form:
            mocs = db.search_moc(facility_id=self.facility.id_, public=public)
            if not mocs:
                raise ErrorPage('No coverage maps have been set up yet.')

        else:
            target = target._replace(x=form['x'], y=form['y'],
                                     system=int(form['system']))

            try:
                coord = parse_coord(target.system, target.x, target.y,
                                    'search target')

                # If the coordinates weren't entered in ICRS, use the
                # Astropy transformation to convert them.
                if target.system != CoordSystem.ICRS:
                    coord = coord.icrs

                order = self.facility.get_moc_order()
                ra_rad = coord.spherical.lon.rad
                dec_rad = coord.spherical.lat.rad
                cell = ang2pix(2 ** order, pi / 2 - dec_rad, ra_rad, nest=True)

                clashes = db.search_moc_cell(
                    facility_id=self.facility.id_, public=public,
                    order=order, cell=int(cell))

            except UserError as e:
                message = e.message

        return {
            'title': 'Clash Tool',
            'systems': CoordSystem.get_options(),
            'run_button': 'Search',
            'target': target,
            'message': message,
            'clashes': clashes,
            'target_url': url_for('.tool_clash'),
            'target_moc_info': '.tool_clash_moc_info',
        }

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
