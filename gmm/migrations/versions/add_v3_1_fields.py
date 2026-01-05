"""Add v3.1 fields - historico_notificacoes, ordens_servico, movimentacoes_estoque

Revision ID: add_v3_1_fields
Revises: 3a53dda54dd3
Create Date: 2026-01-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_v3_1_fields'
down_revision = '3a53dda54dd3'
branch_labels = None
depends_on = None


def upgrade():
    # historico_notificacoes - Novos campos para v3.1
    with op.batch_alter_table('historico_notificacoes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('megaapi_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('tipo_conteudo', sa.String(length=20), nullable=True, server_default='text'))
        batch_op.add_column(sa.Column('url_midia_local', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('mimetype', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('caption', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('mensagem_transcrita', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('status_leitura', sa.String(length=20), nullable=True))
        batch_op.create_index('idx_megaapi_id', ['megaapi_id'], unique=False)

    # ordens_servico - Novos campos para v3.1
    with op.batch_alter_table('ordens_servico', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tempo_execucao_minutos', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('origem_criacao', sa.String(length=20), nullable=True, server_default='web'))
        batch_op.add_column(sa.Column('avaliacao', sa.Integer(), nullable=True))

    # movimentacoes_estoque - Novo campo para v3.1
    with op.batch_alter_table('movimentacoes_estoque', schema=None) as batch_op:
        batch_op.add_column(sa.Column('custo_momento', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade():
    # Reverter movimentacoes_estoque
    with op.batch_alter_table('movimentacoes_estoque', schema=None) as batch_op:
        batch_op.drop_column('custo_momento')

    # Reverter ordens_servico
    with op.batch_alter_table('ordens_servico', schema=None) as batch_op:
        batch_op.drop_column('avaliacao')
        batch_op.drop_column('origem_criacao')
        batch_op.drop_column('tempo_execucao_minutos')

    # Reverter historico_notificacoes
    with op.batch_alter_table('historico_notificacoes', schema=None) as batch_op:
        batch_op.drop_index('idx_megaapi_id')
        batch_op.drop_column('status_leitura')
        batch_op.drop_column('mensagem_transcrita')
        batch_op.drop_column('caption')
        batch_op.drop_column('mimetype')
        batch_op.drop_column('url_midia_local')
        batch_op.drop_column('tipo_conteudo')
        batch_op.drop_column('megaapi_id')
