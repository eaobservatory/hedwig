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
import json
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

from ..type.enum import FigureType, FileTypeInfo


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

    def __init__(self, fmt_string, *fmt_args, **kwargs):
        """
        Construct exception, applying string formatting to the
        message similarly to the FormattedError class.
        """

        Exception.__init__(self, fmt_string.format(*fmt_args))

        self.links = kwargs.get('links', None)


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


def make_enum_converter(enum_class):
    """
    Make a Werkzeug routing converter for a Hedwig enum-style class.

    The given class must have support for URL paths: it should have
    methods `get_url_paths`, `by_url_path` and `url_path`.
    Such a class can be constructed by defining an `url_path` attribute
    and inheriting from the :class:`hedwig.type.base.EnumURLPath` mix-in.
    """

    class EnumTypeConverter(_werkzeug_routing.AnyConverter):
        def __init__(self, map_):
            super(EnumTypeConverter, self).__init__(
                map_, *(enum_class.get_url_paths()))

        def to_python(self, value):
            try:
                return enum_class.by_url_path(value)
            except:
                raise _werkzeug_routing.ValidationError()

        def to_url(self, value):
            try:
                return enum_class.url_path(value)
            except:
                raise _werkzeug_routing.ValidationError()

    return EnumTypeConverter


def mangle_email_address(email_address):
    """
    Mangles an email address by turning it into a JSON-encoded list of
    HTML character entities.

    The `unmangle.js` script can be used to reconstruct such addresses
    when they are placed in the `mangled` data attribute of a span of
    class `mangled_address`, e.g.::

        <span class="mangled_address" data-mangled="{{ email_address }}">&nbsp;</span>
    """

    mangled = []

    for char in email_address:
        mangled.append('&#{};'.format(ord(char)))

    return json.dumps(mangled)


def parse_datetime(name, form):
    """
    Parses date and time fields from the form and returns a combined
    datetime object.

    :param name: the root name of the form parameters -- there should
        be fields `<name>_date` and `<name>_time`.
    :param form: the form to process
    """

    return datetime.combine(
        datetime.strptime(form[name + '_date'], '%Y-%m-%d').date(),
        datetime.strptime(form[name + '_time'], '%H:%M').time())


def register_error_handlers(app):
    """
    Register error handlers with the given Flask app.

    :param app: Flask application with which to register error handlers.
    """

    for error_class in (HTTPError, HTTPForbidden, HTTPNotFound):
        @app.errorhandler(error_class.code)
        def error_handler(error):
            # Flask matches error handlers for HTTP exception classes by
            # code which means it might call our error handler with an
            # exception class which isn't actually one of those we registered.
            # One place this happens is that the handle_exception method
            # uses the handler for code 500 (same as our HTTPError).
            # Flask will already have logged the error, so just replace it
            # with a standard HTTPError.
            if not all((hasattr(error, x) for x in
                        ['name', 'description', 'code'])):
                error = HTTPError()

            return _make_response(
                'error.html',
                {'title': error.name, 'message': error.description},
                status=error.code)


def require_admin(f):
    """
    Decorator to require that the user has administrative access.

    Simply checks that the user is logged in and has administrative
    privileges enabled -- i.e. that the session `is_admin` flag
    is set.  Views should double-check that the user is
    still entitled to administrative privileges (e.g. using
    :func:`hedwig.view.auth.can_be_admin`).
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        _check_session_expiry()

        if 'user_id' in session and session.get('is_admin', False):
            return f(*args, **kwargs)

        raise HTTPForbidden(
            'You need administrative privileges to view this page.')

    return decorated


def require_auth(require_person=False, require_person_admin=False,
                 require_institution=False,
                 register_user_only=False, record_referrer=False):
    """
    Decorator to require that the user is authenticated.

    :param require_person: require the user to have a profile.

    :param require_person_admin: also check that the
        person record in the session has the admin flag.
        (This is not the same as the session `is_admin` flag -- use
        :func:`require_admin` for that.)

    :param require_institution: require the user to have an institution
        associated with thir profile.

    :param register_user_only: used when we want the user to log in or
        create a user account but not to complete a profile before
        proceeding.  This is to support accepting invitation tokens.

    :param record_referrer: if specified then the referrer is added to the
        session as `log_in_referrer` if log in is required.

    .. note::
        This needs to be the outermost route decorator, because under
        certain circumstances (namely requiring the user to authenticate
        from a POST request) it needs to be able to write a response
        directly.

        To help ensure this, it sets an attribute
        `_hedwig_require_auth` on the decorated function which other
        decorators can use to detect the problem.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            _check_session_expiry()

            if not record_referrer:
                session.pop('log_in_referrer', None)

            try:
                if 'user_id' not in session:
                    if _flask_request.method == 'POST':
                        # If someone logged out (in another tab) or their session
                        # expired while they were filling in a form, we should
                        # show a help page.  (Otherwise after logging in they
                        # are redirected back to a blank copy of the form they
                        # were working on.)

                        session['log_in_for'] = url_for('people.log_in_post_done')

                        return _make_response('people/log_in_post.html', {
                            'title': 'Reauthentication Required',
                            'message': None,
                            'without_links': True,
                        })

                    flash('Please log in or register for an account to proceed.')

                    if register_user_only:
                        session['register_user_for'] = _flask_request.url
                    else:
                        session['log_in_for'] = _flask_request.url

                    raise HTTPRedirect(url_for('people.log_in'))

                elif ((require_person or require_person_admin or
                        require_institution) and 'person' not in session):
                    flash('Please complete your profile before proceeding.')
                    session['log_in_for'] = _flask_request.url
                    raise HTTPRedirect(url_for('people.register_person'))

                elif (require_institution and
                        session['person']['institution_id'] is None):
                    flash('Please select your institution before proceeding.')
                    session['log_in_for'] = _flask_request.url
                    raise HTTPRedirect(url_for('people.person_edit_institution',
                                               person_id=session['person']['id']))

            except HTTPRedirect as redirect:
                if record_referrer:
                    session['log_in_referrer'] = _flask_request.referrer

                raise redirect

            if require_person_admin and not session['person']['admin']:
                raise HTTPForbidden('Permission denied.')

            return f(*args, **kwargs)

        decorated_function._hedwig_require_auth = True

        return decorated_function

    return decorator


def require_not_auth(f):
    """
    Decorator to require that the user is not authenticated.

    .. warning::
        `ErrorPage` can not be raised here because this decorator
        is normally applied outside of the "templated" decorator.
    """

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        try:
            if 'user_id' in session:
                raise ErrorPage('You are already logged in.')
        except ErrorPage as err:
            return _error_page_response(err)

        return f(*args, **kwargs)

    return decorated


def send_file(fixed_type=None, allow_cache=False):
    """
    Decorator for route functions which send files.

    If there is a fixed MIME type, it can be set in the decorator
    argument and the function just returns the data.  Otherwise
    the function must return a :class:`~hedwig.type.simple.ProposalFigure`
    `(data, type, filename)` tuple where the type is a value from
    :class:`~hedwig.type.enum.FigureType`.

    :param fixed_type: fixed MIME type, if appropriate (see above).
    :param allow_cache: if enabled, HTTP headers will be added to enable
        caching.  In this case it is assumed that the caller will ensure
        the resource hasn't changed, e.g. by including a checksum in the URL.

    :raises Exception: if applied to a function with an attribute
        `_hedwig_require_auth` because :func:`require_auth` should be
        the outermost decorator.
    """

    def decorator(f):
        if hasattr(f, '_hedwig_require_auth'):
            raise Exception('@send_file applied after @require_auth')

        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            type_ = fixed_type
            data = f(*args, **kwargs)
            filename = None

            if type_ is None:
                # Function should have returned a tuple: unpack it.
                (data, type_, filename) = data

            if isinstance(type_, FileTypeInfo):
                mime_type = type_.mime
                can_view_inline = False
            else:
                mime_type = FigureType.get_mime_type(type_)
                can_view_inline = FigureType.can_view_inline(type_)

            response = _FlaskResponse(data, mimetype=mime_type)

            if filename is not None:
                if can_view_inline:
                    response.headers.add('Content-Disposition', 'inline',
                                         filename=filename)
                else:
                    response.headers.add('Content-Disposition', 'attachment',
                                         filename=filename)

            if allow_cache:
                # Set maximum age to one day to allow the user's browser
                # to cache the file.  However this is assumed to be a part
                # of their proposal, so request no public caching.
                response.cache_control.max_age = 86400
                response.cache_control.private = True

            return response

        return decorated_function

    return decorator


def templated(template):
    """
    Template application decorator.

    Based on the
    `templating decorator <http://flask.pocoo.org/docs/patterns/viewdecorators/#templating-decorator>`_
    example in the Flask documentation.

    The :class:`ErrorPage` exception is caught, and rendered using
    the :func:`_error_page_response` method.

    :raises Exception: if applied to a function with an attribute
        `_hedwig_require_auth` because require_auth should be the outermost
        decorator.
    """

    def decorator(f):
        if hasattr(f, '_hedwig_require_auth'):
            raise Exception('@templated applied after @require_auth')

        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return _make_response(template, f(*args, **kwargs))

            except ErrorPage as err:
                return _error_page_response(err)

        return decorated_function

    return decorator


def _error_page_response(err):
    """
    Prepare flask response for an error page.

    :param err: the :class:`ErrorPage` exception object.
    """

    return _make_response('error.html', {
        'title': 'Error',
        'message': err.message,
        'links': err.links,
    })


def _make_response(template, result, status=None):
    """
    Prepare flask repsonse via a template.

    :param template: the file name of the template to use
    :param result: the template context dictionary
    :param status: the HTTP response status

    :raises HTTPError: if the view function returns `None`.
    """

    if result is None:
        raise HTTPError('View function returned None as result.')

    args = []
    if status is not None:
        args.append(status)

    resp = _flask_make_response(
        _flask_render_template(template, **result), *args)

    resp.headers['Content-Language'] = 'en'

    return resp


def _check_session_expiry():
    """
    Clear the user's session if it has expired.

    This function manages the `date_set` session variable in order to detect
    when the user has been idle for too long.

    * If over 2 hours ago, the session is cleared.
    * If over 10 minutes ago, `date_set` is set to the current time.

    This is invoked by the :func:`require_admin` and :func:`require_auth`
    functions before they examine the session.  `date_set` is originally
    written when the user logs in by the
    :func:`~hedwig.view.people._update_session_user` function.
    """

    date_set = session.get('date_set', None)

    if date_set is None:
        session.clear()
        return

    date_current = datetime.utcnow()

    delta = (date_current - date_set).total_seconds()

    if delta > 7200:
        session.clear()
    elif delta > 600:
        session['date_set'] = date_current
