"""Add pedido compra fields for Phase 3

Revision ID: add_pedido_compra_fields
Revises: add_v3_1_fields
Create Date: 2026-01-04 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_pedido_compra_fields'
down_revision = 'add_v3_1_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to pedidos_compra
    with op.batch_alter_table('pedidos_compra', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token_aprovacao', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('token_expira_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('justificativa', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('unidade_destino_id', sa.Integer(), nullable=True))
        batch_op.create_index('idx_token_aprovacao', ['token_aprovacao'], unique=True)
        batch_op.create_foreign_key('fk_pedido_compra_unidade_destino', 'unidades', ['unidade_destino_id'], ['id'])


def downgrade():
    # Reverse pedidos_compra changes
    with op.batch_alter_table('pedidos_compra', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pedido_compra_unidade_destino', type_='foreignkey')
        batch_op.drop_index('idx_token_aprovacao')
        batch_op.drop_column('unidade_destino_id')
        batch_op.drop_column('justificativa')
        batch_op.drop_column('token_expira_em')
        batch_op.drop_column('token_aprovacao')
