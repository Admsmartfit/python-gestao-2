"""
Migração: adicionar coluna 'ativo' na tabela fornecedores.
Executar no servidor: python migrate_fornecedor_ativo.py
"""
from app import create_app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE fornecedores ADD COLUMN ativo BOOLEAN DEFAULT 1"))
            conn.commit()
            logger.info("Coluna 'ativo' adicionada a tabela 'fornecedores'.")
    except Exception as e:
        logger.info(f"Coluna 'ativo' provavelmente ja existe: {e}")

    # Garantir que todos os fornecedores existentes fiquem ativos
    try:
        with db.engine.connect() as conn:
            conn.execute(text("UPDATE fornecedores SET ativo = 1 WHERE ativo IS NULL"))
            conn.commit()
            logger.info("Fornecedores existentes marcados como ativos.")
    except Exception as e:
        logger.error(f"Erro ao atualizar fornecedores: {e}")

    logger.info("Migracao concluida!")
