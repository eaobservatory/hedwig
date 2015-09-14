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
import logging
import os

from ..config import get_config, get_database, get_facilities, get_home
from ..type import Assessment, AttachmentState, FacilityInfo, \
    ProposalState, ReviewerRole
from .util import require_auth, session, templated

from .blueprint.facility import create_facility_blueprint
from .blueprint.help import create_help_blueprint
from .blueprint.people import create_people_blueprint
from .blueprint.query import create_query_blueprint
from .format import format_text

from ..view.home import prepare_home, \
    prepare_person_proposals, prepare_person_reviews, prepare_contact_page


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

    @app.route('/')
    @templated('home.html')
    def home_page():
        return prepare_home(application_name, facilities)

    @app.route('/proposals')
    @require_auth(require_person=True)
    @templated('person_proposals.html')
    def person_proposals():
        return prepare_person_proposals(
            db, session['person']['id'], facilities)

    @app.route('/reviews')
    @require_auth(require_person=True)
    @templated('person_reviews.html')
    def person_reviews():
        return prepare_person_reviews(
            db, session['person']['id'], facilities)

    @app.route('/contact-us')
    @templated('contact.html')
    def contact_page():
        return prepare_contact_page()

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

    @app.template_filter()
    def assessment_name(value):
        if value is None:
            return ''
        return Assessment.get_name(value)

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
    def format_hours_hms(hours):
        (m, s) = divmod(int(3600 * hours), 60)
        (h, m) = divmod(m, 60)
        return '{0:d}:{1:02d}:{2:02d}'.format(h, m, s)

    @app.template_filter()
    def proposal_state_name(value):
        try:
            return ProposalState.get_name(value)
        except KeyError:
            return 'Unknown state'

    @app.template_filter()
    def reviewer_role_name(value):
        try:
            return ReviewerRole.get_info(value).name
        except KeyError:
            return 'Unknown role'

    @app.template_test()
    def attachment_ready(value):
        return AttachmentState.is_ready(value)

    @app.template_test()
    def attachment_error(value):
        return AttachmentState.is_error(value)

    @app.template_test()
    def reviewer_role_external(value):
        return (value == ReviewerRole.EXTERNAL)

    @app.template_test()
    def reviewer_role_review(value):
        return ReviewerRole.get_info(value).name_review

    app.add_template_filter(format_text)

    return app
