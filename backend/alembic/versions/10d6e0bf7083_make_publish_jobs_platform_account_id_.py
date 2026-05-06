"""make publish_jobs platform_account_id nullable

Revision ID: 10d6e0bf7083
Revises: df3b1005390e
Create Date: 2026-05-03 22:29:14.051292
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '10d6e0bf7083'
down_revision: Union[str, None] = 'df3b1005390e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('publish_jobs', schema=None) as batch_op:
        batch_op.alter_column('platform_account_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('publish_jobs', schema=None) as batch_op:
        batch_op.alter_column('platform_account_id',
               existing_type=sa.INTEGER(),
               nullable=False)
