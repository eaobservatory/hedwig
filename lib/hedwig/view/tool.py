# Copyright (C) 2015-2016 East Asian Observatory
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

from ..astro.coord import CoordSystem, parse_coord
from ..astro.catalog import parse_source_list
from ..error import NoSuchRecord, UserError
from ..type.simple import Link, TargetObject
from ..type.enum import PermissionType
from ..web.util import ErrorPage, HTTPForbidden, HTTPNotFound, url_for
from .util import with_proposal
from . import auth

TargetCoord = namedtuple('TargetCoord', ('x', 'y', 'system'))


class BaseTargetTool(object):
    def __init__(self, facility, id_):
        self.facility = facility
        self.id_ = id_

    @classmethod
    def get_code(cls):
        """
        Get the target tool "code".

        This is a short string used to uniquely identify the target tool
        within facilities which use it.  It will be used in URLs and
        would correspond to an entry in a "tool" database table if there
        is ever a need to store target tool results in the database.
        """

        return NotImplementedError()

    def get_name(self):
        """
        Get the target tool's name.
        """

        return NotImplementedError()

    def get_default_facility_code(self):
        """
        Get the code of the facility for which this target tool is
        designed.

        Target tools need only override this method if the tool
        is intended to be used with multiple facilities.

        :return: `None` if the tool is not expected to be used with
                 multiple facilities, or the facility code otherwise
        """

        return None

    def get_custom_routes(self):
        """
        Method used to find any custom routes required by this tool.

        Note that the route information will automatically be prefixed
        as follows:

        * `template`: `<facility code>/tool_<tool code>_`
        * `rule`: `/tool/<tool code>/`
        * `endpoint`: `tool_<tool code>_`

        :return: a list of RouteInfo tuples
        """

        return []

    def view_single(self, db, args, form):
        """
        View handler function for stand-alone usage of a target tool.

        This is a generic implementation of the view for the target tool's
        "single" mode.  It parses coordinates entered by the user
        and calls the `_view_single` method with these coordinates, or
        `None` if no coordinate was available --- e.g. when the form
        is first displayed for input or in the case of a parsing error.
        """

        target = TargetCoord('', '', CoordSystem.ICRS)
        message = None
        target_object = None

        if form is not None:
            target = target._replace(x=form['x'], y=form['y'],
                                     system=int(form['system']))

            try:
                target_name = 'Input coordinates'
                target_object = TargetObject(
                    target_name, target.system,
                    parse_coord(target.system, target.x, target.y,
                                target_name))

            except UserError as e:
                message = e.message

        tool_code = self.get_code()

        ctx = {
            'title': self.get_name(),
            'show_input': True,
            'show_input_upload': False,
            'run_button': 'Check',
            'systems': CoordSystem.get_options(),
            'target': target,
            'message': message,
            'target_url': url_for('.tool_{}'.format(tool_code)),
            'target_upload': url_for('.tool_{}_upload'.format(tool_code)),
        }

        ctx.update(self._view_single(db, target_object, args, form))

        return ctx

    def _view_single(self, db, target_object, args, form):
        """
        Prepare extra template context for target tool in "single" mode.

        Target tool sub-classes should override this method if they need to
        behave differently in different modes --- otherwise they need only
        override `_view_any_mode`.

        :return: template context dictionary
        """

        return self._view_any_mode(
            db, (None if target_object is None else [target_object]),
            args, form)

    def view_upload(self, db, args, form, file_):
        """
        View handler for stand-alone usage by file upload.

        This is a generic implementation of the view for the target tool's
        "upload" mode.  It parses the file uploaded by the user
        and calls the `_view_upload` method with a list of coordinates, or
        `None` if no coordinates were available --- e.g. when the form
        is first displayed for input or in the case of a parsing error.
        """

        message = None
        target_objects = None

        if form is not None:
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

            except UserError as e:
                message = e.message

        tool_code = self.get_code()

        ctx = {
            'title': self.get_name(),
            'show_input': True,
            'show_input_upload': True,
            'run_button': 'Check',
            'mime_types': ['text/plain', 'text/csv'],
            'message': message,
            'target_url': url_for('.tool_{}_upload'.format(tool_code)),
        }

        ctx.update(self._view_upload(db, target_objects, args, form))

        return ctx

    def _view_upload(self, db, target_objects, args, form):
        """
        Prepare extra template context for target tool in "upload" mode.

        Target tool sub-classes should override this method if they need to
        behave differently in different modes --- otherwise they need only
        override `_view_any_mode`.

        :return: template context dictionary
        """

        return self._view_any_mode(db, target_objects, args, form)

    @with_proposal(permission=PermissionType.VIEW, indirect_facility=True)
    def view_proposal(self, db, proposal, can, args):
        """
        View handler function for proposal-based usage of a target tool.

        This is a generic implementation of the view for the target tool's
        "proposal" mode.  It retrieves target coordinates from the given
        proposal and calls the `_view_proposal` method with this list.
        Unlike other target tool modes, in this mode we (currently)
        always perform the target analysis immediately on the HTTP GET request.
        So there is normally no input form stage and `_view_proposal`
        should not be called without a list of targets to process.

        :raises ErrorPage: if the proposal did not have any targets with
                           coordinates
        """

        targets = db.search_target(proposal_id=proposal.id)

        target_objects = targets.to_object_list()

        if not target_objects:
            raise ErrorPage(
                'The proposal does not appear to have any targets '
                'with coordinates.',
                links=[Link('Back to proposal', url_for(
                    '.proposal_view', proposal_id=proposal.id,
                    _anchor='targets'))])

        ctx = {
            'title': self.get_name(),
            'show_input': False,
            'proposal_id': proposal.id,
            'proposal_code': self.facility.make_proposal_code(db, proposal),
        }

        ctx.update(self._view_proposal(db, proposal, target_objects, args))

        return ctx

    def _view_proposal(self, db, proposal, target_objects, args):
        """
        Prepare extra template context for target tool in "proposal" mode.

        Target tool sub-classes should override this method if they need to
        behave differently in different modes --- otherwise they need only
        override `_view_any_mode`.

        :return: template context dictionary
        """

        return self._view_any_mode(db, target_objects, args, None)

    def _view_any_mode(self, db, target_objects, args, form):
        """
        Prepare extra template context for target tool in any mode.

        Target tool sub-classes should override this method
        to implement the analysis routine which the tool is
        intended to perform.

        If the tool needs to behave differently in different modes
        it can override the specific mode protected methods instead.

        :param db: database access object
        :param target_object: list of TargetObject instances
        :param args: HTTP arguments
        :param form: HTTP form or `None` if not a POST request

        :return: template context dictionary
        """

        return NotImplementedError()
