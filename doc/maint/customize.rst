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

Overriding Display Templates
----------------------------

Hedwig uses `Jinja2 <http://jinja.pocoo.org/>`_ templates
for HTML pages and email messages.

* **HTML pages**

  These templates are rendered by the Jinja2 environment provided by Flask.
  In Hedwig this is done by the :func:`hedwig.web.util.templated` decorator
  and :func:`hedwig.web.util._make_response` function which in turn calls
  `flask.render_template`.

  A number of extra template utilities
  (global functions, filters and tests)
  are added to the Jinja2 enviroment by the
  :func:`hedwig.web.template_util.register_template_utils` function.

  Templates are located in the following directories:

  * `data/web/template/`

    This contains the base `layout.html` template from which most
    other templates inherit.

  * `data/web/template/generic/`

    Contains the generic version of the facility-specific templates.

  * `data/web/template/<facility code>/`

    Contains templates which override the generic versions for a
    particular facility, along with any additional templates used
    by the facility.

* **Email messages**

  Email messages are formatted by a Jinja2 enviroment set up by the
  :func:`hedwig.email.format.get_environment` function and applied by
  :func:`hedwig.email.format.render_email_template`.  This function also
  adjusts the line wrapping of the message in preparation for it to be
  sent in flowed format.

  * `data/email/`

    Again this contains a basic `layout.txt` template used by other templates.

  * `data/email/generic/`
  * `data/email/<facility code>/`

The templates make use of Jinja2's
`template inheritance <http://jinja.pocoo.org/docs/dev/templates/#template-inheritance>`_
mechanism.  For example the generic `proposal_view.html` template
includes a placeholder block for the observing request:

.. code-block:: html+jinja

    {% block proposal_request %}
    {% endblock %}

This can be overridden in a facility-specific template to fill
in the observing request section:

.. code-block:: html+jinja

    {% extends 'generic/proposal_view.html' %}

    {% block proposal_request %}
        <section>
            <h2 id="request">Observing Request</h2>

            <p>...</p>
        </section>
    {% endblock %}

When overriding the generic templates, you may find that the section you
wish to change is already marked as a block, like the `proposal_request`
block above.  It may or may not already include a generic implementation.
Sometimes the part may not yet be enclosed in a block --- then you should
consider editing the generic template to insert a block in order to make
it easier for you to create a child template.

Note that a template block can also call `super` to include the
content of the parent block.

.. code-block:: html+jinja

    {% extends 'generic/some_template.html' %}

    {% block content %}
    <p>
        This is an extra note which this facility
        needs to show on this page.
    </p>

    {{ super() }}
    {% endblock %}


Overriding View Methods
-----------------------

To customize the behavior of Hedwig for your facility,
you will also need to override and add new methods
to the facility view class.  Some of these are used by
the system to get information about your facility,
while others implement handling code for the
various web pages which make up the user interface.

Informational Methods
~~~~~~~~~~~~~~~~~~~~~

You may have noticed that the generic facility's
:class:`~hedwig.facility.generic.view.Generic` class
includes most of its functionality through mix-in classes.
This is done simply to help organize the source code
into manageable components.
If you browse through the
:class:`~hedwig.facility.generic.view.Generic` class
itself, you will find a number of methods you may
wish to override, following on from the
:meth:`~hedwig.facility.generic.view.Generic.get_code` and
:meth:`~hedwig.facility.generic.view.Generic.get_name` methods
discussed above.
Some examples of such methods are:

* :meth:`~hedwig.facility.generic.view.Generic.make_proposal_code` and
  :meth:`~hedwig.facility.generic.view.Generic._parse_proposal_code`

  These methods should implement your facility's scheme for numbering
  proposals.
  Provided you can extract the semester, queue and proposal number
  from a formatted proposal code, you should only
  need to override the protected method
  :meth:`~hedwig.facility.generic.view.Generic._parse_proposal_code`
  and you can leave the generic public method
  :meth:`~hedwig.facility.generic.view.Generic.parse_proposal_code`
  to look up the project in the database.
  If this is not possible you may have to override the
  :meth:`~hedwig.facility.generic.view.Generic.parse_proposal_code`
  method itself.

* :meth:`~hedwig.facility.generic.view.Generic.make_archive_search_url`

  If your facility has a data archive which can be searched by sky coordinates,
  you can override this method to provide a routine capable of producing
  a suitable URL.

* :meth:`~hedwig.facility.generic.view.Generic.make_proposal_info_urls`

  This can be used to make a list of URLs related to previous proposals,
  for example search your archive for observations for a given project,
  or to see the project's details in any online tracking system you may have.

* :meth:`~hedwig.facility.generic.view.Generic.calculate_overall_rating`

  During the review process, the reviewers may enter numerical ratings
  for each proposal.
  This method should implement your facility's algorithm for combining
  these ratings into a single overall rating for each proposal.

* :meth:`~hedwig.facility.generic.view.Generic.calculate_affiliation_assignment`

  This method should implement your rules for determining the affiliation
  of a proposal based on the affiliations of its members.

Web Interface Handling Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The majority of the methods defined in the facility view class are
used to handle requests made to the web interface.
These methods are attached to routes by the
:func:`hedwig.web.blueprint.facility.create_facility_blueprint`
function.
Each view function accepts a number of arguments,
such as the database access object,
information from the URL path and query parameters,
and information from an HTML form, if the request was a POST.
If the route is associated with a Jinja2 template,
then the view function should return the context dictionary
to be used to render the template.

For example, the
:class:`~hedwig.facility.generic.view_proposal.GenericProposal`
mix-in which forms part of the
:class:`~hedwig.facility.generic.view.Generic`
view class includes a method
:meth:`~hedwig.facility.generic.view_proposal.GenericProposal.view_proposal_view`
which is used to show a complete proposal.
This method creates an initial context dictionary and then
calls an additional private method
:meth:`~hedwig.facility.generic.view_proposal.GenericProposal._view_proposal_extra`
to gather more information.
Here is an abbreviated version of these methods:

.. code-block:: python

    @with_proposal(permission='view')
    def view_proposal_view(self, db, proposal, can, args):
        ctx = {
            'title': proposal.title,
        }

        ctx.update(self._view_proposal_extra(db, proposal))

        return ctx

    def _view_proposal_extra(self, db, proposal):
        proposal_text = db.get_all_proposal_text(proposal.id)

        extra = {
            'abstract': proposal_text.get(TextRole.ABSTRACT, None),
        }

        return extra

To extend this for another facility we need only override the
:meth:`~hedwig.facility.generic.view_proposal.GenericProposal._view_proposal_extra`
private method, for example:

.. code-block:: python

    def _view_proposal_extra(self, db, proposal):
        ctx = super(Example, self)._view_proposal_extra(db, proposal)

        requests = db.search_example_request(proposal.id)

        ctx.update({
            'example_requests': requests.values(),
        })

        return ctx

This example illustrates how we can get the "extra" context
from the superclass (normally the
:class:`~hedwig.facility.generic.view.Generic` facility),
when it is appropriate to do so,
and add additional information to it.
You will probably encounter this pattern of methods in
several places within Hedwig.
As with overriding templates, where this mechanism
is already established, you can use it to easily extend
the system's functionality.
Otherwise, you should consider breaking up the appropriate
method into a public (fixed) part and protected part (for overriding)
so that you can add facility-specific behavior without
having to re-implement the whole view function.

The above example also includes the
:func:`hedwig.view.util.with_proposal` decorator.
This is a convenience routine which intercepts the
`db` and `proposal_id` arguments and fetches the proposal from the database.
It then gets the current authorization object ("`can`") for the proposal
and checks that the user has the specified permission.
The decorated function is then called with the `db` object, `proposal`
(in place of the `proposal_id`), "`can`" authorization object
(as an additional argument) and any remaining arguments.
