"""Add WhatsApp automatic responses fields

Revision ID: add_whatsapp_respostas
Revises: add_pedido_compra_fields
Create Date: 2026-01-07

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_whatsapp_respostas'
down_revision = 'add_pedido_compra_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to whatsapp_estados_conversa
    with op.batch_alter_table('whatsapp_estados_conversa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('usuario_tipo', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('usuario_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ordem_servico_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_estado_conversa_os', 'ordens_servico', ['ordem_servico_id'], ['id'])

    # Add new columns to chamados_externos
    with op.batch_alter_table('chamados_externos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('solicitante_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('atualizado_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('concluido_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('observacao_conclusao', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('motivo_recusa', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('data_agendamento', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('endereco', sa.String(300), nullable=True))
        batch_op.add_column(sa.Column('cliente_nome', sa.String(150), nullable=True))
        batch_op.create_foreign_key('fk_chamado_solicitante', 'usuarios', ['solicitante_id'], ['id'])

    # Create solicitacoes_peca table
    op.create_table('solicitacoes_peca',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ordem_servico_id', sa.Integer(), nullable=False),
        sa.Column('estoque_id', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Numeric(10, 3), nullable=False),
        sa.Column('status', sa.String(30), default='aguardando_separacao'),
        sa.Column('solicitante_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('separado_em', sa.DateTime(), nullable=True),
        sa.Column('separado_por_id', sa.Integer(), nullable=True),
        sa.Column('entregue_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ordem_servico_id'], ['ordens_servico.id'], ),
        sa.ForeignKeyConstraint(['estoque_id'], ['estoque.id'], ),
        sa.ForeignKeyConstraint(['separado_por_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop solicitacoes_peca table
    op.drop_table('solicitacoes_peca')

    # Remove columns from chamados_externos
    with op.batch_alter_table('chamados_externos', schema=None) as batch_op:
        batch_op.drop_constraint('fk_chamado_solicitante', type_='foreignkey')
        batch_op.drop_column('cliente_nome')
        batch_op.drop_column('endereco')
        batch_op.drop_column('data_agendamento')
        batch_op.drop_column('motivo_recusa')
        batch_op.drop_column('observacao_conclusao')
        batch_op.drop_column('concluido_em')
        batch_op.drop_column('atualizado_em')
        batch_op.drop_column('solicitante_id')

    # Remove columns from whatsapp_estados_conversa
    with op.batch_alter_table('whatsapp_estados_conversa', schema=None) as batch_op:
        batch_op.drop_constraint('fk_estado_conversa_os', type_='foreignkey')
        batch_op.drop_column('ordem_servico_id')
        batch_op.drop_column('usuario_id')
        batch_op.drop_column('usuario_tipo')
