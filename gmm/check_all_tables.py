import sqlite3
import os

db_path = r'c:\Users\ralan\python gestao 2\gmm\instance\gmm.db'

if not os.path.exists(db_path):
    print(f"Erro: Banco de dados não encontrado em {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables_to_check = {
    'aprovacoes_pedido': [
        'id', 'pedido_id', 'aprovador_id', 'acao', 'observacao', 'via', 'created_at'
    ],
    'faturamentos_compra': [
        'id', 'pedido_id', 'numero_nf', 'valor_faturado', 'data_vencimento_boleto',
        'linha_digitavel', 'arquivo_nf', 'arquivo_boleto', 'registrado_por_id', 'created_at'
    ],
    'orcamentos_unidade': [
        'id', 'unidade_id', 'ano', 'mes', 'categoria', 'valor_orcado', 'criado_por_id',
        'created_at', 'updated_at'
    ],
    'cotacoes_compra': [
        'id', 'pedido_id', 'fornecedor_nome', 'valor_total', 'prazo_dias', 'observacao',
        'selecionada', 'created_at'
    ],
    'configuracao_compras': [
        'id', 'tier1_limite', 'tier2_limite', 'updated_at', 'updated_by_id'
    ]
}

for table, expected_columns in tables_to_check.items():
    print(f"\nVerificando tabela '{table}':")
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        actual_columns = {col[1] for col in cursor.fetchall()}
        
        if not actual_columns:
            print(f"!!! TABELA '{table}' NÃO EXISTE NO BANCO !!!")
            continue
            
        missing = [col for col in expected_columns if col not in actual_columns]
        if missing:
            print(f"!!! Colunas FALTANTES: {', '.join(missing)}")
        else:
            print("✓ Tudo OK.")
    except Exception as e:
        print(f"Erro ao verificar {table}: {e}")

conn.close()
