"""add user_id to publish_jobs

Revision ID: ae358e965bef
Revises: 10d6e0bf7083
Create Date: 2026-05-03 22:47:16.635670
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ae358e965bef'
down_revision: Union[str, None] = '10d6e0bf7083'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('publish_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_publish_jobs_user_id'), ['user_id'], unique=False)

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE publish_jobs SET user_id = ("
        "  SELECT pa.user_id FROM platform_accounts pa"
        "  WHERE pa.id = publish_jobs.platform_account_id"
        ") WHERE user_id IS NULL AND platform_account_id IS NOT NULL"
    ))
    conn.execute(sa.text(
        "UPDATE publish_jobs SET user_id = ("
        "  SELECT ad.user_id FROM ai_drafts ad"
        "  WHERE ad.id = publish_jobs.source_draft_id"
        ") WHERE user_id IS NULL AND source_draft_id IS NOT NULL"
    ))


def downgrade() -> None:
    with op.batch_alter_table('publish_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_publish_jobs_user_id'))
        batch_op.drop_column('user_id')
