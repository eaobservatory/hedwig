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
    and table options `table_opts` from the
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
    * Additional options provided by the `table_opts` value
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
    The following example contains a collection class to be used to
    contain the results of retieving requests from the database.
    This includes the :class:`~hedwig.type.base.CollectionByProposal`
    mix-in since the results will include a `proposal_id` field.

    .. literalinclude:: /../lib/hedwig/facility/example/type.py
        :lines: 18-

#.  Create another file `control.py` in your facility directory.
    This should declare a class named like your facility, but with
    the suffix `Part`.  This class will be used as a mix-in when
    the system constructs a combined database access object.

    Hedwig database access methods are typically given names
    starting with a verb such as `add`, `delete`, `get`, `search`,
    `set`, `sync` or `update`.

    In the following example we allow queries to be performed for
    multiple proposals at once by using :func:`~hedwig.util.is_list_like`
    to check whether multiple `proposal_id` values have been given.
    If so we assign the corresponding column to `iter_field` and
    then, in the transaction `with` block, use
    :meth:`~hedwig.db.control.Database._iter_stmt` to generate a series of
    queries, each for a block of proposals.
    (The size of these blocks is controlled by the database access
    object's `query_block_size` attribute.)
    If `iter_field` is `None` then
    :meth:`~hedwig.db.control.Database._iter_stmt`
    simply returns the statement as-is,
    so we don't need a second version of the query execution step
    for the single-proposal case.

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

* :meth:`~hedwig.facility.generic.view.Generic.get_text_roles`

  This method should return the enum-style class defining text roles
  for the facility.  This will usually be a subclass of
  :class:`~hedwig.type.enum.BaseTextRole`.

* :meth:`~hedwig.facility.generic.view.Generic.get_reviewer_roles`

  This method should return the enum-style class defining reviewer roles
  for the facility.  This will usually be a subclass of
  :class:`~hedwig.type.enum.BaseReviewerRole`.

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

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_view(self, db, proposal, can, args):
        ctx = {
            'title': proposal.title,
        }

        ctx.update(self._view_proposal_extra(db, proposal))

        return ctx

    def _view_proposal_extra(self, db, proposal):
        role_class = self.get_text_roles()
        proposal_text = db.get_all_proposal_text(proposal.id)

        extra = {
            'abstract': proposal_text.get(role_class.ABSTRACT, None),
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

How Hedwig Configures Facilities
--------------------------------

This section gives description of how Hedwig loads facility-specific
code and sets up the web application.

The web application is constructed by
:func:`hedwig.web.app.create_web_app`
which in turn uses the
:func:`~hedwig.config.get_database` and
:func:`~hedwig.config.get_facilities`
functions from the :mod:`hedwig.config` module
to obtain the necessary information before calling
:func:`~hedwig.web.blueprint.facility.create_facility_blueprint`.

#.  :func:`~hedwig.config.get_database` uses a private function
    :func:`~hedwig.config._get_db_class` which reads the list of facilities
    from the configuration file.

    See also the :ref:`facility_database_access` section of the
    :doc:`overview` for an introduction to this process.

    * If the facility is given with a complete package and class name
      then the function tries to load `meta` and `control` modules
      from the same package.

      For example if the facility class was `mypackage.view.MyFacility`,
      we would try to import modules `mypackage.meta` and `mypackage.control`.

    * If the facility is given as a plain class name, it is assumed to
      be located in a module `hedwig.facility.<lower case name>.view`.
      We try to import modules `hedwig.facility.<lower case name>.meta`
      and `hedwig.facility.<lower case name>.control`.

    * Importing the `meta` module will cause the database table information
      to be associated with the `metadata` object in
      :mod:`hedwig.db.meta`.

    * A class `<facility name>Part` is loaded from the `control`
      module and used as part of the dynamically-generated
      `CombinedDatabase` class.

    * Finally an instance of the `CombinedDatabase` class is
      constructed, using the SQLAlchemy engine object
      prepared by :func:`hedwig.db.engine.get_engine`.

#.  :func:`~hedwig.config.get_facilities` gets a list of facility
    classes with the assistance of the private function
    :func:`~hedwig.config._import_class`.

    See also the :ref:`facility_view_classes` section of the
    :doc:`overview` for an introduction to this process.

    * If a complete package and class name is provided then that
      class is loaded.

    * Otherwise if a plain class name is given, it is loaded from the
      module `hedwig.facility.<lower case name>.view`.

#.  The :func:`hedwig.web.app.create_web_app` function now has a database
    control object and list of facility classes.
    It can then go ahead and construct an instance of each
    facility class as follows:

    * It obtains the facility's code using the
      class method :meth:`~hedwig.facility.generic.view.Generic.get_code`.

    * It calls the database's
      :meth:`~hedwig.db.part.proposal.ProposalPart.ensure_facility`
      method to get the facility identifier.
      This is a unique integer used within the database to refer to the
      facility.
      If the facility code was not found, this database method
      adds it to the database and returns the newly-assigned
      identifying number.

    * The facility identifier is passed to the facility class constructor
      which records it as the `id_` attribute.
      Therefore within a facility method, the identifier can always
      be obtained from `self.id_`.

#.  A :class:`~hedwig.type.simple.FacilityInfo` instance,
    with the constructed facility view object stored in the
    `view` attribute, is added to the `facilities` ordered dictionary.
    This is used by some of the other blueprints --- for example the
    "home" blueprint uses it to show each of the facilities on the
    home page.

#.  :func:`~hedwig.web.blueprint.facility.create_facility_blueprint`
    is then passed the facility view object in order to create
    a Flask blueprint which will be registered in the application
    with an URL prefix containing the facility code.

    * An additional template context parameter `facility_name` is
      set up using the value returned by the
      :meth:`~hedwig.facility.generic.view.Generic.get_name` method.

    * All of the fixed facility routes are registered with the
      blueprint, using functions which invoke the methods of the
      view object.

    * The facility's
      :meth:`~hedwig.facility.generic.view.Generic.get_calculator_classes`
      method is used to get a tuple of calculator classes.

      * For each calculator,
        :meth:`~hedwig.view.calculator.BaseCalculator.get_code`
        is called to get the short code name.
        This is converted to an identifier using
        :meth:`~hedwig.db.part.calculator.CalculatorPart.ensure_calculator`
        and then the calculator can be constructed,
        giving the facility view object and calculator identifier.

      * Calculator routes are then registered with the blueprint.

      * A default redirect route is added for the calculator's first mode,
        allowing links to be created to the calculator without
        specifying a mode.

    * The facility's
      :meth:`~hedwig.facility.generic.view.Generic.get_target_tool_classes`
      method is used to get a tuple of target tool classes.

      * As for calculators, for each tool the code is obtained from the
        :meth:`~hedwig.view.tool.BaseTargetTool.get_code` method.
        There are currently no tool identifiers since no database
        tables refer to target tools --- a placeholder tool identifier
        of 0 is passed to the tool constructor along with the facility
        view object.

      * Various routes for each target tool are registered.

      * The target tool's
        :meth:`~hedwig.view.tool.BaseTargetTool.get_custom_routes`
        method is called to determine whether it has any additional
        routes which should be registered with the blueprint.

Adding Calculators
------------------

A "calculator" is a class which can perform any kind of calculation
relevant for the preparation of proposals.
These are typically integration time calculators,
used to estimate the time required for an observation,
but in principle other types of calculators can be added.

The calculator class is often just a type of "wrapper" which
interfaces an existing Python package with the Hedwig calculation system.
The existing package would already implement the required numerical
routines but would not want to be contain Hedwig-specific functionality.
Even if you are creating an entirely new calculator,
you should consider structuring your calculator in this way
because it will make it easy for you to use the separate
calculation package from other code unrelated to Hedwig.

Calculators have the following properties:

* A proposal needs to record the exact input and ouput of the calculator
  as it was at the time the proposal was prepared.
  Therefore calculations, including their results,
  are stored in the `calculation` database table.

  The input and output values of each calculation are stored
  as JSON-encoded dictionaries using a custom
  database columm class :class:`~hedwig.db.type.JSONEncoded`.

* A calculator can have several modes of operation.
  The first defined mode is considerered to be the "default"
  mode and will be the mode accessed by an URL which omits the mode code.
  The calculator should be able to convert calculations between
  its different modes.  For example if an integration time calculator has
  "time" (as a function of sensitivity) and
  "sensitivity" (as a function of time) modes,
  it should be able to convert a "sensitivity" calculation
  to a "time" calculation by taking the output sensitivity
  and making it an input to the "time" calculation.

* A calculator must have a (integer) version number
  which will be saved in the `calculation` table with any
  calculations attached to proposals.
  It must support the following version-specific operations:

  * Getting a list of input parameters for any version of the calculator.
    This is necessary for proposals to know how to format the inputs
    of calculations saved with a previous version.

  * Converting a set of input parameters from any version into a
    set of inputs usable with the current version.
    This is used whenever someone tries to re-open a saved
    calculation.

  * Getting a list of output parameters for any version.
    Again this is so that a calculation can be formatted for display
    on a proposal.

* The calculator should also be able to determine the version
  of the underlying calculation code.
  When the calculations are performed by a separate Python module,
  this can be the version (string) of that module.

When you are ready to start implementing a new calculator
class for Hedwig, you can begin as follows:

#.  Add a new module to your facility directory which implements
    a class derived from the
    :class:`hedwig.view.calculator.BaseCalculator` class.

#.  Import your calculator class in your facility's `view` module
    and add it to the tuple returned by your
    :meth:`~hedwig.facility.generic.view.Generic.get_calculator_classes`
    method.

#.  Override the :meth:`~hedwig.view.calculator.BaseCalculator.get_code`
    method so that it returns a short code name which will be unique
    in all facilities which may use the calculator.

    Also override :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.get_name`
    to return the calculator's name for display purposes and define
    an integer class `version` attribute.

#.  Define the modes implemented by your calculator.
    Each mode needs:

    * An integer identifier.
    * A short unique code name.
    * A display name.

    A calculator class will normally define "constant" variables
    for the mode identifiers.
    It must then define a class variable `modes` which is an
    ordered dictionary mapping mode identifiers to
    :class:`~hedwig.type.simple.CalculatorMode` tuples
    containing the code and name.  For example:

    .. code-block:: python

        class AnotherExampleCalculator(BaseCalculator):
            TIME = 1
            SENSITIVITY = 2

            modes = OrderedDict((
                (TIME, CalculatorMode(
                    'time',
                    'Time for given sensitivity')),
                (SENSITIVITY, CalculatorMode(
                    'sensitivity',
                    'Sensitivity for given time')),
            ))

            version = 1

#.  Next you will need to define the inputs and outputs of your
    calculator.  Each of these values is specified by a
    :class:`~hedwig.type.simple.CalculatorValue` tuple.

    The inputs and outputs are defined by implementing the methods
    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.get_inputs` and
    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.get_outputs`.
    Both of these take the calculator mode and version as
    arguments and return a list of values.
    In the case of the input values, this list should be an instance of
    :class:`~hedwig.type.misc.SectionedList`
    because the `calculator_base.html` template displays the section
    names as separators between parts of the HTML form.
    This class may also make it easier to constuct the
    input value list for different versions/modes of a calculator.
    However if you override the whole `calculator_input_list` template block
    then a :class:`~hedwig.type.misc.SectionedList` is not required
    and the standard list type can be used.

#.  Completing the calculator class involves overriding several more
    methods in order to implement your calculator's functionality.
    Please take a look at the source code for the
    :class:`~hedwig.view.calculator.BaseCalculator` and
    :class:`~hedwig.facility.example.calculator_example.ExampleCalculator`
    classes.

    The main view handling method is
    :meth:`hedwig.view.calculator.BaseCalculator.view`
    and this is intended to be used for most calculators.
    It calls other calculator methods which implement the
    functionality which is expected to change for different calculators.
    It is therefore recommended that you do not override the
    :meth:`~hedwig.view.calculator.BaseCalculator.view`
    method unless you are writing an unusual type of
    calculator for which it is not appropriate.

    Methods which you are likely to wish to customize include:

    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.get_calc_version`
        This returns the version (string) of the underlying calculation
        routine.  This is just used for information in order to allow
        users to identify the version of a calculator which produced
        a given result.

        This should not be confused with the `version` attribute which
        controls the version of the interface with Hedwig --- i.e.
        the list of input and output values for a given mode and version.

    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.get_default_input`
        This should return sensible default input parameters for any mode.

    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.convert_input_mode`
        Adjusts the input parameters when changing mode.

    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.convert_input_version`
        Converts the input parameters for any given version of the calculator
        so that they will work with the current version.

    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.parse_input`
        Parses values retrieved from the input form.

        This is separate from the
        :meth:`~hedwig.view.calculator.BaseCalculator.get_form_input`
        method, which you may not need to override,
        in order to improve handing of invalid input.

    :meth:`~hedwig.facility.example.calculator_example.ExampleCalculator.__call__`
        Performs the actual calcuation, returning a
        :class:`~hedwig.type.simple.CalculatorResult` tuple.

#.  Finally you will probably need to customize the HTML
    template used for your calculator.
    Your template should be named `calculator_<calculator code>.html` and
    located in your facility's template directory.
    Most calculator templates will extend the
    `generic/calculator_base.html` template which contains a large number of
    inheritance blocks for easy customization.

    Here is the template for the example calculator which adds
    sections to display additional information from the
    `extra` component of the :class:`~hedwig.type.simple.CalculatorResult`.

    .. literalinclude:: /../data/web/template/example/calculator_example.html
        :language: html+jinja

Adding Target Tools
-------------------

A "target tool" is a class which can perform some kind of analysis
of one or more observing target positions.
One target tool --- the "Clash Tool"
(implemented in the :class:`~hedwig.facility.generic.tool_clash.ClashTool`
class) is integrated with Hedwig.
It queries the coverage regions stored in the `moc`, `moc_cell`
and `moc_fits` database tables and managed through the
facility administrative interface.
Properties of target tools are:

* We are generally only interested in the current analysis of the
  target positions from the most recent version of the tool
  and its associated data.
  Therefore tool results are currently not stored in the database.
  If it ever becomes necessary for a proposal author to refer to exact
  results from a target tool, or if a target tool becomes
  computationally expensive to run, then we will need to add
  database structures to allow target tool results to be saved.

* Target tools can be run on a single target specified by the user,
  or applied to a list of targets retrieved from a proposal
  or uploaded by a user.
  These comprise the three operational modes of a target tool:
  "single", "proposal" and "upload".

* In general target tools are simpler than calculators as they
  do not deal with storing results and tracking version information.
  However it is not anticipated that their output will fit into a
  common structure --- each tool will likely need a
  completely different HTML template, at least for the output block.

If you would like to implement a new target tool for use with
Hedwig, you can get started as follows:

#.  Add a new module to your facility directory which implements
    a class derived from the
    :class:`hedwig.view.tool.BaseTargetTool` class.
    If your new target tool is intended to be more generally
    useful, you might wish to consider adding it to Hedwig's
    generic facility instead.

#.  Import your target tool class in your facility's `view` module
    and add it to the tuple returned by your
    :meth:`~hedwig.facility.generic.view.Generic.get_target_tool_classes`
    method.

#.  Override the :meth:`~hedwig.view.tool.BaseTargetTool.get_code`
    method so that it returns a short code name which will be unique
    in all facilities which may use the target tool.

    Also override :meth:`~hedwig.view.tool.BaseTargetTool.get_name`
    to provide the name of the target tool and
    :meth:`~hedwig.view.tool.BaseTargetTool.get_default_facility_code`
    if you intend it to be used by multiple facilities.

#.  Provide an implementation of the main target analysis method
    :meth:`~hedwig.view.tool.BaseTargetTool._view_any_mode`.
    By default this will be called with a list of target objects
    for all of the target tool's modes (single target, uploaded list
    and proposal-based).

    If you need to implement different behavior in different modes,
    you can instead override the
    :meth:`~hedwig.view.tool.BaseTargetTool._view_single`,
    :meth:`~hedwig.view.tool.BaseTargetTool._view_upload` and
    :meth:`~hedwig.view.tool.BaseTargetTool._view_proposal`
    methods directly.

    Any of these view methods returns a dictionary which is
    used to update the template context.
    You can add any output from your target tool,
    any additional information you wish to display on the
    target tool's web pages
    and override existing entries such as the
    `message` indicating errors with the user input and the
    `run_button` text used for the form's submit button.

#.  Take a look at the source code of the
    :class:`~hedwig.view.tool.BaseTargetTool` and
    :class:`~hedwig.facility.generic.tool_clash.ClashTool`
    (as an example)
    classes in case there are any other methods you would
    like to override.

#.  You will need to provide an HTML template to display your
    target tool's output.  This should be named
    `tool_<tool code>.html` and be located in the facility's
    template directory.
    The template should almost always inherit from the
    `generic/tool_base.html` template which provides the
    input form for single targets and target list uploads.

    Here is a simple example target tool HTML template.
    Note that we check whether we have output to display --- the
    base template calls this block in either case, because
    there may be fixed information we wish to show.
    Here we check if some output, assumed to be stored in the
    template context value `tool_output`, is `None`.
    The view function would need to ensure that it sets
    this value to `None` if called without a list of target
    objects to analyze.

    .. code-block:: html+jinja

        {% extends 'generic/tool_base.html' %}

        {% block tool_output %}
            {% if tool_output is not none %}
                <p>Target tool output here...</p>
            {% endif %}
        {% endblock %}

#.  If necessary for your target tool, you can add custom routes
    by overriding the
    :meth:`~hedwig.view.tool.BaseTargetTool.get_custom_routes`
    method and writing the appropriate view functions and HTML templates.
