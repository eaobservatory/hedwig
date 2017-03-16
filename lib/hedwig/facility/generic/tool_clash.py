# Copyright (C) 2015-2017 East Asian Observatory
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

from ...astro.coord import CoordSystem, format_coord
from ...error import NoSuchRecord, UserError
from ...file.moc import read_moc
from ...view import auth
from ...view.tool import BaseTargetTool
from ...view.util import with_verified_admin
from ...web.util import ErrorPage, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from ...type.enum import AttachmentState, FileTypeInfo, FormatType
from ...type.simple import MOCInfo, RouteInfo
from ...type.util import null_tuple

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

    def get_default_facility_code(self):
        """
        Get the code of the facility for which this target tool is
        designed.
        """

        return 'generic'

    def get_custom_routes(self):
        """
        Get list of custom routes used by the clash tool.
        """

        return [
            # Informational routes:
            RouteInfo(
                'moc_view.html',
                'moc/<int:moc_id>',
                'moc_info',
                self.view_moc_info,
                {}),
            RouteInfo(
                None,
                'moc/<int:moc_id>/fits',
                'moc_fits',
                self.view_moc_fits,
                {}),
            RouteInfo(
                'moc_list.html',
                'moc/',
                'moc_list',
                self.view_moc_list,
                {}),

            # Administrative routes:
            RouteInfo(
                'moc_admin.html',
                'admin/',
                'moc_admin',
                self.view_moc_admin,
                {'admin_required': True}),
            RouteInfo(
                'moc_edit.html',
                'admin/new',
                'moc_new',
                self.view_moc_edit,
                {'admin_required': True, 'allow_post': True,
                 'post_files': ['file'], 'extra_params': [None]}),
            RouteInfo(
                'moc_edit.html',
                'admin/<int:moc_id>',
                'moc_edit',
                self.view_moc_edit,
                {'admin_required': True, 'allow_post': True,
                 'post_files': ['file'], 'init_route_params': ['moc_id']}),
            RouteInfo(
                'moc_delete.html',
                'admin/<int:moc_id>/delete',
                'moc_delete',
                self.view_moc_delete,
                {'admin_required': True, 'allow_post': True,
                 'init_route_params': ['moc_id']}),
        ]

    def _view_any_mode(self, db, target_objects, args, form, auth_cache):
        """
        Prepare clash tool template context for all tool modes.

        This performs a MOC search if the `target_objects`
        list is not `None`.
        """

        clashes = None
        non_clashes = None

        public = self._determine_public_constraint(db, auth_cache=auth_cache)
        try:
            moc_ready = self._check_mocs_exist_and_ready(db, public)
        except NoSuchRecord:
            if session.get('is_admin', False):
                # Allow site administrators to view the clash tool when
                # "empty" so that they can set up coverage maps.
                moc_ready = True
            else:
                raise ErrorPage('No coverage maps have been set up yet.')

        if target_objects is not None:
            (clashes, non_clashes) = self._do_moc_search(
                db, target_objects, public=public)

        return {
            'run_button': 'Search',
            'clashes': clashes,
            'non_clashes': non_clashes,
            'moc_ready': moc_ready,
        }

    def _determine_public_constraint(self, db, auth_cache=None):
        """
        Determine the database search constraint we should use on the public
        field.

        The constraint should be that the public flag is true, unless the user
        has access to private mocs.
        """

        public = True

        if auth.for_private_moc(db, self.facility.id_,
                                auth_cache=auth_cache).view:
            public = None

        return public

    def _check_mocs_exist_and_ready(self, db, public):
        """
        Check the status of coverage maps (MOCs) for this facility.

        :return: True if all available MOCs are ready.
        :raise NoSuchRecord: if there are no MOCs available
        """

        mocs = db.search_moc(facility_id=self.facility.id_, public=public)
        if not mocs:
            raise NoSuchRecord('no coverage maps found')

        return all(AttachmentState.is_ready(x.state) for x in mocs.values())

    def _do_moc_search(self, db, targets, public):
        """
        Search the coverage maps (MOCs) for the given list of targets.

        Iterates over the list of targets and converts each to a
        HEALPix cell at the facility's specified (maximum) MOC order.
        Then searches the MOC cell database table to determine whether
        the target clashes or not.

        :param db: database access object
        :param targets: list of targets
        :param public: database MOC search "public" constraint as determined by
                       :meth:`_determine_public_constraint`

        :return: tuple of lists `(clashes, non_clashes)` where each
                 entry is a `TargetClash` tuple
        """

        order = self.facility.get_moc_order()
        clashes = []
        non_clashes = []

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

    def view_moc_list(self, db):
        """
        View handler for MOC listing custom route.
        """

        public = self._determine_public_constraint(db)

        mocs = db.search_moc(facility_id=self.facility.id_, public=public)

        return {
            'title': 'Coverage List',
            'mocs': mocs,
        }

    def view_moc_info(self, db, moc_id):
        """
        View handler for MOC info custom route.
        """

        public = self._determine_public_constraint(db)

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

    def view_moc_fits(self, db, moc_id):
        """
        View handler for MOC FITS download custom route.
        """

        public = self._determine_public_constraint(db)

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
            null_tuple(FileTypeInfo)._replace(mime='application/fits'),
            '{}.fits'.format(re.sub('[^-_a-z0-9]', '_', moc.name.lower())))

    def view_moc_admin(self, db):
        mocs = db.search_moc(facility_id=self.facility.id_, public=None)

        return {
            'title': 'Coverage Management',
            'mocs': mocs,
        }

    @with_verified_admin
    def view_moc_edit(self, db, moc_id, form, file_):
        if moc_id is None:
            # We are uploading a new MOC -- create a blank record.
            moc = null_tuple(MOCInfo)._replace(
                name='', description='', description_format=FormatType.PLAIN,
                public=True)
            title = 'New Coverage Map'
            target = url_for('.tool_clash_moc_new')

        else:
            # We are editing an existing MOC -- fetch its info from
            # the database.
            try:
                moc = db.search_moc(
                    facility_id=self.facility.id_, moc_id=moc_id,
                    public=None, with_description=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Coverage map not found')

            title = 'Edit {}'.format(moc.name)
            target = url_for('.tool_clash_moc_edit', moc_id=moc_id)

        message = None

        if form is not None:
            try:
                moc = moc._replace(
                    name=form['name'],
                    description=form['description'],
                    description_format=int(form['description_format']),
                    public=('public' in form))

                moc_object = None
                if file_:
                    try:
                        moc_object = read_moc(
                            file_=file_,
                            max_order=self.facility.get_moc_order())
                    finally:
                        file_.close()

                elif moc_id is None:
                    raise UserError('No new MOC file was received.')

                if moc_id is None:
                    moc_id = db.add_moc(
                        self.facility.id_, moc.name, moc.description,
                        moc.description_format, moc.public, moc_object)
                    flash('The new coverage map has been stored.')
                else:
                    db.update_moc(
                        moc_id, name=moc.name, description=moc.description,
                        description_format=moc.description_format,
                        public=moc.public, moc_object=moc_object)

                    if moc_object is None:
                        flash('The coverage map details have been updated.')
                    else:
                        flash('The updated coverage map has been stored.')

                raise HTTPRedirect(url_for('.tool_clash_moc_admin'))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'moc': moc,
            'message': message,
            'format_types': FormatType.get_options(is_system=True),
        }

    @with_verified_admin
    def view_moc_delete(self, db, moc_id, form):
        try:
            moc = db.search_moc(facility_id=self.facility.id_, moc_id=moc_id,
                                public=None).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Coverage map not found')

        if form:
            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.tool_clash_moc_admin'))

            elif 'submit_confirm' in form:
                db.delete_moc(self.facility.id_, moc_id)
                flash('The coverage map has been deleted.')
                raise HTTPRedirect(url_for('.tool_clash_moc_admin'))

        return {
            'title': 'Delete Coverage: {}'.format(moc.name),
            'message': 'Are you sure you wish to delete this coverage map?',
        }
