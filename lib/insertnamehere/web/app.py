# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015 East Asian Observatory.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import OrderedDict
from flask import Flask
from jinja2.runtime import Undefined
import os

from ..config import get_config, get_database, get_facilities, get_home
from ..type import FacilityInfo, ProposalAttachmentState, ProposalState
from .util import require_auth, session, templated

from .blueprint.facility import create_facility_blueprint
from .blueprint.people import create_people_blueprint
from .format import format_text

from ..view.home import prepare_dashboard, prepare_home


def create_web_app():
    """
    Function to prepare the Flask web application.
    """

    home = get_home()
    config = get_config()
    db = get_database()
    facilities = OrderedDict()

    application_name = config.get('application', 'name')

    app = Flask(
        __name__,
        static_folder=os.path.join(home, 'data', 'web', 'static'),
        template_folder=os.path.join(home, 'data', 'web', 'template'),
    )

    # Try to read the secret key from the configuration file, but if
    # there isn't one, generate a temporary key.
    secret_key = config.get('application', 'secret_key')
    if not secret_key:
        # TODO: issue warning: generating temporary secret key
        secret_key = os.urandom(32)
    app.secret_key = secret_key

    @app.route('/')
    @templated('home.html')
    def home_page():
        return prepare_home(application_name, facilities)

    @app.route('/dashboard')
    @require_auth(require_person=True)
    @templated('dashboard.html')
    def dashboard():
        return prepare_dashboard(db, session['person']['id'], facilities)

    app.register_blueprint(create_people_blueprint(db))

    # Register blueprints for each facility.
    for facility_class in get_facilities():
        # Create facility object.
        facility_code = facility_class.get_code()
        facility_id = db.ensure_facility(facility_code)
        facility = facility_class(facility_id)

        # Store in our facilities list.
        facilities[facility_id] = FacilityInfo(
            facility_id, facility_code, facility.get_name(), facility)

        # Register blueprint for the facility.
        app.register_blueprint(create_facility_blueprint(db, facility),
                               url_prefix='/' + facility_code)

    @app.context_processor
    def add_to_context():
        return {
            'application_name': application_name,
        }

    @app.template_filter()
    def fmt(value, format_):
        """
        Similar to the Jinja built in filter "format" but the other way
        round and using new-style formatting.
        """

        if value is None or isinstance(value, Undefined):
            return ''
        return format_.format(value)

    @app.template_filter()
    def format_date(value):
        if value is None:
            return ''
        return value.strftime('%Y-%m-%d')

    @app.template_filter()
    def format_time(value):
        if value is None:
            return ''
        return value.strftime('%H:%M')

    @app.template_filter()
    def format_datetime(value):
        if value is None:
            return ''
        return value.strftime('%Y-%m-%d %H:%M')

    @app.template_filter()
    def proposal_state_name(value):
        try:
            return ProposalState.get_name(value)
        except KeyError:
            return 'Unknown state'

    @app.template_test()
    def attachment_ready(value):
        return ProposalAttachmentState.is_ready(value)

    @app.template_test()
    def attachment_error(value):
        return ProposalAttachmentState.is_error(value)

    app.add_template_filter(format_text)

    return app
