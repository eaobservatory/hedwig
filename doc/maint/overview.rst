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

`hedwig.web`
    Contains functions which set up the Flask web application
    and act as a thin wrapper around Flask for use by the
    view functions.

`hedwig.view`
    Define "view" functions which contain the actual logic
    required for the web interface.

The `hedwig.web` Package
~~~~~~~~~~~~~~~~~~~~~~~~

This package includes:

`hedwig.web.app`
    Defines a function `create_web_app` which constructs and
    returns a Flask application object.
    This is used by the WSGI script to create the `application` object,
    and by `hedwigctl` when running a test web server.

    This function defines some basic routes, such as the home page,
    and then registers Flask "blueprints" for other aspects of
    the system.

    It also defines a number of Jinja2 template filters and tests,
    such as `fmt` which applies new-style Python string formatting.

`hedwig.web.util`
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

`hedwig.web.blueprint`
    This package contains a number of modules with functions to create
    Flask "blueprints".  (Blueprints are a mechanism of Flask by which
    a web application can be separated into distinct parts.)

    `hedwig.web.blueprint.people`
        Mentioned here as a typical example,
        this contains a function to make
        a blueprint with routes for handling user accounts, profiles,
        institutions and invitations.

    `hedwig.web.blueprint.facility`
        This contains a blueprint function which is special in that it
        takes a facility "view" class as an argument.
        It then creates routes for the facility-specific parts of the
        system and dynamically constructs routes for the facility's
        calculators and target tools.

The `hedwig.view` Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The modules in the `hedwig.view` package define view functions
which are used to handle the routes defined in the various
blueprints.  (Other than facility-specific routes.)
For example `hedwig.view.people` defines the functions used by the
"people" blueprint.

The package also contains some utility modules:

`hedwig.view.auth`
    Contains methods for determining whether the current user
    is authorized to view and/or edit a given resource.

`hedwig.view.util`
    Contains general utility functions used by the view functions.
    One useful example is the `with_proposal` decorator,
    which checks the user's authorization for a proposal,
    and, if successful, calls the decorated function with a
    `Proposal` and `Authorization` object in place of the route's 
    `proposal_id` number.

Facility-specific View Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The "view" code for facility-specific parts of the application,
such as proposal handing, is located in the `hedwig.facility`
package and arranged in classes.
The "Generic Facility" is both an example, which you can use
to test the system before defining your specific facility class,
and the basis for more specific classes.
In order to make the size of the class more manageable,
the view class "Generic" contains only basic methods,
with the main view methods defined via "mix-in" classes
in the `hedwig.facility.generic` package.

The `hedwig.config.get_facilities` method reads the list of facilities
from the configuration file.
By default each facility is expected to have a `view` module
defining a class with the same name as the facility.

For example, for the JCMT facility:

`hedwig.facility.jcmt.view`
    Defines a view class `JCMT` which inherits from the
    `Generic` facility view class.
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
in the `hedwig.db` module.
This is organized as follows:

`hedwig.db.meta`
    This defines an SQLAlchemy `MetaData` object called `metadata`
    to which the definitions of the database tables are attached.
    The table definitions can also be imported from this module.

`hedwig.db.control`
    Defines a class `Database` with methods providing access to
    the database.
    From the rest of the code base, all database access should be
    performed through this class.
    The `Database` class itself only defines a few private methods
    which are useful for defining other access methods, including:

    `_transaction`
        A context manager for managing database transactions.

    `_sync_records`
        A general purpose method for updating a set of database
        records to match a given set of records.  This is used by
        several record-syncing methods, such as `sync_proposal_target`
        which updates the list of target objects associated with a proposal.

    The actual access methods are defined in "mix-in" classes which
    `Database` inherits, located in the `hedwig.db.part` package.
    A couple of examples are:

    `hedwig.db.part.people.PeoplePart`
        Provides methods for handling the database records of user accounts,
        profiles and institutions.

    `hedwig.db.part.message.MessagePart`
        Provides methods for handling email messages.
        (Hedwig stores writes email messages which it would like to send
        to the database for subsequent sending by a poll task.)

`hedwig.db.engine`
    Provides a function for acquiring an SQLAlchemy database
    `Engine` object.
    (This is normally accessed via the
    `hedwig.config.get_database` function.)

`hedwig.db.type`
    This module is intended to contain custom database column types.
    Presently there is only one such type, `JSONEncoded`,
    which is used to store calculation input and output.

`hedwig.db.util`
    Contains utility functions.

Facility-specific Database Access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `hedwig.config.get_database` function reads the list of
facilities specified in the configuration file.
If there is a `meta` or `control` module in the same directory
which defines the facility class, then it will be imported,
with the assumption that the `control` module will define
a class called `<Facility>Part` where `<Facility>` is the
name of the facility.
It then dynamically creates a new class `CombinedDatabase`
which inherits from the `Database` class described above
and each of the facility database parts.

To give a concrete example, for the JCMT facility:

`hedwig.facility.jcmt.meta`
    Defines a database table `jcmt_request` to represent observing
    requests for the JCMT.

`hedwig.facility.jcmt.control`
    Defines a database "mix-in" `JCMTPart` with methods for accessing
    the observing request table, amongst other things.

Other Notable Modules
---------------------

Other modules which are worth mentioning in this overview are:

`hedwig.error`
    Defines a number of exception classes.
    Many of these inherit from a `FormattedError` class which
    has a constructor that applies new-style Python string formatting
    to its arguments.

`hedwig.type`
    Defines a large number of data types used by Hedwig.
    Some of these are `namedtuple` types and some are custom classes.

    * Many of the `namedtuple` types are defined in terms of the columns
      of a database table (as defined in `hedwig.db.meta`).
      For example the `Person` `namedtuple` contains the columns of the
      `person` database table with a few added attributes.

    * There a some enumeration-type classes, such as `ProposalState`.
      These contain a series of upper case class attributes
      with integer values.  There is often also a table of information
      about the enumeration values and a set of methods for working with them.

    * Finally there is a `ResultCollection` class (which inherits from
      `OrderedDict`) and a few more specific classes which inherit from it.
      These are used by database methods which return multiple results.
      The use of `OrderedDict` as the basis for these classes rather than
      a simple list may not always seem necessary, but at some times
      it can be very useful, such as when trying to "sync" sets of
      database methods.

`hedwig.util`
    Contains general utilities.

    `get_logger` returns a `FormattedLogger` wrapper around the standard
    Python logger to apply new-style string formatting.
