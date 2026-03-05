from sqlalchemy import text

def check_db_schema(app, db):
    """
    Verifica e corrige inconsistências no esquema do banco de dados (Self-Healing).
    Útil para quando migrações manuais não foram executadas no servidor.
    """
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # 1. Verificar colunas em pedidos_compra
                result = conn.execute(text("PRAGMA table_info(pedidos_compra)"))
                columns = [row[1] for row in result]
                
                required_pedidos = [
                    ('valor_unitario_estimado', 'NUMERIC(12, 2)'),
                    ('valor_total_estimado', 'NUMERIC(12, 2)'),
                    ('tier_aprovacao', 'INTEGER'),
                    ('data_entrega_prevista', 'DATETIME'),
                    ('data_recebimento', 'DATETIME'),
                    ('rating_fornecedor', 'INTEGER'),
                    ('tipo_pedido', "VARCHAR(20) DEFAULT 'catalogo'")
                ]
                
                for col_name, col_type in required_pedidos:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE pedidos_compra ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            app.logger.info(f"Self-Healing: Coluna '{col_name}' adicionada a 'pedidos_compra'.")
                        except Exception as e:
                            app.logger.error(f"Erro ao adicionar coluna {col_name}: {e}")

                # 2. Verificar colunas em fornecedores
                result = conn.execute(text("PRAGMA table_info(fornecedores)"))
                columns = [row[1] for row in result]
                
                required_fornecedores = [
                    ('whatsapp', 'VARCHAR(20)'),
                    ('cnpj', 'VARCHAR(20)'),
                    ('forma_contato_alternativa', 'TEXT')
                ]
                
                for col_name, col_type in required_fornecedores:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE fornecedores ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            app.logger.info(f"Self-Healing: Coluna '{col_name}' adicionada a 'fornecedores'.")
                        except Exception as e:
                            app.logger.error(f"Erro ao adicionar coluna {col_name}: {e}")
                
                # 3. Garantir que as novas tabelas existam
                # create_all() não deleta dados, apenas cria tabelas que não existem
                db.create_all()
                
        except Exception as e:
            app.logger.error(f"Erro durante check_db_schema: {e}")
