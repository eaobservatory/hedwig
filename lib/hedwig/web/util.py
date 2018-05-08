# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015-2017 East Asian Observatory.
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
from werkzeug import urls as _werkzeug_urls

from ..compat import ExceptionWithMessage, string_type
from ..error import UserError
from ..type.simple import DateAndTime
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


class ErrorPage(ExceptionWithMessage):
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

        <span class="mangled_address" data-mangled="{{ email_address | mangle_email_address }}">&nbsp;</span>
    """

    mangled = []

    for char in email_address:
        mangled.append('&#{};'.format(ord(char)))

    return json.dumps(mangled)


def parse_datetime(date_and_time):
    """
    Parses date and time strings as received from a form.

    The intention is that this function is used in conjunction with
    :func:`format_datetime` to pass datetimes to and from forms.
    The values from a form (which will be strings) are read into
    a `DateAndTime` tuple.  This tuple can be returned to the form
    (in the event of parsing errors) to allow the user to make corrections.
    Otherwise it is parsed by this function to obtain a `datetime` object.
    For the reverse process --- populating an edit form with existing
    data --- :func:`format_datetime` is used to convert a `datetime` object
    to a `DateAndTime` tuple which the form template can use for
    default values.

    :param date_time_pair: a `DateAndTime` tuple of strings.

    :return: combined `datetime` object.

    :raises UserError: if the date or time can not be parsed.
    """

    try:
        return datetime.combine(
            datetime.strptime(date_and_time.date, '%Y-%m-%d').date(),
            datetime.strptime(date_and_time.time, '%H:%M').time())

    except ValueError:
        raise UserError('Could not parse date and time {} {}.',
                        date_and_time.date, date_and_time.time)


def format_datetime(value):
    """
    Converts datetime object to date and time string pair.

    If the object is `None`, returns a pair of empty strings.

    Please see :func:`parse_datetime` for a description of the
    intended usage of this function.

    :param value: `datetime` object.

    :return: a `DateAndTime` tuple containing formatted strings.
    """

    if value is None:
        return DateAndTime('', '')

    return DateAndTime(value.strftime('%Y-%m-%d'), value.strftime('%H:%M'))


def register_error_handlers(app):
    """
    Register error handlers with the given Flask app.

    :param app: Flask application with which to register error handlers.
    """

    for error_class in (HTTPError, HTTPForbidden, HTTPNotFound,
                        _werkzeug_exceptions.BadRequest):
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

    :param record_referrer: if specified then the referrer is passed
        to the log in page as an argument if log in is required.

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
            redirect_kwargs = {}
            request_url = _flask_request.url
            if request_url is not None:
                redirect_kwargs['log_in_for'] = url_relative(request_url)
            if register_user_only:
                redirect_kwargs['register_only'] = 1
            if record_referrer:
                request_referrer = _flask_request.referrer
                if request_referrer is not None:
                    redirect_kwargs['log_in_referrer'] = url_relative(
                        request_referrer)

            if 'user_id' not in session:
                if _flask_request.method == 'POST':
                    # If someone logged out (in another tab) or their
                    # session expired while they were filling in a form,
                    # we should show a help page.
                    # (Otherwise after logging in they are redirected
                    # back to a blank copy of the form they were
                    # working on.)

                    return _make_response('people/log_in_post.html', {
                        'title': 'Reauthentication Required',
                        'message': None,
                        'log_in_for': url_for('people.log_in_post_done'),
                        'log_in_referrer': None,
                        'register_only': False,
                    })

                flash('Please log in or register for an account to proceed.')

                raise HTTPRedirect(url_for(
                    'people.log_in', **redirect_kwargs))

            elif ((require_person or require_person_admin or
                    require_institution) and 'person' not in session):
                flash('Please complete your profile before proceeding.')
                raise HTTPRedirect(url_for(
                    'people.register_person', **redirect_kwargs))

            elif (require_institution and
                    session['person']['institution_id'] is None):
                flash('Please select your institution before proceeding.')
                raise HTTPRedirect(url_for(
                    'people.person_edit_institution',
                    person_id=session['person']['id'], **redirect_kwargs))

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
            can_view_inline = False

            if type_ is None:
                # Function should have returned a tuple: unpack it.
                (data, type_, filename) = data

            if isinstance(type_, FileTypeInfo):
                mime_type = type_.mime
            elif isinstance(type_, string_type):
                mime_type = type_
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


def check_session_expiry():
    """
    Clear the user's session if it has expired.

    This function manages the `date_set` session variable in order to detect
    when the user has been idle for too long.

    * If over 2 hours ago, the session is cleared.
    * If over 10 minutes ago, `date_set` is set to the current time.

    This is invoked at the start of each request, as it is registered
    with Flask as a `before_request` function by the
    :func:`~hedwig.web.app.create_web_app` function.
    It should run before the :func:`require_admin` and :func:`require_auth`
    functions examine the session.  `date_set` is originally
    written when the user logs in by the
    :func:`~hedwig.view.people._update_session_user` function.
    """

    date_set = session.get('date_set', None)

    if date_set is not None:
        date_current = datetime.utcnow()

        delta = (date_current - date_set).total_seconds()

        if delta < 7200:
            if delta > 600:
                session['date_set'] = date_current

            return

    # Save flashed messages so that we can restore them after clearing the
    # session.  (Otherwise the logged out message never displays because
    # logging out clears the whole session, including date_set.  We can't
    # use `get_flashed_messages` as Flask will then store them in the
    # request context not not clear them when they are displayed.)
    messages = session.get('_flashes', None)

    session.clear()

    if messages is not None:
        session['_flashes'] = messages


def _url_manipulation(f):
    """
    Decorator to assist in URL manipulation.

    The URL is "parsed" by `_werkzeug_urls.parse_url` before being
    passed to the decorated function and the return value is then
    reconstructed by `_werkzeug_urls.unparse_url` afterwards.
    """

    @functools.wraps(f)
    def decorated(url, *args, **kwargs):
        return _werkzeug_urls.url_unparse(
            f(_werkzeug_urls.url_parse(url), *args, **kwargs))

    return decorated


@_url_manipulation
def url_add_args(url, **kwargs):
    """
    Add keyword arguments to the given URL as query parameters.
    """

    query = url.decode_query()

    query.update(kwargs)

    return url.replace(query=_werkzeug_urls.url_encode(query, sort=True))


@_url_manipulation
def url_relative(url):
    """
    Convert an URL to relative form, by removing the scheme and location.
    """

    return url.replace(scheme='', netloc='')
