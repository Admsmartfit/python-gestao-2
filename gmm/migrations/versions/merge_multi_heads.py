"""Merge das duas chains independentes

Revision ID: merge_multi_heads
Revises: 3ec26333d72d, add_cotacoes_config_compras
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_multi_heads'
down_revision = ('3ec26333d72d', 'add_cotacoes_config_compras')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
