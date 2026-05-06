"""add user_id to notes

Revision ID: 60cd5c95fde1
Revises: 9023195751b1
Create Date: 2026-05-06 11:56:07.372899
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '60cd5c95fde1'
down_revision: Union[str, None] = '9023195751b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_index(batch_op.f('ix_notes_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notes_user_id'))
        batch_op.drop_column('user_id')
