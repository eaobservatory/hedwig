# Copyright (C) 2015-2024 East Asian Observatory
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

from collections import namedtuple, OrderedDict
from itertools import chain
from math import sqrt, pi
import re

from pymoc.util.catalog import catalog_to_cells

from ...astro.coord import CoordSystem, concatenate_coord_objects
from ...error import NoSuchRecord, UserError
from ...file.moc import read_moc
from ...view import auth
from ...view.tool import BaseTargetTool
from ...web.util import ErrorPage, HTTPNotFound, HTTPRedirect, \
    flash, url_for
from ...type.enum import AttachmentState, FormatType
from ...type.simple import MOCInfo, RouteInfo
from ...type.util import null_tuple
from ...util import item_combinations

TargetClash = namedtuple('TargetClash', ('target', 'mocs', 'target_links'))


class ClashTool(BaseTargetTool):
    # This tool always shows a search radius form with message display,
    # so we need not raise proposal messages as errors.
    proposal_message_error = False

    def __init__(self, *args, **kwargs):
        """
        Construct ClashTool instance.

        This routine gets the facility's configured MOC order and uses it
        to determine a suitable range of search radii.  For example
        with MOC order 12 (51" cells) the following table shows typical
        numbers of cells searched for different radii:

        ===== ========== ===============
        Radius           Search
        ---------------- ---------------
        Cells Arcseconds Number of cells
        ===== ========== ===============
        0.5   30         ~ 4
        3.5   180        ~ 50
        35    1800       ~ 4000
        70    3600       ~ 16000
        ===== ========== ===============
        """

        super(ClashTool, self).__init__(*args, **kwargs)

        # Prepare MOC order information.
        self.order = self.facility.get_moc_order()

        cell_size = 3600 * sqrt(10800.0 / pi) / (2 ** self.order)

        radius_min = cell_size * 0.5
        radius_max = cell_size * 35.0

        cell_scales = (1, 3, 15, 30)
        self.radius_options = [
            r for r in chain(
                cell_scales,
                (x * 60 for x in cell_scales),
                (x * 3600 for x in cell_scales))
            if radius_min <= r <= radius_max]

        if not self.radius_options:
            raise Exception('could not find any valid clash tool search radii')

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

    def _view_any_mode(
            self, current_user, db, target_objects,
            extra_info, args, form, auth_cache):
        """
        Prepare clash tool template context for all tool modes.

        This performs a MOC search if the `target_objects`
        list is not `None`.
        """

        clashes = None
        non_clashes = None
        message = None

        public = self._determine_public_constraint(
            current_user, db, auth_cache=auth_cache)

        mocs = db.search_moc(facility_id=self.facility.id_, public=public)

        if mocs:
            unready_states = AttachmentState.unready_states(
                include_discard=False)

            moc_ready = all(
                x.state not in unready_states for x in mocs.values())

        elif current_user.is_admin:
            # Allow site administrators to view the clash tool when
            # "empty" so that they can set up coverage maps.
            moc_ready = True

        else:
            raise ErrorPage('No coverage maps have been set up yet.')

        try:
            (radius,) = extra_info

            if radius < self.radius_options[0]:
                radius = 0
            elif radius > self.radius_options[-1]:
                raise UserError("Search radius is too large.")

            if target_objects is not None:
                (clashes, non_clashes) = self._do_moc_search(
                    db, target_objects, public=public, radius=float(radius))

        except UserError as e:
            message = e.message

        return {
            'run_button': 'Search',
            'clashes': clashes,
            'non_clashes': non_clashes,
            'moc_ready': moc_ready,
            'radius': radius,
            'radius_options': self.radius_options,
            'message': message,
        }

    def _view_extra_info(self, args, form):
        """
        Read clash tool-specific information from the query arguments or form.
        """

        radius = self.radius_options[0]

        # Read the radius from the form if provided (single target and
        # upload modes) or check the arguments otherwise (proposal mode).
        if form is not None:
            radius = int(form['radius'])

        elif 'radius' in args:
            radius = int(args['radius'])

        return [radius]

    def _determine_public_constraint(self, current_user, db, auth_cache=None):
        """
        Determine the database search constraint we should use on the public
        field.

        The constraint should be that the public flag is true, unless the user
        has access to private mocs.
        """

        public = True

        if auth.for_private_moc(
                current_user, db, self.facility.id_,
                auth_cache=auth_cache).view:
            public = None

        return public

    def _do_moc_search(self, db, targets, public, radius):
        """
        Search the coverage maps (MOCs) for the given list of targets.

        Iterates over the list of targets and converts each to a
        set of HEALPix cells at the facility's specified MOC order.
        Then searches the MOC cell database table to determine whether
        the target clashes or not.

        :param db: database access object
        :param targets: list of targets
        :param public: database MOC search "public" constraint as determined by
                       :meth:`_determine_public_constraint`
        :param radius: search radius (arcseconds)

        :return: tuple of lists `(clashes, non_clashes)` where each
                 entry is a `TargetClash` tuple
        """

        clashes = []
        non_clashes = []

        for target in targets:
            # If the coordinates weren't entered in ICRS, use the
            # Astropy transformation to convert them.
            if target.system == CoordSystem.ICRS:
                coord = target.coord
            else:
                coord = target.coord.icrs

            cells = catalog_to_cells(
                coord, radius=radius, order=self.order, inclusive=True)

            # Double check we didn't get a huge number of cells (would
            # generate a very large SQL query but this shouldn't happen
            # because of the constraint on radius).
            if len(cells) > 20000:
                raise ErrorPage(
                    'The search radius contains an excessive number '
                    'of HEALPix cells.')

            target_clashes = db.search_moc_cell(
                facility_id=self.facility.id_, public=public,
                order=self.order, cell=cells)

            archive_links = self.facility.make_archive_search_urls(
                coord, public=public)

            if target_clashes:
                clashes.append(TargetClash(
                    target, target_clashes, archive_links))

            else:
                non_clashes.append(TargetClash(
                    target, None, archive_links))

        return (clashes, non_clashes)

    def view_moc_list(self, current_user, db):
        """
        View handler for MOC listing custom route.
        """

        if current_user.is_admin:
            can_edit = True
            public = None
        else:
            can_edit = False
            public = self._determine_public_constraint(current_user, db)

        mocs = db.search_moc(facility_id=self.facility.id_, public=public)

        return {
            'title': 'Coverage List',
            'mocs': mocs,
            'can_edit': can_edit,
        }

    def view_moc_info(self, current_user, db, moc_id):
        """
        View handler for MOC info custom route.
        """

        public = self._determine_public_constraint(current_user, db)

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

    def view_moc_fits(self, current_user, db, moc_id):
        """
        View handler for MOC FITS download custom route.
        """

        public = self._determine_public_constraint(current_user, db)

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
            'application/fits',
            '{}.fits'.format(re.sub('[^-_a-z0-9]', '_', moc.name.lower())))

    def view_moc_edit(self, current_user, db, moc_id, form, file_):
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
                            file_=file_, max_order=self.order)
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

                raise HTTPRedirect(url_for('.tool_clash_moc_list'))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'moc': moc,
            'message': message,
            'format_types': FormatType.get_options(is_system=True),
        }

    def view_moc_delete(self, current_user, db, moc_id, form):
        try:
            moc = db.search_moc(facility_id=self.facility.id_, moc_id=moc_id,
                                public=None).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Coverage map not found')

        if form:
            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.tool_clash_moc_list'))

            elif 'submit_confirm' in form:
                db.delete_moc(self.facility.id_, moc_id)
                flash('The coverage map has been deleted.')
                raise HTTPRedirect(url_for('.tool_clash_moc_list'))

        return {
            'title': 'Delete Coverage: {}'.format(moc.name),
            'message': 'Are you sure you wish to delete this coverage map?',
        }

    def search_between_proposals(
            self, current_user, db, proposals, args, form):
        message = None
        result = None
        proposals_clash = None

        extra_info = self._view_extra_info(args, form)
        (radius,) = extra_info

        def all_cells(proposal):
            object_list = proposal.targets.to_object_list()
            if not object_list:
                return set()

            return catalog_to_cells(
                concatenate_coord_objects(object_list),
                radius=radius, order=self.order,
                inclusive=True)

        if proposals is not None:
            result = item_combinations(
                proposals,
                all_cells,
                (lambda x, y: not x.isdisjoint(y)),
                filter_combination=(lambda x: x))

            proposal_ids = set(chain(*result.keys()))
            proposals_clash = proposals.map_values(
                filter_key=lambda x: x in proposal_ids)

        return {
            'radius': radius,
            'radius_options': self.radius_options,
            'run_button': 'Search',
            'message': message,
            'clashes': result,
            'proposals': proposals_clash,
        }

    def search_proposal_pair(
            self, current_user, db, proposals, args):
        message = None

        extra_info = self._view_extra_info(args, None)
        (radius,) = extra_info

        proposal_list = []
        proposal_targets = []
        proposal_cells = []
        for proposal in proposals.values():
            targets = OrderedDict()
            cells = {}
            proposal_list.append(proposal)
            proposal_targets.append(targets)
            proposal_cells.append(cells)

            for id_, target in enumerate(proposal.targets.to_object_list()):
                targets[id_] = target
                cells[id_] = catalog_to_cells(
                    target.coord, radius=radius, order=self.order,
                    inclusive=True)

        clashes = {}
        for (target_a, cells_a) in proposal_cells[0].items():
            for (target_b, cells_b) in proposal_cells[1].items():
                if not cells_a.isdisjoint(cells_b):
                    clashes[(target_a, target_b)] = True

        targets_clash = []
        for i in (0, 1):
            ids = set((x[i] for x in clashes.keys()))

            targets_clash.append(OrderedDict((
                (id_, x) for (id_, x) in proposal_targets[i].items()
                if id_ in ids)))

        return {
            'radius': radius,
            'radius_options': self.radius_options,
            'run_button': 'Search',
            'message': message,
            'clashes': clashes,
            'proposal_a': proposal_list[0],
            'proposal_b': proposal_list[1],
            'targets_a': targets_clash[0],
            'targets_b': targets_clash[1],
        }
