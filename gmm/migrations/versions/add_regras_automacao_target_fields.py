"""Add para_terceirizados and para_usuarios to RegrasAutomacao

Revision ID: add_regras_target_fields
Revises: add_resposta_nao_cadastrado
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_regras_target_fields'
down_revision = 'add_resposta_nao_cadastrado'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('whatsapp_regras_automacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'para_terceirizados', sa.Boolean(), nullable=True, server_default=sa.true()
        ))
        batch_op.add_column(sa.Column(
            'para_usuarios', sa.Boolean(), nullable=True, server_default=sa.true()
        ))


def downgrade():
    with op.batch_alter_table('whatsapp_regras_automacao', schema=None) as batch_op:
        batch_op.drop_column('para_usuarios')
        batch_op.drop_column('para_terceirizados')
