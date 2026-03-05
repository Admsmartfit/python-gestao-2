"""GMM v4.0 - Compras Enterprise: novos modelos e campos

Revision ID: add_compras_enterprise_v4
Revises: add_tipo_resposta_estruturada
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_compras_enterprise_v4'
down_revision = 'add_tipo_resposta_estruturada'
branch_labels = None
depends_on = None


def upgrade():
    # ── Novos campos em pedidos_compra ─────────────────────────────────────
    with op.batch_alter_table('pedidos_compra', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valor_unitario_estimado', sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column('valor_total_estimado', sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column('tier_aprovacao', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('data_entrega_prevista', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('data_recebimento', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('rating_fornecedor', sa.Integer(), nullable=True))

    # ── aprovacoes_pedido ──────────────────────────────────────────────────
    op.create_table('aprovacoes_pedido',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pedido_id', sa.Integer(), sa.ForeignKey('pedidos_compra.id'), nullable=False),
        sa.Column('aprovador_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('acao', sa.String(20), nullable=False),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('via', sa.String(20), server_default='web'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # ── faturamentos_compra ────────────────────────────────────────────────
    op.create_table('faturamentos_compra',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pedido_id', sa.Integer(), sa.ForeignKey('pedidos_compra.id'), nullable=False),
        sa.Column('numero_nf', sa.String(50), nullable=True),
        sa.Column('valor_faturado', sa.Numeric(12, 2), nullable=True),
        sa.Column('data_vencimento_boleto', sa.Date(), nullable=True),
        sa.Column('linha_digitavel', sa.String(100), nullable=True),
        sa.Column('arquivo_nf', sa.String(300), nullable=True),
        sa.Column('arquivo_boleto', sa.String(300), nullable=True),
        sa.Column('registrado_por_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pedido_id')
    )

    # ── orcamentos_unidade ─────────────────────────────────────────────────
    op.create_table('orcamentos_unidade',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), sa.ForeignKey('unidades.id'), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('categoria', sa.String(50), nullable=True),
        sa.Column('valor_orcado', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('criado_por_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('orcamentos_unidade')
    op.drop_table('faturamentos_compra')
    op.drop_table('aprovacoes_pedido')
    with op.batch_alter_table('pedidos_compra', schema=None) as batch_op:
        batch_op.drop_column('rating_fornecedor')
        batch_op.drop_column('data_recebimento')
        batch_op.drop_column('data_entrega_prevista')
        batch_op.drop_column('tier_aprovacao')
        batch_op.drop_column('valor_total_estimado')
        batch_op.drop_column('valor_unitario_estimado')
