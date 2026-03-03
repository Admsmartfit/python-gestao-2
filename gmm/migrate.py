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
            conn.commit()
        print(f'\nConcluído: {ok} colunas adicionadas, {skip} já existiam.')

if __name__ == '__main__':
    run()
