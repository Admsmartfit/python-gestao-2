"""Add tipo_resposta and resposta_estruturada to RegrasAutomacao

Revision ID: add_tipo_resposta_estruturada
Revises: add_palavras_saudacao
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_tipo_resposta_estruturada'
down_revision = 'add_palavras_saudacao'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('whatsapp_regras_automacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tipo_resposta', sa.String(30), nullable=False, server_default='texto'))
        batch_op.add_column(sa.Column('resposta_estruturada', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('whatsapp_regras_automacao', schema=None) as batch_op:
        batch_op.drop_column('resposta_estruturada')
        batch_op.drop_column('tipo_resposta')
