from __future__ import with_statement

import logging

from alembic import context

logging.basicConfig(level=logging.INFO)

from hedwig.db.meta import metadata as target_metadata
from hedwig.config import get_config, get_database


def include_object(object_, name, type_, reflected, compare_to):
    """Determine whether or not to include an object.

    Used to ignore the "sqlite_sequence" table.
    """

    if type_ == 'table':
        if name == 'sqlite_sequence':
            return False

    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """

    context.configure(
        url=get_config().get('database', 'url'),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = get_database()._engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
