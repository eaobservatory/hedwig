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
import re

from healpy import ang2pix

from ...astro.coord import CoordSystem, format_coord, parse_coord
from ...astro.catalog import parse_source_list
from ...error import NoSuchRecord, UserError
from ...view.tool import BaseTargetTool
from ...web.util import ErrorPage, HTTPNotFound, session, url_for
from ...type import FileTypeInfo, Link, TargetObject

TargetCoord = namedtuple('TargetCoord', ('x', 'y', 'system'))

TargetClash = namedtuple('TargetClash', ('target', 'mocs', 'target_search',
                                         'display_coord'))


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
             {}),
            (None,
             '/tool/clash/moc/<int:moc_id>/fits',
             'tool_clash_moc_fits',
             self.view_moc_fits,
             {}),
            ('generic/moc_view_list.html',
             '/tool/clash/moc/',
             'tool_clash_moc_list',
             self.view_moc_list,
             {}),
        ]

    def view_single(self, db, args, form):
        """
        View handler function for stand-alone usage of the clash tool.
        """

        target = TargetCoord('', '', CoordSystem.ICRS)
        message = None
        clashes = None
        non_clashes = None

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

                (clashes, non_clashes) = self._do_moc_search(db, [target_obj])

            except UserError as e:
                message = e.message

        return {
            'title': 'Clash Tool',
            'show_input': True,
            'show_input_upload': False,
            'systems': CoordSystem.get_options(),
            'run_button': 'Search',
            'target': target,
            'message': message,
            'clashes': clashes,
            'non_clashes': non_clashes,
            'target_url': url_for('.tool_clash'),
            'target_moc_info': '.tool_clash_moc_info',
            'target_upload': url_for('.tool_upload_clash'),
        }

    def view_upload(self, db, args, form, file_):
        """
        View handler for stand-alone usage by file upload.
        """

        message = None
        clashes = None
        non_clashes = None

        if form is None:
            self._check_mocs_exist(db)

        else:
            try:
                if file_:
                    try:
                        buff = file_.read(64 * 1024)
                        if len(file_.read(1)):
                            raise UserError('The uploaded file was too large.')
                    finally:
                        file_.close()
                else:
                    raise UserError('No target list file was received.')

                # TODO: would be more efficient to update parse_source_list
                # to be able to return a list directly: this converts to
                # and from Astropy objects twice.
                target_objects = parse_source_list(buff).to_object_list()

                (clashes, non_clashes) = self._do_moc_search(db,
                                                             target_objects)

            except UserError as e:
                message = e.message

        return {
            'title': 'Clash Tool',
            'show_input': True,
            'show_input_upload': True,
            'run_button': 'Search',
            'mime_types': ['text/plain', 'text/csv'],
            'message': message,
            'clashes': clashes,
            'non_clashes': non_clashes,
            'target_url': url_for('.tool_upload_clash'),
            'target_moc_info': '.tool_clash_moc_info',
        }

    def _view_proposal(self, db, proposal, targets, args):
        target_objects = targets.to_object_list()

        if not target_objects:
            raise ErrorPage(
                'The proposal does not appear to have any targets '
                'with coordinates.',
                links=[Link('Back to proposal', url_for(
                    '.proposal_view', proposal_id=proposal.id,
                    _anchor='targets'))])

        self._check_mocs_exist(db)

        (clashes, non_clashes) = self._do_moc_search(db, target_objects)

        return {
            'title': 'Clash Tool',
            'show_input': False,
            'clashes': clashes,
            'non_clashes': non_clashes,
            'target_moc_info': '.tool_clash_moc_info',
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
        non_clashes = []
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

            archive_url = self.facility.make_archive_search_url(
                coord.spherical.lon.deg, coord.spherical.lat.deg)
            archive_url_text = ' '.join(format_coord(CoordSystem.ICRS, coord))

            if target_clashes:
                clashes.append(TargetClash(
                    target, target_clashes, archive_url, archive_url_text))

            else:
                non_clashes.append(TargetClash(
                    target, None, archive_url, archive_url_text))

        return (clashes, non_clashes)

    def view_moc_list(self, db, args, form):
        public = True
        if 'user_id' in session and session.get('is_admin', False):
            # If the user has administrative access, remove public
            # constraint.  (Probably not worthwhile to re-validate
            # administrative access here.)
            public = None

        mocs = db.search_moc(facility_id=self.facility.id_, public=public)

        return {
            'title': 'Coverage List',
            'mocs': mocs.values(),
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

    def view_moc_fits(self, db, args, form, moc_id):
        public = True
        if 'user_id' in session and session.get('is_admin', False):
            # If the user has administrative access, remove public
            # constraint.  (Probably not worthwhile to re-validate
            # administrative access here.)
            public = None

        try:
            moc = db.search_moc(
                facility_id=self.facility.id_, public=public,
                moc_id=moc_id, with_description=False).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Coverage map not found.')

        try:
            moc_fits = db.get_moc_fits(moc_id)
        except NoSuchRecord:
            raise HTTPNotFound('The FITS file for this coverage map '
                               'appears to be missing.')

        return (
            moc_fits,
            FileTypeInfo(name='FITS', mime='application/fits', preview=None),
            '{}.fits'.format(re.sub('[^-_a-z0-9]', '_', moc.name.lower())))
