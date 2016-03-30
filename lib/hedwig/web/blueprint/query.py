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

from flask import Blueprint, Response, request
import requests

from ..util import HTTPError


def create_query_blueprint(db):
    """
    Create Flask Blueprint for services to be queried by our JavaScript
    code.
    """

    bp = Blueprint('query', __name__)

    @bp.route('/nameresolver')
    def name_resolver():
        """
        Simple proxy for the CADC name resolver service.

        Ideally CADC's service would support HTTPS and CORS so that our
        JavaScript code could access it directly.
        """

        cadc_name_resolver = \
            'http://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/NameResolver/find'

        try:
            r = requests.get(cadc_name_resolver, params=request.args,
                             timeout=15)

            r.raise_for_status()

            return Response(r.content, mimetype=r.headers['Content-Type'])

        except requests.exceptions.RequestException:
            raise HTTPError('Failed to resolve name via CADC.')

    return bp
