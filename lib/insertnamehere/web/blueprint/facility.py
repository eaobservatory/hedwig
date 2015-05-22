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

from flask import Blueprint, request

from ..util import require_auth, templated


def create_facility_blueprint(db, facility):
    """
    Create Flask blueprint for a facility.
    """

    code = facility.get_code()
    name = facility.get_name()

    bp = Blueprint(code, __name__)

    def facility_template(template):
        """
        Decorator which uses the template from the facility's directory if it
        exists, otherwise the generic template.  It does this by providing a
        list of alternative templates, from which Flask's "render_template"
        method will pick the first which exists.
        """

        def decorator(f):
            return templated((code + '/' + template, 'generic/' + template))(f)
        return decorator

    @bp.route('/')
    @facility_template('facility_home.html')
    def facility_home():
        return facility.view_facility_home(db)

    @bp.context_processor
    def add_to_context():
        return {
            'facility_name': name,
        }

    return bp
