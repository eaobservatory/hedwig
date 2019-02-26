Updates Requiring Intervention
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `util/update` directory contains scripts to assist with updates
to the Hedwig database which cannot be handled automatically by `Alembic`.

* 2019-02-26: Transition to linked text, PDF and figure records

  In order to support operations such as copying proposals, extra linking
  tables have been added so that tables which contain large data columns
  (`proposal_fig`, `proposal_pdf`, `proposal_text` and `review_fig`)
  no longer reference the `proposal` (or `reviewer`) table directly.
  Instead these tables will be associated with proposals (or reviews)
  via new linking tables `proposal_fig_link`, `proposal_pdf_link`,
  `proposal_text_link` and `review_fig_link`.

  `Alembic` can be used to create the new tables and remove the
  old references.  However you should fill the references in the
  new tables before the old columns are removed.  Therefore the
  update must be performed in three steps:

  * Use `Alembic` to add the new link tables, but do not allow it to drop
    the `caption`, `proposal_id`, `role` and `reviewer_id` columns of the
    `proposal_fig`, `proposal_pdf`, `proposal_text` and `review_fig` tables.
    You may have to move the commands which drop the
    `idx_pdf_prop_role` and `idx_text_prop_role` indexes to the start
    of the script so that new indexes with those names can be created.

  * Run the `util/update/002_link_attachments` script to fill the new
    link tables.

  * If the update script was successful, use `Alembic` again,
    this time allowing it to drop the old columns.

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
