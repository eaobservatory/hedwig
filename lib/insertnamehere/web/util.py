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

import functools

from flask import flash, session, url_for
from flask import make_response as _flask_make_response
from flask import render_template as _flask_render_template
import werkzeug.exceptions
import werkzeug.routing


class HTTPError(werkzeug.exceptions.InternalServerError):
    """Exception class for raising HTTP errors."""

    pass


class HTTPForbidden(werkzeug.exceptions.Forbidden):
    """Exception class for HTTP forbidden errors."""

    pass


class HTTPNotFound(werkzeug.exceptions.NotFound):
    """Exception class for HTTP not found errors."""

    pass


class HTTPRedirect(werkzeug.routing.RequestRedirect):
    """Exception class requesting a temporary ("See Other") HTTP redirect."""

    code = 303


class ErrorPage(Exception):
    """Exception class where an error page should be shown."""

    pass


def require_auth(f):
    """
    Decorator to require that the user is authenticated.
    """

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in or register for an account to proceed.')
            raise HTTPRedirect(url_for('people.login'))
        return f(*args, **kwargs)

    return decorated


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
