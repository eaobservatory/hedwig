Hedwig
======

Installation
------------

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
* lxml
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

Configuration
~~~~~~~~~~~~~

In the `etc` directory, you will find a file called `hedwig.ini.template`.
This file should be copied to create the configuration file `hedwig.ini`.
You will then need to edit the file to complete the configuration.

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

Running a Test Server
~~~~~~~~~~~~~~~~~~~~~

For testing purposes, a stand-alone copy of Hedwig can be run using::

    scripts/hedwigctl test_server

You can also add the `--debug` command line option to enable debugging
and automatic reloading.
Note that this enables the
`Werkzeug Debugger <http://werkzeug.pocoo.org/docs/0.10/debug/>`_
which provides tracebacks and provided access to a Python shell.
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
