Customizing Hedwig for a New Facility
=====================================

Hedwig is designed to be easily customizable for different facilities,
via the use of facility-specific view classes, database methods and
display templates.

Before starting this guide, you might like first to read the :doc:`overview`,
especially the sections on :ref:`facility_view_classes` and
:ref:`facility_database_access` if you have not already done so.

While reading this guide, you might also find it useful to take a look
at existing facility-specific code, such as that for JCMT, which you can
find in the `lib/hedwig/facility/jcmt/` directory.

A Minimal Example View Class
----------------------------

The first step in customizing Hedwig for a new facility is to define
a new facility view class.
In this example it is assumed that you can place your new facility
code within the `hedwig` namespace.
You can create a minimal example as follows:

#.  Create a new sub-directory inside `lib/hedwig/facility/` to contain
    code related to your facility.  The name of the directory should be
    in lower case and there should be an empty `__init__.py`
    file inside allow Python to load modules from it (with Python 2).

    An example is included with Hedwig as `lib/hedwig/facility/example/`.

#.  Create a Python module `view.py` inside your new facility directory
    which defines a class.  The class should have the same name as your
    directory but is not limited to lower case.  In the case of the
    example, we define a class :class:`~hedwig.facility.example.view.Example`.

    The class inherits from Hedwig's base
    :class:`~hedwig.facility.generic.view.Generic` facility class
    and we override the
    :meth:`~hedwig.facility.example.view.Example.get_code` and
    :meth:`~hedwig.facility.example.view.Example.get_name` methods.
    These are class methods because we need to be able to call them
    before constructing an instance of the class.

    The facility code is a short, unique, normally lower case, name used to
    identify your facility.  It is also used in file names and URLs.

    .. literalinclude:: /../lib/hedwig/facility/example/view.py
        :lines: 18-

#.  Add the name of your facility class to your `etc/hedwig.ini` configuration
    file.

    .. code-block:: ini

        [application]
        facilities=Generic,Example

    (If you do not already have a configuration file, please see the
    :ref:`installation_configuration` section of the :doc:`install` guide.)

#.  *Optional:* Create a thumbnail image (picture or icon) to represent
    your new facility on the home page.

    The image should be placed in the `data/web/static/image/` directory
    and be named `facility_<code>.jpeg`, where `<code>` is the short name
    returned by your view class's `get_code` method.

#.  Launch a copy of Hedwig as described in the
    :ref:`installation_test_server` section of the :doc:`install` guide.
    If you have not already done so, you will need to set up a database
    as described in the :ref:`installation_database` section.

    You should see your new facility on the home page.
    It will act like the standard Generic Facility until further customized.

Adding Custom Database Features
-------------------------------

Each facility is likely to require some custom database tables
and associated interface methods.
An example is the table required to store the observing request
for each proposal -- this is not included in the generic
code as it is expected to be quite different at different facilities.

Hedwig uses the SQLAlchemy core expression language library for database
access.  If you are not familiar with this library,
you might like to check out the
`SQLAlchemy expression language tutorial <http://docs.sqlalchemy.org/en/rel_1_0/core/tutorial.html>`_
before proceeding.

#.  Create a file `meta.py` in your facility directory.
    This file should declare any database tables which your facility needs.

    You should import the SQLAlchemy `Metadata` container `metadata`
    and table options `_table_opts` from the
    :mod:`hedwig.db.meta` module and use them in each table defined.

    In the example below we declare one new database table, `example_request`.
    This table has:

    * A matching Python variable name and table name
      (first argument to `Table`).
    * The `metadata` from :mod:`hedwig.db.meta`
      (second argument to `Table`).
    * An integer primary key.
    * A foreign key referencing the `proposal` table.
    * A unique constraint to prevent the insertion of multiple rows
      for the same proposal and instrument.
    * Additional options provided by the `_table_opts` value
      from :mod:`hedwig.db.meta`.

    .. literalinclude:: /../lib/hedwig/facility/example/meta.py
        :lines: 18-

    Please see the
    `SQLAlchemy core metadata documentation <http://docs.sqlalchemy.org/en/rel_1_0/core/metadata.html>`_
    for more information about how to describe your database tables.

#.  Hedwig generally represents data retrieved from the database
    via `namedtuple` types.  These can be conveniently defined
    in terms of the database table's columns.

    You can do this in a file `type.py` in your facility directory.
    This file can also contain any enum-style classes and collection
    classes which you wish to define.

    .. literalinclude:: /../lib/hedwig/facility/example/type.py
        :lines: 18-

#.  Create another file `control.py` in your facility directory.
    This should declare a class named like your facility, but with
    the suffix `Part`.  This class will be used as a mix-in when
    the system constructs a combined database access object.

    Hedwig database access methods are typically given names
    starting with a verb such as `add`, `delete`, `get`, `search`,
    `set`, `sync` or `update`.

    .. literalinclude:: /../lib/hedwig/facility/example/control.py
        :lines: 18-

#.  Ensure that the `etc/hedwig.ini` configuration file includes
    your facility in the `application.facilities` entry
    so that the system loads your facility-specific code
    when setting up a database access object.

#.  Update your database to contain your new tables.
    If you already created a database, then you can use
    Alembic to automatically update the structure.
    Otherwise you can initialize your database and it
    should contain your new tables.
    Both of these operations are described in the
    :ref:`installation_database` section of the :doc:`install` guide.

.. note::
    The database tables for all facilities will be stored in the
    same database namespace.  The same also applies to methods which
    you provide for accessing these tables.  Therefore, to avoid
    custom tables and methods from conflicting with those from
    other facilities, if they are ever run in the same installation
    of Hedwig, it is a good idea to prefix the database tables
    with the facility's short code name.  Database access methods
    should also include the facility code.  For example the JCMT
    facility include a table `jcmt_request` with access methods
    `search_jcmt_request` and `sync_jcmt_proposal_request`.
