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
import logging
import os

from ..config import get_config, get_database, get_facilities, get_home
from ..type import FacilityInfo, GroupType, TextRole
from .template_util import register_template_utils
from .util import make_enum_converter

from .blueprint.admin import create_admin_blueprint
from .blueprint.facility import create_facility_blueprint
from .blueprint.help import create_help_blueprint
from .blueprint.home import create_home_blueprint
from .blueprint.people import create_people_blueprint
from .blueprint.query import create_query_blueprint


def create_web_app(db=None):
    """
    Function to prepare the Flask web application.
    """

    home = get_home()
    config = get_config()

    if db is None:
        db = get_database()

    facilities = OrderedDict()

    application_name = config.get('application', 'name')

    app = Flask(
        __name__,
        static_folder=os.path.join(home, 'data', 'web', 'static'),
        template_folder=os.path.join(home, 'data', 'web', 'template'),
    )

    log_file = config.get('application', 'log_file')
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(logging.Formatter(
            fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'))
        app.logger.addHandler(file_handler)

    # Determine maximum upload size: check all upload limits from the
    # configuration file.
    max_upload_size = max(
        int(upload_val) for (upload_key, upload_val) in config.items('upload')
        if upload_key.startswith('max_') and upload_key.endswith('_size'))
    app.config['MAX_CONTENT_LENGTH'] = max_upload_size * 1024 * 1024

    # Try to read the secret key from the configuration file, but if
    # there isn't one, generate a temporary key.
    secret_key = config.get('application', 'secret_key')
    if not secret_key:
        app.logger.warning('Generating temporary secret key')
        secret_key = os.urandom(32)
    app.secret_key = secret_key

    # Set up routing converters.
    app.url_map.converters['hedwig_group'] = make_enum_converter(GroupType)
    app.url_map.converters['hedwig_text'] = make_enum_converter(TextRole)

    app.register_blueprint(create_home_blueprint(db, facilities))
    app.register_blueprint(create_admin_blueprint(db, facilities),
                           url_prefix='/admin')
    app.register_blueprint(create_people_blueprint(db, facilities))
    app.register_blueprint(create_help_blueprint(), url_prefix='/help')
    app.register_blueprint(create_query_blueprint(db), url_prefix='/query')

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

    register_template_utils(app)

    return app
