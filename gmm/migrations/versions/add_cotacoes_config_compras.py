"""GMM v4.1 - Cotações de compra e configuração de tiers

Revision ID: add_cotacoes_config_compras
Revises: add_compras_enterprise_v4
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_cotacoes_config_compras'
down_revision = 'add_compras_enterprise_v4'
branch_labels = None
depends_on = None


def upgrade():
    # ── tipo_pedido em pedidos_compra ──────────────────────────────────────
    with op.batch_alter_table('pedidos_compra', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tipo_pedido', sa.String(20), nullable=False, server_default='catalogo'))

    # ── cotacoes_compra ────────────────────────────────────────────────────
    op.create_table('cotacoes_compra',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pedido_id', sa.Integer(), sa.ForeignKey('pedidos_compra.id'), nullable=False),
        sa.Column('fornecedor_nome', sa.String(200), nullable=False),
        sa.Column('valor_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('prazo_dias', sa.Integer(), nullable=True),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('selecionada', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # ── configuracao_compras ───────────────────────────────────────────────
    op.create_table('configuracao_compras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tier1_limite', sa.Numeric(12, 2), server_default='500'),
        sa.Column('tier2_limite', sa.Numeric(12, 2), server_default='5000'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('configuracao_compras')
    op.drop_table('cotacoes_compra')
    with op.batch_alter_table('pedidos_compra', schema=None) as batch_op:
        batch_op.drop_column('tipo_pedido')
