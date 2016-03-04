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
from ..util import require_auth, session, templated


def create_home_blueprint(db, facilities):
    bp = Blueprint('home', __name__)
    view = HomeView()

    @bp.route('/')
    @templated('home.html')
    def home_page():
        return view.home(facilities)

    @bp.route('/proposals')
    @require_auth(require_person=True)
    @templated('person_proposals.html')
    def person_proposals():
        return view.person_proposals(
            db, session['person']['id'], facilities)

    @bp.route('/reviews')
    @require_auth(require_person=True)
    @templated('person_reviews.html')
    def person_reviews():
        return view.person_reviews(
            db, session['person']['id'], facilities)

    @bp.route('/contact-us')
    @templated('contact.html')
    def contact_page():
        return view.contact_page()

    return bp
