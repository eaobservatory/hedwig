# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015-2022 East Asian Observatory.
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

from itertools import count
import logging
import os

from flask import Flask
from flask import g as flask_g
from jinja2_orderblocks import OrderBlocks

from ..config import get_config, get_database, get_facilities, get_home
from ..type.enum import GroupType, MessageThreadType, SiteGroupType
from .template_util import register_template_utils
from .util import check_current_user , \
    make_enum_converter, register_error_handlers

from .blueprint.admin import create_admin_blueprint
from .blueprint.facility import create_facility_blueprint
from .blueprint.help import create_help_blueprint
from .blueprint.home import create_home_blueprint
from .blueprint.oauth import create_oauth_blueprint
from .blueprint.people import create_people_blueprint
from .blueprint.query import create_query_blueprint

_mem_ctr = count()


def create_web_app(db=None, facility_spec=None, auto_reload_templates=False,
                   without_logger=False, without_auth=False,
                   _test_return_extra=False):
    """
    Function to prepare the Flask web application.

    :param db: database access object to use.  If `None` then one will be
        constructed based on the configuration (and `facility_spec`).
    :param facility_spec: facility specification used to construct the
        facility list (via :func:`hedwig.config.get_config`) and database
        object (if not given, via :func:`hedwig.config.get_database`).
    :param auto_reload_templates: Configure whether Jinja2 should automatically
        reload template files.  (Only applies with Flask 0.11 or later.)
    :param without_logger: if `True`, do not configure the application's
        logger.  (Otherwise it is configured to log to the file specified
        in the configuration file.)
    :param without_auth: if `True`, do not set up the `before_request`
        function to check for log in information.
    :param _test_return_extra: if true, instead of just returning the
        application object, return a dictionary of values useful for
        debugging.  (Currently just returns the output of `locals()`.)
    """

    home = get_home()
    config = get_config()

    if db is None:
        db = get_database(facility_spec=facility_spec)

    # Load facilities as specified in the configuration.
    facilities = get_facilities(db=db, facility_spec=facility_spec)

    # Configure the web application.
    application_name = config.get('application', 'name')

    app = Flask(
        __name__,
        static_folder=os.path.join(home, 'data', 'web', 'static'),
        template_folder=os.path.join(home, 'data', 'web', 'template'),
    )

    app._mem_id = next(_mem_ctr)

    if 'extensions' not in app.jinja_options:
        app.jinja_options['extensions'] = []

    app.jinja_options['extensions'].append(OrderBlocks)

    if not without_logger:
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

    # Configure template reloading.  Note we must do this before we set up
    # custom template filters. (Otherwise we could rely on Flask doing this
    # automatically when we run the application with debog=True.)
    app.config['TEMPLATES_AUTO_RELOAD'] = auto_reload_templates

    # Set up routing converters.
    app.url_map.converters['hedwig_group'] = make_enum_converter(GroupType)
    app.url_map.converters['hedwig_thread'] = \
        make_enum_converter(MessageThreadType)
    app.url_map.converters['hedwig_site_group'] = \
        make_enum_converter(SiteGroupType)

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
    app.register_blueprint(create_help_blueprint(db), url_prefix='/help')
    app.register_blueprint(create_query_blueprint(db), url_prefix='/query')
    app.register_blueprint(create_oauth_blueprint(db, app), url_prefix='/user/oauth')

    # Register blueprints for each facility.
    for facility in facilities.values():
        app.register_blueprint(create_facility_blueprint(db, facility.view),
                               url_prefix='/' + facility.code)

    if not without_auth:
        # Add beginning of request function to check session for user log in.
        @app.before_request
        def _check_current_user():
            check_current_user(db)

    @app.context_processor
    def add_to_context():
        return {
            'application_name': application_name,
            'application_status_notice': config.get('status', 'notice'),
            'current_user': flask_g.current_user,
        }

    register_error_handlers(app)
    register_template_utils(app)

    if _test_return_extra:
        return locals()

    return app
