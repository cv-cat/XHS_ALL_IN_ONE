"""drop crawl_count and daily_publish_count from auto_tasks

Revision ID: 9023195751b1
Revises: e716e37aa5c1
Create Date: 2026-05-05 21:35:08.586745
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9023195751b1'
down_revision: Union[str, None] = 'e716e37aa5c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('auto_tasks', schema=None) as batch_op:
        batch_op.drop_column('crawl_count')
        batch_op.drop_column('daily_publish_count')


def downgrade() -> None:
    with op.batch_alter_table('auto_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('crawl_count', sa.Integer(), server_default='5', nullable=False))
        batch_op.add_column(sa.Column('daily_publish_count', sa.Integer(), server_default='2', nullable=False))
