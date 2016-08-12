Software Overview
=================

Hedwig is based around two Python libraries:

* The `SQLAlchemy <http://www.sqlalchemy.org/>`_ Core expression language.

* The `Flask <http://flask.pocoo.org/>`_  web "microframework".

  This is based in turn on:

  * The `Werkzeug <http://werkzeug.pocoo.org/>`_ WSGI library.
  * The `Jinja2 <http://jinja.pocoo.org/>`_ template engine.

However the usage of these libraries has been largely contained to
certain areas of the Hedwig code base.
The intention is to isolate most of the code from the details
of the web and database interfaces,
in case either of these things need to be changed in the future.
The following sections describe the way in which these libraries
are used in Hedwig.

The Web Interface
-----------------

The majority of the Hedwig web interface code is split between
two packages:

:doc:`hedwig.web <api/web>`
    Contains functions which set up the Flask web application
    and act as a thin wrapper around Flask for use by the
    view functions.

:doc:`hedwig.view <api/view>`
    Defines "view" classes which contain the actual logic
    required for the web interface.

The :doc:`hedwig.web <api/web>` Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This package includes:

:mod:`hedwig.web.app`
    Defines a function `create_web_app` which constructs and
    returns a Flask application object.
    This is used by the WSGI script to create the `application` object,
    and by `hedwigctl` when running a test web server.

    This function registers Flask "blueprints" for all aspects of
    web interface.

    It also invokes :func:`hedwig.web.template_util.register_template_utils`
    to define a number of Jinja2 template filters and tests,
    such as `fmt` which applies new-style Python string formatting.

:mod:`hedwig.web.util`
    This module is the place from which other parts of the system
    should import web-based utility functions and classes,
    especially those related to Flask and werkzeug.
    For example it imports `session` and `url_for` from Flask,
    so you can re-import those names from this module.
    It also defines exception classes, several of which
    inherit from a werkzeug exception, e.g.
    `HTTPRedirect` which inherits from `werkzeug.routing.RequestRedirect`
    and sets a "see other" HTTP status code.

    There are various other useful functions in this module such as:

    * `flash` which applies new-style string formatting and calls Flask's
      `flash` function.

    * `require_auth` and `require_admin` for authorization.

    * `templated` which applies Jinja2 templates and traps the
      `ErrorPage` exception.

    * `send_file` for responding with non-HTML content.

:doc:`hedwig.web.blueprint <api/web_blueprint>`
    This package contains a number of modules with functions to create
    Flask "blueprints".  (Blueprints are a mechanism of Flask by which
    a web application can be separated into distinct parts.)

    :mod:`hedwig.web.blueprint.people`
        Mentioned here as a typical example,
        this contains a function to make
        a blueprint with routes for handling user accounts, profiles,
        institutions and invitations.

    :mod:`hedwig.web.blueprint.facility`
        This contains a blueprint function which is special in that it
        takes a facility "view" class as an argument.
        It then creates routes for the facility-specific parts of the
        system and dynamically constructs routes for the facility's
        calculators and target tools.

The :doc:`hedwig.view <api/view>` Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The modules in the :doc:`hedwig.view <api/view>` package define view classes
which are used to handle the routes defined in the various
blueprints.  (Other than facility-specific routes.)
For example :mod:`hedwig.view.people` defines the methods used by the
"people" blueprint.

The package also contains some utility modules:

:mod:`hedwig.view.auth`
    Contains methods for determining whether the current user
    is authorized to view and/or edit a given resource.

:mod:`hedwig.view.util`
    Contains general utility functions used by the view functions.
    One useful example is the
    :func:`~hedwig.view.util.with_proposal` decorator,
    which checks the user's authorization for a proposal,
    and, if successful, calls the decorated function with a
    :class:`~hedwig.type.simple.Proposal` and
    :class:`~hedwig.view.auth.Authorization`
    object in place of the route's
    `proposal_id` number.

.. _facility_view_classes:

Facility-specific View Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The "view" code for facility-specific parts of the application,
such as proposal handing, is located in the `hedwig.facility` package.
The "Generic Facility" is both an example, which you can use
to test the system before defining your specific facility class,
and the basis for more specific classes.
In order to make the size of the class more manageable,
the view class "Generic" contains only basic methods,
with the main view methods defined via "mix-in" classes
in the :doc:`hedwig.facility.generic <api/facility_generic>` package.

The :func:`hedwig.config.get_facilities` function reads the list of facilities
from the configuration file.
By default each facility is expected to have a `view` module
defining a class with the same name as the facility.

For example, for the JCMT facility:

:mod:`hedwig.facility.jcmt.view`
    Defines a view class
    :class:`~hedwig.facility.jcmt.view.JCMT`
    which inherits from the
    :class:`~hedwig.facility.generic.view.Generic`
    facility view class.
    This only defines / overrides specific methods as required
    for JCMT which are different from the Generic Facility.

The Database Interface
----------------------

As mentioned above, Hedwig makes use of SQLAlchemy,
but only the core expression language rather than the
ORM (Object Relational Mapper).
This layer of SQLAlchemy allows us to write database queries in
Python rather than writing the SQL code directly.
The advantage is that SQLAlchemy handles some of the differences between
databases for us, so that we can, for example,
develop and test the system using SQLite
and then use MySQL in a live deployment.

For an introduction to the SQLAlchemy Core,
see the links on the right hand side of the
`SQLAlchemy documentation page <http://docs.sqlalchemy.org/en/latest/>`_.
For reference information, see the
`Core <http://docs.sqlalchemy.org/en/latest/core/index.html>`_
section in the documentation
`Table of Contents <http://docs.sqlalchemy.org/en/latest/contents.html>`_.

The majority of the SQLAlchemy-related code in Hedwig resides
in the :doc:`hedwig.db <api/db>` module.
This is organized as follows:

:mod:`hedwig.db.meta`
    This defines an SQLAlchemy `MetaData` object called `metadata`
    to which the definitions of the database tables are attached.
    The table definitions can also be imported from this module.

:mod:`hedwig.db.control`
    Defines a class :class:`~hedwig.db.control.Database`
    with methods providing access to the database.
    From the rest of the code base, all database access should be
    performed through this class.
    The :class:`~hedwig.db.control.Database`
    class itself only defines a few private methods
    which are useful for defining other access methods, including:

    :meth:`~hedwig.db.control.Database._transaction`
        A context manager for managing database transactions.

    :meth:`~hedwig.db.control.Database._sync_records`
        A general purpose method for updating a set of database
        records to match a given set of records.  This is used by
        several record-syncing methods, such as `sync_proposal_target`
        which updates the list of target objects associated with a proposal.

    The actual access methods are defined in "mix-in" classes which
    :class:`~hedwig.db.control.Database` inherits,
    located in the :doc:`hedwig.db.part <api/db_part>` package.
    A couple of examples are:

    :class:`hedwig.db.part.people.PeoplePart`
        Provides methods for handling the database records of user accounts,
        profiles and institutions.

    :class:`hedwig.db.part.message.MessagePart`
        Provides methods for handling email messages.
        (Hedwig stores writes email messages which it would like to send
        to the database for subsequent sending by a poll task.)

:mod:`hedwig.db.engine`
    Provides a function for acquiring an SQLAlchemy database
    `Engine` object.
    (This is normally accessed via the
    :func:`hedwig.config.get_database` function.)

:mod:`hedwig.db.type`
    This module is intended to contain custom database column types.
    Presently there is only one such type,
    :class:`~hedwig.db.type.JSONEncoded`,
    which is used to store calculation input and output.

:mod:`hedwig.db.util`
    Contains utility functions.

.. _facility_database_access:

Facility-specific Database Access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :func:`hedwig.config.get_database` function reads the list of
facilities specified in the configuration file.
If there is a `meta` or `control` module in the same directory
which defines the facility class, then it will be imported,
with the assumption that the `control` module will define
a class called `<Facility>Part` where `<Facility>` is the
name of the facility.
It then dynamically creates a new class `CombinedDatabase`
which inherits from the :class:`~hedwig.db.control.Database`
class described above
and each of the facility database parts.

To give a concrete example, for the JCMT facility:

:mod:`hedwig.facility.jcmt.meta`
    Defines a database table `jcmt_request` to represent observing
    requests for the JCMT.

:mod:`hedwig.facility.jcmt.control`
    Defines a database "mix-in" :class:`~hedwig.facility.jcmt.control.JCMTPart`
    with methods for accessing
    the observing request table, amongst other things.

Other Notable Modules
---------------------

Other modules which are worth mentioning in this overview are:

:mod:`hedwig.error`
    Defines a number of exception classes.
    Many of these inherit from a :class:`~hedwig.error.FormattedError`
    class which has a constructor that applies
    new-style Python string formatting to its arguments.

:doc:`hedwig.type <api/type>`
    Defines a large number of data types used by Hedwig.
    Some of these are `namedtuple` types and some are custom classes.
    They are divided into separate modules:

    :mod:`hedwig.type.simple`
        Many of the `namedtuple` types are defined in terms of the columns
        of a database table (as defined in :mod:`hedwig.db.meta`).
        For example the :class:`~hedwig.type.simple.Person` `namedtuple`
        contains the columns of the
        `person` database table with a few added attributes.

    :mod:`hedwig.type.enum`
        There are some enumeration-type classes, such as
        :class:`~hedwig.type.enum.ProposalState`.
        These contain a series of upper case class attributes
        with integer values.  There is often also a table of information
        about the enumeration values and a set of methods for working with
        them.

    :mod:`hedwig.type.collection`
        There is a :class:`~hedwig.type.collection.ResultCollection`
        class (which inherits from `OrderedDict`) and a few more specific classes
        which inherit from it.
        These are used by database methods which return multiple results.
        The use of `OrderedDict` as the basis for these classes rather than
        a simple list may not always seem necessary, but at some times
        it can be very useful, such as when trying to "sync" sets of
        database methods.

    :mod:`hedwig.type.base`
        This module defines a number of mix-in classes which are
        used by some of the custom classes.

    :mod:`hedwig.type.misc`
        This module contains additional miscellaneous types.

    :mod:`hedwig.type.util`
        This module contains utility functions for working with the
        Hedwig types.  One very useful function is
        :func:`hedwig.type.util.null_tuple`.  This creates a tuple
        of the given type containing null values.  It should be used
        to generate the custom `namedtuple` instances to avoid errors when
        the number of entries in the tuple changes.  For example::

            person = null_tuple(Person)._replace(name='', public=False)

:mod:`hedwig.util`
    Contains general utilities.

    :func:`~hedwig.util.get_logger` returns a
    :class:`~hedwig.util.FormattedLogger` wrapper around the standard
    Python logger to apply new-style string formatting.
