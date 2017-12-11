Updates Requiring Intervention
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `util/update` directory contains scripts to assist with updates
to the Hedwig database which cannot be handled automatically by `Alembic`.

* 2018-05-22: Addition of state column to review table

  A `state` column has been added to the `review` database table.  `Alembic`
  should create the new column correctly, but you should ensure that the
  default value (used for the existing records) is 2 (corresponding to
  `ReviewState.DONE`::

      op.add_column('review', sa.Column(
          'state', sa.Integer(), nullable=False, server_default='2'))

* 2017-06-08: Addition of state column to message table

  A `state` column has been added to the `message` database table.  This new
  column replaces the previous `discard` column.
  It is recommended that you disable any poll process which would send
  email messages during this update and check that the status of
  existing messages is correct (no messages unexpectedly marked as *unsent*)
  before reactivating it.
  The update must be performed in three steps:

  * Use `Alembic` to add the new `state` column, but do not allow it to drop
    the `discard` column.
    Set the `server_default` argument to 0
    (corresponding to an unknown status)::

        op.add_column('message', sa.Column(
            'state', sa.Integer(), nullable=False, server_default='0'))

  * Run the `util/update/001_message_state` script to fill the new `state`
    column values.

  * If the update script was successful, use `Alembic` again,
    this time allowing it to drop the old `discard` column.
