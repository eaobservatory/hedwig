# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015-2016 East Asian Observatory.
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
import logging
import os

from flask import Flask
from jinja2_orderblocks import OrderBlocks

from ..config import get_config, get_database, get_facilities, get_home
from ..type.enum import GroupType, MessageThreadType
from ..type.simple import FacilityInfo
from .template_util import register_template_utils
from .util import make_enum_converter, register_error_handlers

from .blueprint.admin import create_admin_blueprint
from .blueprint.facility import create_facility_blueprint
from .blueprint.help import create_help_blueprint
from .blueprint.home import create_home_blueprint
from .blueprint.people import create_people_blueprint
from .blueprint.query import create_query_blueprint


def create_web_app(db=None, facility_spec=None, _test_return_extra=False):
    """
    Function to prepare the Flask web application.

    :param db: database access object to use.  If `None` then one will be
        constructed based on the configuration (and `facility_spec`).
    :param facility_spec: facility specification used to construct the
        facility list (via :func:`hedwig.config.get_config`) and database
        object (if not given, via :func:`hedwig.config.get_database`).
    :param _test_return_extra: if true, instead of just returning the
        application object, return a dictionary of values useful for
        debugging.  (Currently just returns the output of `locals()`.)
    """

    home = get_home()
    config = get_config()

    if db is None:
        db = get_database(facility_spec=facility_spec)

    # Load facilities as specified in the configuration.
    facilities = OrderedDict()

    for facility_class in get_facilities(facility_spec=facility_spec):
        # Create facility object.
        facility_code = facility_class.get_code()
        facility_id = db.ensure_facility(facility_code)
        facility = facility_class(facility_id)

        # Store in our facilities list.
        facilities[facility_id] = FacilityInfo(
            facility_id, facility_code, facility.get_name(), facility)

    # Configure the web application.
    application_name = config.get('application', 'name')

    app = Flask(
        __name__,
        static_folder=os.path.join(home, 'data', 'web', 'static'),
        template_folder=os.path.join(home, 'data', 'web', 'template'),
    )

    app.jinja_options['extensions'].append(OrderBlocks)

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
    app.url_map.converters['hedwig_thread'] = \
        make_enum_converter(MessageThreadType)

    for facility in facilities.values():
        app.url_map.converters['hedwig_call_type_{}'.format(facility.code)] = \
            make_enum_converter(facility.view.get_call_types())

        app.url_map.converters['hedwig_review_{}'.format(facility.code)] = \
            make_enum_converter(facility.view.get_reviewer_roles())

        app.url_map.converters['hedwig_text_{}'.format(facility.code)] = \
            make_enum_converter(facility.view.get_text_roles())

        for filter_ in facility.view.get_custom_filters():
            app.add_template_filter(
                filter_, '{}_{}'.format(facility.code, filter_.__name__))

    app.register_blueprint(create_home_blueprint(db, facilities))
    app.register_blueprint(create_admin_blueprint(db, facilities),
                           url_prefix='/admin')
    app.register_blueprint(create_people_blueprint(db, facilities))
    app.register_blueprint(create_help_blueprint(), url_prefix='/help')
    app.register_blueprint(create_query_blueprint(db), url_prefix='/query')

    # Register blueprints for each facility.
    for facility in facilities.values():
        app.register_blueprint(create_facility_blueprint(db, facility.view),
                               url_prefix='/' + facility.code)

    @app.context_processor
    def add_to_context():
        return {
            'application_name': application_name,
        }

    register_error_handlers(app)
    register_template_utils(app)

    if _test_return_extra:
        return locals()

    return app
