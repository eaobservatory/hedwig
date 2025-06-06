Updates Requiring Intervention
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `util/update` directory contains scripts to assist with updates
to the Hedwig database which cannot be handled automatically by `Alembic`.

* 2025-01-02: Addition of format column to message table

  A `format` column has been added to the `message` table to allow
  different types of message formatting to be used.  `Alembic` can
  be used to create the new column, but the default value (to be
  used for existing records) should be 1 (corresponding to
  `MessageFormatType.PLAIN_FLOWED`)::

      op.add_column('message', sa.Column(
          'format', sa.Integer(), nullable=False, server_default='1'))

* 2023-08-24: New email validation check

  The regular expression used to check that email addresses are valid
  has been updated to be more specific.  You may check whether all
  addresses would still be considered valid as follows:

  * Run the `util/update/005_check_email` script to look for existing
    database entries which do not match the new pattern.

  * Adjust or remove any invalid addresses via the web interface.

* 2023-05-04: Addition of sort_order column to prev_proposal table

  A `sort_order` column has been added to the `prev_proposal` table to
  allow entries to be ordered as desired in a similar way to other
  parts of a proposal.

  * Use `Alembic` to add the new column, giving a `server_default`
    argument of 0::

      op.add_column('prev_proposal', sa.Column(
        'sort_order', sa.Integer(), nullable=False, server_default='0'))

  * Run the `util/update/004_prev_proposal_sort` script to fill the
    new column based on the previous ordering (order in which added).

* 2022-07-21: Addition of verified column to person table

  A new flag has been added to the person table to record whether
  their account has been verified.  When creating the new column
  with `Alembic`, a false default value should be given::

      op.add_column('person', sa.Column(
        'verified', sa.Boolean(), nullable=False, server_default='0'))

  Then if you want existing verified users to be able to continue to use the
  system without being prompted to re-verify their account:

  * Run the `util/update/003_person_verified` script to set the verified
    flag for existing registered accounts with verified addresses or
    logged invitation acceptances.

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
    the `sort_order`, `caption`, `proposal_id`, `role` and `reviewer_id`
    columns of the `proposal_fig`, `proposal_pdf`, `proposal_text` and
    `review_fig` tables.  You may have to move the commands which drop the
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
  `ReviewState.DONE`)::

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
