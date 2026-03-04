"""Add fallback and saudacao fields to ConfiguracaoWhatsApp

Revision ID: add_config_fallback_saudacao
Revises: add_regras_target_fields
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_config_fallback_saudacao'
down_revision = 'add_regras_target_fields'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('whatsapp_configuracao', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'ativar_saudacao_nativa', sa.Boolean(), nullable=True, server_default=sa.true()
        ))
        batch_op.add_column(sa.Column(
            'acao_fallback_padrao', sa.String(50), nullable=True, server_default='ignorar'
        ))
        batch_op.add_column(sa.Column(
            'mensagem_fallback_padrao', sa.Text(), nullable=True
        ))


def downgrade():
    with op.batch_alter_table('whatsapp_configuracao', schema=None) as batch_op:
        batch_op.drop_column('mensagem_fallback_padrao')
        batch_op.drop_column('acao_fallback_padrao')
        batch_op.drop_column('ativar_saudacao_nativa')
