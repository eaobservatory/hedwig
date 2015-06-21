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

from datetime import datetime
import functools

# Import the names we wish to expose.
from flask import session, url_for

# Import the names which we use but do not wish to expose.
from flask import flash as _flask_flash
from flask import make_response as _flask_make_response
from flask import render_template as _flask_render_template
from flask import request as _flask_request
from flask import Response as _FlaskResponse
from werkzeug import exceptions as _werkzeug_exceptions
from werkzeug import routing as _werkzeug_routing

from ..type import FigureType


class HTTPError(_werkzeug_exceptions.InternalServerError):
    """Exception class for raising HTTP errors."""

    pass


class HTTPForbidden(_werkzeug_exceptions.Forbidden):
    """Exception class for HTTP forbidden errors."""

    pass


class HTTPNotFound(_werkzeug_exceptions.NotFound):
    """Exception class for HTTP not found errors."""

    pass


class HTTPRedirect(_werkzeug_routing.RequestRedirect):
    """Exception class requesting a temporary ("See Other") HTTP redirect."""

    code = 303


class ErrorPage(Exception):
    """Exception class where an error page should be shown."""

    def __init__(self, fmt_string, *fmt_args):
        """
        Construct exception, applying string formatting to the
        message similarly to the FormattedError class.
        """

        Exception.__init__(self, fmt_string.format(*fmt_args))


def flash(message, *args):
    """
    Add a message to the list of messages to be flashed on
    the next page viewied.

    The message can include string formatting and the remaining
    arguments taken as arguments for string formatting.
    """

    if args:
        _flask_flash(message.format(*args))
    else:
        _flask_flash(message)


def parse_datetime(name, form):
    """
    Parses date and time fields from the form and returns a combined
    datetime object.

    "name" is the root name of the form parameters -- there should
    be fields <name>_date and <name>_time.
    """

    return datetime.combine(
        datetime.strptime(form[name + '_date'], '%Y-%m-%d').date(),
        datetime.strptime(form[name + '_time'], '%H:%M').time())


def require_admin(f):
    """
    Decorator to require that the user has administrative access.

    Simply checks that the user is logged in and has administrative
    privileges enabled.  Views should double-check that the user is
    still entitled to administrative privileges (e.g. using
    view.auth.can_be_admin).
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' in session and session.get('is_admin', False):
            return f(*args, **kwargs)

        raise HTTPForbidden(
            'You need administrative privileges to view this page.')

    return decorated


def require_auth(require_person=False, require_institution=False,
                 register_user_only=False):
    """
    Decorator to require that the user is authenticated.

    Can optionally require the user to have a profile,
    and to have an institution associated with that profile.

    If "register_user_only" is set, then we want the user to log in or
    create a user account but not to complete a profile before
    proceeding.  This is to support accepting invitation tokens.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in or register for an account to proceed.')

                if register_user_only:
                    session['register_user_for'] = _flask_request.url
                else:
                    session['log_in_for'] = _flask_request.url

                raise HTTPRedirect(url_for('people.log_in'))

            elif ((require_person or require_institution) and
                    'person' not in session):
                flash('Please complete your profile before proceeding.')
                session['log_in_for'] = _flask_request.url
                raise HTTPRedirect(url_for('people.register_person'))

            elif (require_institution and
                    session['person']['institution_id'] is None):
                flash('Please select your institution before proceeding.')
                session['log_in_for'] = _flask_request.url
                raise HTTPRedirect(url_for('people.person_edit_institution',
                                           person_id=session['person']['id']))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_not_auth(f):
    """
    Decorator to require that the user is not authenticated.
    """

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' in session:
            raise ErrorPage('You are already logged in.')
        return f(*args, **kwargs)

    return decorated


def send_file(fixed_type=None):
    """
    Decorator for route functions which send files.

    If there is a fixed MIME type, it can be set in the decorator
    argument and the function just returns the data.  Otherwise
    the function must return a ProposalFigure(data, type, filename) tuple
    where the type is a value from FigureType.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            type_ = fixed_type
            data = f(*args, **kwargs)

            if type_ is None:
                # Function should have returned a tuple: unpack it.
                (data, type_, filename) = data

            return _FlaskResponse(
                data, mimetype=FigureType.get_mime_type(type_))

        return decorated_function

    return decorator


def templated(template):
    """
    Template application decorator.

    Based on the example in the Flask documentation at:
    http://flask.pocoo.org/docs/patterns/viewdecorators/

    The ErrorPage exception is caught, and rendered using
    the error_page_repsonse method.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return _make_response(template, f(*args, **kwargs))

            except ErrorPage as err:
                return _error_page_response(err)

        return decorated_function

    return decorator


def _error_page_response(err):
    """Prepare flask response for an error page."""

    return _make_response('error.html',
                          {'title': 'Error', 'message': err.message})


def _make_response(template, result):
    """Prepare flask repsonse via a template."""

    resp = _flask_make_response(_flask_render_template(template, **result))
    resp.headers['Content-Language'] = 'en'

    return resp
