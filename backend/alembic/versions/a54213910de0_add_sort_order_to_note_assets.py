"""add sort_order to note_assets

Revision ID: a54213910de0
Revises: ae358e965bef
Create Date: 2026-05-05 14:01:42.818935
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a54213910de0'
down_revision: Union[str, None] = 'ae358e965bef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('note_assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('note_assets', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
