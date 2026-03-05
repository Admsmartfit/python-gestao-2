import sqlite3
import os

db_path = r'c:\Users\ralan\python gestao 2\gmm\instance\gmm.db'

if not os.path.exists(db_path):
    print(f"Erro: Banco de dados não encontrado em {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(pedidos_compra)")
columns = {col[1] for col in cursor.fetchall()}

model_columns = [
    "id", "fornecedor_id", "estoque_id", "quantidade", "data_solicitacao",
    "data_chegada", "status", "solicitante_id", "aprovador_id", "recebedor_id",
    "token_aprovacao", "token_expira_em", "justificativa", "unidade_destino_id",
    "os_id", "descricao_livre", "categoria_compra", "ordem_lista_id",
    "valor_unitario_estimado", "valor_total_estimado", "tier_aprovacao",
    "data_entrega_prevista", "data_recebimento", "rating_fornecedor", "tipo_pedido"
]

missing = [col for col in model_columns if col not in columns]

print("Colunas presentes:")
for col in sorted(list(columns)):
    print(f"- {col}")

print("\nColunas FALTANTES no banco (definidas no modelo):")
for col in missing:
    print(f"!!! {col}")

conn.close()
