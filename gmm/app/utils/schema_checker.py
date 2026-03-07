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
                
                # 3. Verificar colunas em planos_manutencao
                result = conn.execute(text("PRAGMA table_info(planos_manutencao)"))
                columns = [row[1] for row in result]

                if 'unidade_id' not in columns:
                    try:
                        conn.execute(text("ALTER TABLE planos_manutencao ADD COLUMN unidade_id INTEGER REFERENCES unidades(id)"))
                        conn.commit()
                        app.logger.info("Self-Healing: Coluna 'unidade_id' adicionada a 'planos_manutencao'.")
                    except Exception as e:
                        app.logger.error(f"Erro ao adicionar coluna unidade_id em planos_manutencao: {e}")

                # 3b. Verificar colunas em cotacoes_compra
                result = conn.execute(text("PRAGMA table_info(cotacoes_compra)"))
                columns = [row[1] for row in result]

                if 'link_produto' not in columns:
                    try:
                        conn.execute(text("ALTER TABLE cotacoes_compra ADD COLUMN link_produto VARCHAR(500)"))
                        conn.commit()
                        app.logger.info("Self-Healing: Coluna 'link_produto' adicionada a 'cotacoes_compra'.")
                    except Exception as e:
                        app.logger.error(f"Erro ao adicionar coluna link_produto: {e}")

                # 4. Verificar colunas em whatsapp_configuracao
                result = conn.execute(text("PRAGMA table_info(whatsapp_configuracao)"))
                columns = [row[1] for row in result]
                
                required_whatsapp_config = [
                    ('ativar_saudacao_nativa', 'BOOLEAN DEFAULT 1'),
                    ('acao_fallback_padrao', "VARCHAR(50) DEFAULT 'ignorar'"),
                    ('mensagem_fallback_padrao', 'TEXT'),
                    ('palavras_saudacao', "TEXT DEFAULT 'OI,OLA,OLÁ,MENU,#MENU,BOM DIA,BOA TARDE,BOA NOITE'")
                ]
                
                for col_name, col_type in required_whatsapp_config:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE whatsapp_configuracao ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            app.logger.info(f"Self-Healing: Coluna '{col_name}' adicionada a 'whatsapp_configuracao'.")
                        except Exception as e:
                            app.logger.error(f"Erro ao adicionar coluna {col_name} em whatsapp_configuracao: {e}")

                # 5. Verificar colunas em whatsapp_regras_automacao
                result = conn.execute(text("PRAGMA table_info(whatsapp_regras_automacao)"))
                columns = [row[1] for row in result]
                
                required_whatsapp_regras = [
                    ('tipo_resposta', "VARCHAR(30) DEFAULT 'texto'"),
                    ('resposta_estruturada', 'TEXT'),
                    ('para_terceirizados', 'BOOLEAN DEFAULT 1'),
                    ('para_usuarios', 'BOOLEAN DEFAULT 1')
                ]
                
                for col_name, col_type in required_whatsapp_regras:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE whatsapp_regras_automacao ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            app.logger.info(f"Self-Healing: Coluna '{col_name}' adicionada a 'whatsapp_regras_automacao'.")
                        except Exception as e:
                            app.logger.error(f"Erro ao adicionar coluna {col_name} em whatsapp_regras_automacao: {e}")

                # 6. Verificar colunas em whatsapp_estados_conversa
                result = conn.execute(text("PRAGMA table_info(whatsapp_estados_conversa)"))
                columns = [row[1] for row in result]
                
                required_whatsapp_estados = [
                    ('usuario_tipo', 'VARCHAR(20)'),
                    ('usuario_id', 'INTEGER'),
                    ('ordem_servico_id', 'INTEGER')
                ]
                
                for col_name, col_type in required_whatsapp_estados:
                    if col_name not in columns:
                        try:
                            # Tentar foreign keys se suportado/necessário, mas focus é nas colunas para evitar OperationalError
                            conn.execute(text(f"ALTER TABLE whatsapp_estados_conversa ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            app.logger.info(f"Self-Healing: Coluna '{col_name}' adicionada a 'whatsapp_estados_conversa'.")
                        except Exception as e:
                            app.logger.error(f"Erro ao adicionar coluna {col_name} em whatsapp_estados_conversa: {e}")

                # 7. Garantir que as novas tabelas existam
                # create_all() não deleta dados, apenas cria tabelas que não existem
                db.create_all()
                
        except Exception as e:
            app.logger.error(f"Erro durante check_db_schema: {e}")
