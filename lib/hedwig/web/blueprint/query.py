# Copyright (C) 2015-2023 East Asian Observatory
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

from ...view.query import QueryView
from ..util import send_file, send_json


def create_query_blueprint(db):
    """
    Create Flask Blueprint for services to be queried by our JavaScript
    code.
    """

    bp = Blueprint('query', __name__)
    view = QueryView()

    @bp.route('/countries')
    @send_file(fixed_type='application/json', allow_cache=True)
    def country_list():
        return view.get_country_list()

    @bp.route('/institutions')
    @send_json(allow_cache=True, cache_max_age=10)
    def institution_list():
        return view.get_institution_list(db)

    @bp.route('/nameresolver')
    @send_file(allow_cache=True, cache_max_age=3600, cache_private=False)
    def name_resolver():
        return view.resolve_name(request.args)

    return bp
