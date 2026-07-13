"""add user admin and active flags

Revision ID: a4f7c2d9e801
Revises: 60cd5c95fde1
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4f7c2d9e801"
down_revision: Union[str, None] = "60cd5c95fde1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE users SET is_admin = :is_admin "
            "WHERE id = (SELECT MIN(id) FROM users)"
        ).bindparams(is_admin=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("is_active")
        batch_op.drop_column("is_admin")
