#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para aplicar migração: adicionar campos de fornecedor e tabela de comunicações
"""

import sqlite3
import os
import sys

# Caminho do banco de dados
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'gmm.db')

def aplicar_migracao():
    """Aplica as migrações necessárias no banco de dados"""

    if not os.path.exists(DB_PATH):
        print(f"❌ Banco de dados não encontrado em: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("🔧 Aplicando migrações...")

        # 1. Adicionar campo forma_contato_alternativa na tabela fornecedores
        try:
            cursor.execute("""
                ALTER TABLE fornecedores
                ADD COLUMN forma_contato_alternativa TEXT
            """)
            print("✅ Campo 'forma_contato_alternativa' adicionado à tabela fornecedores")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  Campo 'forma_contato_alternativa' já existe")
            else:
                raise

        # 2. Criar tabela comunicacoes_fornecedor
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comunicacoes_fornecedor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_compra_id INTEGER NOT NULL,
                fornecedor_id INTEGER NOT NULL,
                tipo_comunicacao VARCHAR(20) NOT NULL,
                direcao VARCHAR(10) NOT NULL,
                mensagem TEXT,
                status VARCHAR(20) DEFAULT 'pendente',
                resposta TEXT,
                data_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_resposta DATETIME,
                FOREIGN KEY (pedido_compra_id) REFERENCES pedidos_compra (id),
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (id)
            )
        """)
        print("✅ Tabela 'comunicacoes_fornecedor' criada")

        # 3. Criar índices para melhor performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_comunicacoes_pedido
            ON comunicacoes_fornecedor(pedido_compra_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_comunicacoes_fornecedor_fk
            ON comunicacoes_fornecedor(fornecedor_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_comunicacoes_data
            ON comunicacoes_fornecedor(data_envio DESC)
        """)
        print("✅ Índices criados")

        # Commit das alterações
        conn.commit()

        print("\n✨ Migrações aplicadas com sucesso!")
        return True

    except Exception as e:
        print(f"\n❌ Erro ao aplicar migrações: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

def verificar_estrutura():
    """Verifica se as alterações foram aplicadas corretamente"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("\n🔍 Verificando estrutura do banco...")

        # Verificar coluna forma_contato_alternativa
        cursor.execute("PRAGMA table_info(fornecedores)")
        colunas = [col[1] for col in cursor.fetchall()]

        if 'forma_contato_alternativa' in colunas:
            print("✅ Campo 'forma_contato_alternativa' encontrado")
        else:
            print("❌ Campo 'forma_contato_alternativa' NÃO encontrado")

        # Verificar tabela comunicacoes_fornecedor
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='comunicacoes_fornecedor'
        """)

        if cursor.fetchone():
            print("✅ Tabela 'comunicacoes_fornecedor' encontrada")

            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM comunicacoes_fornecedor")
            count = cursor.fetchone()[0]
            print(f"   📊 Registros: {count}")
        else:
            print("❌ Tabela 'comunicacoes_fornecedor' NÃO encontrada")

        conn.close()

    except Exception as e:
        print(f"❌ Erro ao verificar estrutura: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRAÇÃO: Fornecedores e Comunicações")
    print("=" * 60)

    if aplicar_migracao():
        verificar_estrutura()
        print("\n✅ Script concluído com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Script falhou!")
        sys.exit(1)
