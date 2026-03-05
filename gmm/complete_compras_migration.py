from app import create_app, db
from app.models.estoque_models import *
from sqlalchemy import text
import sys

def complete_migration():
    app = create_app()
    with app.app_context():
        print("🚀 Iniciando finalização da migração do módulo Compras (v4.0)...")
        
        # 1. Criar Tabelas Faltantes
        # SQLAlchemy detecta os modelos se forem importados
        db.create_all()
        print("✅ Tabelas criadas/verificadas.")
        
        # 2. Adicionar colunas faltantes em tabelas existentes
        columns_to_add = {
            "fornecedores": [
                ("whatsapp", "VARCHAR(20)"),
                ("cnpj", "VARCHAR(20)"),
                ("forma_contato_alternativa", "TEXT")
            ],
            "pedidos_compra": [
                ("valor_unitario_estimado", "NUMERIC(12, 2)"),
                ("valor_total_estimado", "NUMERIC(12, 2)"),
                ("tier_aprovacao", "INTEGER"),
                ("data_entrega_prevista", "DATETIME"),
                ("data_recebimento", "DATETIME"),
                ("rating_fornecedor", "INTEGER"),
                ("tipo_pedido", "VARCHAR(20) DEFAULT 'catalogo'")
            ]
        }
        
        with db.engine.connect() as conn:
            for table, cols in columns_to_add.items():
                for col_name, col_type in cols:
                    try:
                        query = text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                        conn.execute(query)
                        conn.commit()
                        print(f"✅ [{table}] Coluna '{col_name}' adicionada.")
                    except Exception as e:
                        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                            pass
                        else:
                            print(f"❌ [{table}] Erro ao adicionar '{col_name}': {e}")

        # 3. Inicializar ConfiguracaoCompras
        try:
            if not ConfiguracaoCompras.query.first():
                cfg = ConfiguracaoCompras(tier1_limite=500, tier2_limite=5000)
                db.session.add(cfg)
                db.session.commit()
                print("✅ Configurações de Compras inicializadas (Tier 1: 500, Tier 2: 5000).")
        except Exception as e:
            print(f"❌ Erro ao inicializar configurações: {e}")
            
        print("\n✨ Migração finalizada com sucesso!")

if __name__ == "__main__":
    complete_migration()
