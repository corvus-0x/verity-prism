import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import app.models  # noqa — makes Alembic see all our models
from app.config import settings
from app.database import Base

config = context.config

# When running under the test suite, TEST_DATABASE_URL is set and must take
# precedence so migrations target catalyst_test, not the production DB.
url = os.environ.get("TEST_DATABASE_URL") or settings.database_url
config.set_main_option("sqlalchemy.url", url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
