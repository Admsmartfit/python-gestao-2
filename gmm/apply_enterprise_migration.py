from app import create_app, db
from sqlalchemy import text
import sys

def apply_migration():
    app = create_app()
    with app.app_context():
        print("Iniciando migração para Compras Enterprise (v4.0)...")
        
        columns_to_add = [
            ("valor_unitario_estimado", "NUMERIC(12, 2)"),
            ("valor_total_estimado", "NUMERIC(12, 2)"),
            ("tier_aprovacao", "INTEGER"),
            ("data_entrega_prevista", "DATETIME"),
            ("data_recebimento", "DATETIME"),
            ("rating_fornecedor", "INTEGER"),
            ("tipo_pedido", "VARCHAR(20) DEFAULT 'catalogo'")
        ]
        
        with db.engine.connect() as conn:
            for col_name, col_type in columns_to_add:
                try:
                    query = text(f"ALTER TABLE pedidos_compra ADD COLUMN {col_name} {col_type}")
                    conn.execute(query)
                    conn.commit()
                    print(f"✓ Coluna '{col_name}' adicionada com sucesso.")
                except Exception as e:
                    if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                        print(f"⚠ Coluna '{col_name}' já existe.")
                    else:
                        print(f"✗ Erro ao adicionar '{col_name}': {e}")
            
        print("\nMigração concluída.")

if __name__ == "__main__":
    apply_migration()
