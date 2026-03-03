"""
Script de migração — executar no servidor de produção:
  python migrate.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db

app = create_app()

MIGRATIONS = [
    # Etapa 1 — Número de série nos equipamentos
    ('equipamentos', 'numero_serie',
     'ALTER TABLE equipamentos ADD COLUMN numero_serie VARCHAR(100)'),

    # Etapa 3 — Vínculo com OS em pedidos e transferências
    ('solicitacoes_transferencia', 'os_id',
     'ALTER TABLE solicitacoes_transferencia ADD COLUMN os_id INTEGER REFERENCES ordens_servico(id)'),
    ('pedidos_compra', 'os_id',
     'ALTER TABLE pedidos_compra ADD COLUMN os_id INTEGER REFERENCES ordens_servico(id)'),

    # Etapa 4 — Compras livres (sem item do estoque)
    ('pedidos_compra', 'descricao_livre',
     'ALTER TABLE pedidos_compra ADD COLUMN descricao_livre VARCHAR(300)'),
    ('pedidos_compra', 'categoria_compra',
     'ALTER TABLE pedidos_compra ADD COLUMN categoria_compra VARCHAR(50)'),

    # Equipamentos — QR code externo
    ('equipamentos', 'qrcode_externo',
     'ALTER TABLE equipamentos ADD COLUMN qrcode_externo TEXT'),

    # HistoricoNotificacao — campos de mídia
    ('historico_notificacoes', 'url_midia_local',
     'ALTER TABLE historico_notificacoes ADD COLUMN url_midia_local TEXT'),
    ('historico_notificacoes', 'mensagem_transcrita',
     'ALTER TABLE historico_notificacoes ADD COLUMN mensagem_transcrita TEXT'),
]


def fix_estoque_id_nullable(conn):
    """
    SQLite não suporta ALTER COLUMN.
    Recria pedidos_compra com estoque_id nullable se ainda estiver NOT NULL.
    """
    result = conn.execute(db.text('PRAGMA table_info(pedidos_compra)'))
    rows = result.fetchall()

    # Verifica se estoque_id ainda é NOT NULL (notnull == 1)
    estoque_col = next((r for r in rows if r[1] == 'estoque_id'), None)
    if estoque_col is None:
        print('  [skip] pedidos_compra.estoque_id (coluna não existe?)')
        return
    if estoque_col[3] == 0:
        print('  [skip] pedidos_compra.estoque_id já é nullable')
        return

    print('  [fix]  pedidos_compra.estoque_id — removendo NOT NULL (recriando tabela)...')

    # Detectar colunas existentes para o INSERT SELECT
    col_names = [r[1] for r in rows]
    cols_sql = ', '.join(col_names)

    conn.execute(db.text('PRAGMA foreign_keys = OFF'))
    conn.execute(db.text(f'''
        CREATE TABLE pedidos_compra_new (
            id INTEGER PRIMARY KEY,
            fornecedor_id INTEGER REFERENCES fornecedores(id),
            estoque_id INTEGER REFERENCES estoque(id),
            quantidade NUMERIC(10,3) NOT NULL,
            data_solicitacao DATETIME,
            data_chegada DATETIME,
            status VARCHAR(20),
            solicitante_id INTEGER REFERENCES usuarios(id),
            aprovador_id INTEGER REFERENCES usuarios(id),
            recebedor_id INTEGER REFERENCES usuarios(id),
            token_aprovacao VARCHAR(64) UNIQUE,
            token_expira_em DATETIME,
            justificativa TEXT,
            unidade_destino_id INTEGER REFERENCES unidades(id),
            os_id INTEGER REFERENCES ordens_servico(id),
            descricao_livre VARCHAR(300),
            categoria_compra VARCHAR(50)
        )
    '''))
    conn.execute(db.text(f'INSERT INTO pedidos_compra_new ({cols_sql}) SELECT {cols_sql} FROM pedidos_compra'))
    conn.execute(db.text('DROP TABLE pedidos_compra'))
    conn.execute(db.text('ALTER TABLE pedidos_compra_new RENAME TO pedidos_compra'))
    conn.execute(db.text('PRAGMA foreign_keys = ON'))
    print('  [ok]   pedidos_compra recriada com estoque_id nullable')


def run():
    with app.app_context():
        with db.engine.connect() as conn:
            ok = 0
            skip = 0
            for tabela, coluna, sql in MIGRATIONS:
                result = conn.execute(db.text(f'PRAGMA table_info({tabela})'))
                cols = [row[1] for row in result]
                if coluna in cols:
                    print(f'  [skip] {tabela}.{coluna}')
                    skip += 1
                else:
                    try:
                        conn.execute(db.text(sql))
                        print(f'  [ok]   {tabela}.{coluna} adicionada')
                        ok += 1
                    except Exception as e:
                        print(f'  [erro] {tabela}.{coluna}: {e}')

            # Migração especial: tornar estoque_id nullable em pedidos_compra
            fix_estoque_id_nullable(conn)

            conn.commit()
        print(f'\nConcluído: {ok} colunas adicionadas, {skip} já existiam.')


if __name__ == '__main__':
    run()
