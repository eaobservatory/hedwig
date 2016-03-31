Hedwig
======

Installation
------------

.. hedwigstartinstall

For Development
~~~~~~~~~~~~~~~

To prepare a copy of Hedwig for testing and development, you should clone
the Git repository into your workspace.
You can then either "install" the package, perhaps in a "virtualenv"::

    virtualenv-2.7 venv
    source venv/bin/activate
    pip install --editable .

Or set your `PYTHONPATH` environment variable to include Hedwig's `lib`
directory::

    export PYTHONPATH=lib

If you need to run Hedwig from another directory, set an absolute `PYTHONPATH`
(if not using a "virtualenv") and set the environment variable
`HEDWIG_DIR` to the top level of the Hedwig repository.
This is necessary to enable Hedwig to locate resources such as
the configuration file and HTML templates.

For Apache (with mod_wsgi)
~~~~~~~~~~~~~~~~~~~~~~~~~~

An example `.wsgi` script file is provided with Hedwig, called
`hedwig.wsgi.example`.
You can copy this file to `hedwig.wsgi` and adjust the paths
for the "virtualenv" and Hedwig home directory.
For more information about using Flask-based applications
(such as Hedwig) with `mod_wsgi`, see the
`Flask guide for mod_wsgi <http://flask.pocoo.org/docs/0.10/deploying/mod_wsgi/>`_.

Requirements
~~~~~~~~~~~~

The following Python modules should be installed:

* astropy
* docopt
* docutils
* Flask
* healpy
* mysql-connector-python
* Pillow
* pycountry
* pymoc
* PyPDF2
* python-magic
* requests
* SQLAlchemy

There are also facility-specific requirements:

* JCMT

  * jcmt_itc_heterodyne
  * jcmt_itc_scuba2

.. _installation_configuration:

Configuration
~~~~~~~~~~~~~

In the `etc` directory, you will find a file called `hedwig.ini.template`.
This file should be copied to create the configuration file `hedwig.ini`.
You will then need to edit the file to complete the configuration.

* **database**

  * *url*

    This is the SQLAlchemy URL for the database you wish Hedwig to use.
    The example configuration file contains URL formats for SQLite
    and MySQL.
    (These are the two databases which have been tested with Hedwig.
    In theory any database supported by SQLAlchemy should be usable,
    but may require additional tuning of the Hedwig database access code,
    as has been done for these databases.)

  * *pool_size* and *pool_overflow* (optional)

    These configure the SQLAlchemy pool.  They can be left blank to use
    Hedwig's defaults (size 15, overflow 5).

* **application**

  * *name*

    This is the name by which the system will refer to itself.  You can alter
    this if you want it to be called something other than "Hedwig".

  * *secret_key*

    This is the key used by Flask for its secure cookie session system.
    Since Hedwig uses this system to authenticate users, you must be
    sure to enter a good random string here.
    The `Flask quick start guide <http://flask.pocoo.org/docs/0.10/quickstart/>`_
    recommends 24 random bytes.

  * *facilities*

    Here you can list the facilities for which you wish to accept proposals.
    Hedwig has a basic facility configuration called "Generic" which you can
    use to test the system.  It also forms the basis for specific facilities.
    To indicate multiple facilities, you can give a comma-separated list.
    Each facility can either be a plain name, in which case the classes
    defining the facility are loaded from a submodule of `hedwig.facility`,
    or as a full Python module and class name, if the classes cannot be
    placed in the Hedwig namespace.

  * *log_file* (optional)

    If this entry is set, it configures the location to which errors and
    warnings from the web application will be written.

* **upload**

  In this section you can configure maximum file size upload limits (in MiB).
  The Flask `MAX_CONTENT_LENGTH` will be set to the maximum of the sizes
  given here.

* **email**

  * *server*

    Here you should enter the name of a mail server to which Hedwig can
    connect to send email messages.

  * *from*

    This specifies the from header which should be used.  You may wish to
    use your proposal support mailing list address here to allow people
    to reply directly, for example::

        Hedwig <proposals@some-observatory.org>

  * *footer_title* (optional)

    A title to display under the *application_name* in the signature part
    of the email, e.g.::

        Some Observatory Proposal System

  * *footer_url* and *footer_email* (optional)

    An optional URL and email address (which may or may not be the same as
    that in the *from* header) to show in the footer of email messages.

* **utilities**

  This section contains the paths to various applications which Hedwig uses.
  You may need to customize this section if the applications aren't in
  their typical location.

  * *ghostscript*

    Used to process files (PDF and EPS) uploaded as part of a proposal.

  * *firefox*

    Used in the integration test system.  (See the next section for details.)

* **ads**

  *api_token*

  This is an API token for the Astrophysics Data System, used to look up
  ADS bibcodes and DOIs.
  To obtain a token, create an account for the
  `new version of ADS <https://ui.adsabs.harvard.edu/>`_
  and select
  "API Token" under "Customize Settings".

Tests
~~~~~

The Hedwig unit tests can be run with::

    PYTHONPATH=lib python2 -m unittest discover

(You can omit the `PYTHONPATH` setting if you have activated
a "virtualenv" or already set `PYTHONPATH` as described above.)

Hedwig also includes a `Selenium <http://www.seleniumhq.org/>`_-based
integration test.
This also acquires the screenshots used in the documentation.
It can be run with::

    PYTHONPATH=lib:util/selenium python2 -m unittest discover -s ti

Note that the tests use the example configuration file
`hedwig.ini.template` in order to avoid requiring configuration.
Unfortunately this means that you may need to adjust the path
to Firefox in this file so that it points to a (typically older)
version of Firefox supported by Selenium.

.. _installation_database:

Database
~~~~~~~~

After configuring your database in the `hedwig.ini` file,
you can create the initial database structure using the `hedwigctl` tool::

    scripts/hedwigctl initialize_database

If you need to update an existing Hedwig database when an update to the
software leads to a change to the database structure, you can use
`Alembic <https://alembic.readthedocs.org/>`_ to help you make the change.
Configuration for Alembic is included with Hedwig.
You can generate a migration script with::

    alembic revision --autogenerate -m 'Description of change ...'

And then apply the changes with::

    alembic upgrade head

The script will be created in the `util/alembic/versions` directory.
It is often necessary to adjust the script slightly.
For example to provide a `server_default` keyword argument
for new columns without defaults which do not allow nulls.
(The `server_default` is an SQL string representing the default
value.
This could, for example, be `"0"` for a boolean column.)

When deploying a live copy of Hedwig, don't forget to set up a
database backup system.
One way to do this is to set up a Cron job to run
`mysqldump <https://dev.mysql.com/doc/refman/5.0/en/mysqldump.html>`_
regularly.

Please ensure that your database's settings regarding maximum
query size permit Hedwig to store and retrieve the maximum upload
file size as set in the configuration file.
For example, with MySQL and the default `max_pdf_size` of 10MiB
you might wish to set the maximum packet size to 15MiB::

    max_allowed_packet=15M

.. _installation_test_server:

Running a Test Server
~~~~~~~~~~~~~~~~~~~~~

For testing purposes, a stand-alone copy of Hedwig can be run using::

    scripts/hedwigctl test_server

You can also add the `--debug` command line option to enable debugging
and automatic reloading.
Note that this enables the
`Werkzeug Debugger <http://werkzeug.pocoo.org/docs/0.10/debug/>`_
which provides tracebacks and provides access to a Python shell.
*It should never be run in a manner accessible to untrusted users!*
When this option is specified, `hedwigctl` configures the
internal server to listen on localhost only.

Poll Process
~~~~~~~~~~~~

In order for the web interface to remain responsive during busy
periods, Hedwig was designed to take certain background tasks
offline.
These are:

* Sending email messages.
* Processing uploaded figures.
* Processing uploaded PDF files.
* Looking up publication references.
* Preparing feedback messages.

In a live copy of Hedwig, you will need to keep a poll process
running to perform these tasks.
You can do this with a Cron job such as the following
(with the path to Hedwig completed)::

    */10 * * * * cd ..../hedwig; source venv/bin/activate; hedwigctl poll all --pidfile poll.pid --pause 15 --logfile poll.log

This example checks every 10 minutes that `hedwigctl poll` is running
and uses a 15 second pause between polls for tasks to perform.
The process is controlled by the `poll.pid` file and a `poll.log` file
is written --- both of these will be in the Hedwig directory
if the job is defined as given above.

If you need more control over the background processes,
you can poll for specific types of tasks.

Documentation
~~~~~~~~~~~~~

You can use `Sphinx <http://sphinx-doc.org/>`_ to build the
documenation with::

    sphinx-build -b html doc doc/_build/html

Updating a Live Instance
~~~~~~~~~~~~~~~~~~~~~~~~

If you would like to update the version of the Hedwig running in
a live deployment, there are a number of steps which you should
perform to ensure that the processes is completed smoothly.
These include:

* Ensure you have an up-to-date backup of your database,
  especially if the update requires changes to the database
  schema.
  (See the `Database`_ section above for information about `mysqldump`.)
* Run the `Selenium` test to generate updated screenshots for the documentation
  (as described in the `Tests`_ section)
  and copy them to your web server, if necessary.
* Stop any running poll processes and temporarily disable any Cron jobs which
  would restart them.
* Update the software version.
  The exact steps required would depend on how you installed Hedwig ---
  if you have a `Git` clone installed in "editable" mode into a "virtualenv",
  this can be as simple as performing a `Git` pull.
* Run the unit tests, being sure that you are testing the new version
  of the software.
  This may indicate if there are any additional software dependencies
  which need to be installed.
* Update your configuration file if necessary, for example if new
  options have been added.  (Compare your hedwig.ini to hedwig.ini.template
  to check.)
* Update your database if the schema has changed --- see the
  notes on using `Alembic` in the `Database`_ section.
* Restart the web application.
  For example, using Apache, you can touch the `hedwig.wsgi` file,
  provided `WSGIScriptReloading` is enabled, which it is by default.
* Try accessing the web application.
  There may be delay loading the first page as Apache restarts Hedwig.
* Restart your poll processes or re-enable the Cron jobs which run them.
* Add any new database tables to your backup system.
* From the site administration menu,
  check the email messages and processing status pages for tasks stuck in the
  "Processing" or "Sending" states.

.. hedwigendinstall

License
-------

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
