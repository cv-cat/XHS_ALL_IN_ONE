"""add schedule fields to auto_tasks

Revision ID: 37a4bd3e2351
Revises: 31c257707df9
Create Date: 2026-05-05 18:54:06.222993
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '37a4bd3e2351'
down_revision: Union[str, None] = '31c257707df9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('auto_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('schedule_type', sa.String(32), server_default='manual', nullable=False))
        batch_op.add_column(sa.Column('schedule_time', sa.String(32), server_default='09:00', nullable=False))
        batch_op.add_column(sa.Column('schedule_days', sa.String(64), server_default='', nullable=False))
        batch_op.add_column(sa.Column('schedule_interval_hours', sa.Integer(), server_default='24', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('auto_tasks', schema=None) as batch_op:
        batch_op.drop_column('schedule_interval_hours')
        batch_op.drop_column('schedule_days')
        batch_op.drop_column('schedule_time')
        batch_op.drop_column('schedule_type')
