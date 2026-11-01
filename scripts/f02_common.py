"""Private development control connections; credentials never enter URLs or output."""

import os
import stat
from pathlib import Path

import psycopg
import sqlalchemy as sa
from sqlalchemy.pool import QueuePool

NAMES = {
    "app": ("f02_identity_app", "identity_app_password"),
    "admin": ("f02_identity_admin", "identity_admin_password"),
    "migrator": ("f01_control_migrator", "control_migrator_password"),
    "bootstrap": ("f01_bootstrap", "postgres_password"),
}


def credential(role):
    user, name = NAMES[role]
    path = Path("/run/secrets") / name
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise ValueError("PRIVATE_FILE")
    value = path.read_text()
    if not value or len(value) > 4096:
        raise ValueError("PRIVATE_FILE")
    return user, value


def connect(role):
    user, password = credential(role)
    return psycopg.connect(
        host="postgres",
        port=5432,
        dbname="rag_control",
        user=user,
        password=password,
        sslmode="verify-full",
        sslrootcert="/run/f01-ca.crt",
        connect_timeout=5,
        application_name="rag-f02-identity-" + role,
    )


def engine(role="app"):
    return sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: connect(role),
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
        hide_parameters=True,
    )
