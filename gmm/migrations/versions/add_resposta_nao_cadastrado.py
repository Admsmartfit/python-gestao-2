"""Add resposta_nao_cadastrado fields to ConfiguracaoWhatsApp

Revision ID: add_resposta_nao_cadastrado
Revises: add_whatsapp_respostas
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_resposta_nao_cadastrado'
down_revision = 'add_whatsapp_respostas'
branch_labels = None
depends_on = None

TEXTO_PADRAO = (
    "⚠️ *Telefone não cadastrado*\n\n"
    "Seu número não está registrado no sistema GMM.\n\n"
    "Entre em contato com o administrador para solicitar cadastro."
)


def upgrade():
    with op.batch_alter_table('whatsapp_configuracao', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'resposta_nao_cadastrado_ativa',
            sa.Boolean(),
            nullable=True,
            server_default=sa.true()
        ))
        batch_op.add_column(sa.Column(
            'resposta_nao_cadastrado_texto',
            sa.Text(),
            nullable=True,
            server_default=TEXTO_PADRAO
        ))


def downgrade():
    with op.batch_alter_table('whatsapp_configuracao', schema=None) as batch_op:
        batch_op.drop_column('resposta_nao_cadastrado_texto')
        batch_op.drop_column('resposta_nao_cadastrado_ativa')
