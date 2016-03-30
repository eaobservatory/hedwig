# Copyright (C) 2016 East Asian Observatory
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

from flask import Blueprint

from ...view.home import HomeView
from ..util import templated


def create_home_blueprint(db, facilities):
    """
    Create Flask Blueprint for the home and other related pages.
    """

    bp = Blueprint('home', __name__)
    view = HomeView()

    @bp.route('/')
    @templated('home.html')
    def home_page():
        return view.home(facilities)

    @bp.route('/contact-us')
    @templated('contact.html')
    def contact_page():
        return view.contact_page()

    return bp
