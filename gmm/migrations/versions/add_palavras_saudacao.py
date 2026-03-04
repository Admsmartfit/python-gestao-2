"""Add palavras_saudacao to ConfiguracaoWhatsApp

Revision ID: add_palavras_saudacao
Revises: add_config_fallback_saudacao
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_palavras_saudacao'
down_revision = 'add_config_fallback_saudacao'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('whatsapp_configuracao', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'palavras_saudacao', sa.Text(), nullable=True,
            server_default='OI,OLA,OLÁ,MENU,#MENU,BOM DIA,BOA TARDE,BOA NOITE'
        ))


def downgrade():
    with op.batch_alter_table('whatsapp_configuracao', schema=None) as batch_op:
        batch_op.drop_column('palavras_saudacao')
