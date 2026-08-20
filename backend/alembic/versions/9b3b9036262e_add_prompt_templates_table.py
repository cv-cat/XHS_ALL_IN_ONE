"""add prompt_templates table

Revision ID: 9b3b9036262e
Revises: 60cd5c95fde1
Create Date: 2026-06-09 14:06:14.942158
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9b3b9036262e'
down_revision: Union[str, None] = '60cd5c95fde1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('description', sa.String(length=256), nullable=False, server_default=''),
        sa.Column('topic_hint', sa.Text(), nullable=False, server_default=''),
        sa.Column('reference_hint', sa.Text(), nullable=False, server_default=''),
        sa.Column('instruction', sa.Text(), nullable=False, server_default=''),
        sa.Column('system_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_prompt_templates_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_prompt_templates_user_id'))
    op.drop_table('prompt_templates')
