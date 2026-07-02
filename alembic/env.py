"""Alembic environment configuration for migrations."""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Path setup
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")

def load_dotenv(path: str) -> None:
    """Populate os.environ from a .env file."""
    if not os.path.exists(path):
        return
    with open(path, "r") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            if key and _ and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")

# Load environment variables
load_dotenv(DOTENV_PATH)

# Ensure app is importable
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app import models 
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def get_database_url() -> str:
    """Return database URL from env."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set in environment or .env file")
    return url

# Set the URL dynamically
config.set_main_option("sqlalchemy.url", get_database_url())
target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode using a live async DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, poolclass=pool.NullPool)

    def do_run_migrations(connection) -> None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
