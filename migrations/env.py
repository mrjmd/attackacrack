import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# This is the Flask app and db setup
import sys
# Ensure the project root is in sys.path so app and extensions can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

from app import create_app
from extensions import db as _db # Import db from extensions

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# Corrected: Directly reference alembic.ini from the project root
# Assumes alembic.ini is in the project root (/app/alembic.ini)
# and env.py is in /app/migrations/env.py
# The config.config_file_name itself is 'alembic.ini' if invoked from root
# So, we need to construct the absolute path to it.
alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'alembic.ini'))
fileConfig(alembic_ini_path, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = _db.metadata # Use the metadata from your Flask-SQLAlchemy db instance

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# Create the Flask app instance once
app = create_app()

def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine a
    more complete example would use.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario, we need to create an Engine
    and associate a Connection with the Context.
    """
    # This entire block now runs within the Flask app context
    with app.app_context():
        # Use the db engine from your Flask app
        connectable = _db.engine

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

