from app import create_app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

def add_column_if_not_exists(table, column, definition):
    try:
        with db.engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
            conn.commit()
            logger.info(f"Column '{column}' added to table '{table}'.")
    except Exception as e:
        logger.info(f"Column '{column}' in '{table}' probably already exists or error: {e}")

with app.app_context():
    logger.info("Starting database migration for Sprint 1...")
    
    # 1. Equipamentos
    add_column_if_not_exists('equipamentos', 'status', "VARCHAR(20) DEFAULT 'operacional'")
    add_column_if_not_exists('equipamentos', 'codigo', "VARCHAR(50)")
    add_column_if_not_exists('equipamentos', 'descricao', "TEXT")
    add_column_if_not_exists('equipamentos', 'data_aquisicao', "DATETIME")
    add_column_if_not_exists('equipamentos', 'custo_aquisicao', "NUMERIC(10, 2)")

    # 2. OrdemServico
    add_column_if_not_exists('ordens_servico', 'data_inicio', "DATETIME")
    add_column_if_not_exists('ordens_servico', 'tempo_execucao_minutos', "INTEGER DEFAULT 0")
    add_column_if_not_exists('ordens_servico', 'origem_criacao', "VARCHAR(50) DEFAULT 'sistema'")
    add_column_if_not_exists('ordens_servico', 'data_prevista', "DATETIME")

    # 3. PedidoCompra
    add_column_if_not_exists('pedidos_compra', 'valor_total', "NUMERIC(10, 2) DEFAULT 0")
    add_column_if_not_exists('pedidos_compra', 'numero_pedido', "VARCHAR(20)")

    # 4. Fornecedores
    add_column_if_not_exists('fornecedores', 'whatsapp', "VARCHAR(20)")
    add_column_if_not_exists('fornecedores', 'cnpj', "VARCHAR(20)")

    logger.info("Migration completed.")
