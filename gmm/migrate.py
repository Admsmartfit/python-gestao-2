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

    # Etapa 5 — Fornecedor pré-definido em itens de lista padrão
    ('lista_compra_itens', 'fornecedor_id',
     'ALTER TABLE lista_compra_itens ADD COLUMN fornecedor_id INTEGER REFERENCES fornecedores(id)'),

    # Etapa 5 — Vínculo de pedido individual com OrdemCompraLista
    ('pedidos_compra', 'ordem_lista_id',
     'ALTER TABLE pedidos_compra ADD COLUMN ordem_lista_id INTEGER REFERENCES ordens_compra_lista(id)'),

    # Etapa 6 — Regras de automação WhatsApp: notificação e para_desconhecidos
    ('whatsapp_regras_automacao', 'notificar_usuario_id',
     'ALTER TABLE whatsapp_regras_automacao ADD COLUMN notificar_usuario_id INTEGER'),
    ('whatsapp_regras_automacao', 'para_desconhecidos',
     'ALTER TABLE whatsapp_regras_automacao ADD COLUMN para_desconhecidos BOOLEAN DEFAULT 1'),

    # v4.0 Compras Enterprise — Fornecedores
    ('fornecedores', 'whatsapp', 'ALTER TABLE fornecedores ADD COLUMN whatsapp VARCHAR(20)'),
    ('fornecedores', 'cnpj', 'ALTER TABLE fornecedores ADD COLUMN cnpj VARCHAR(20)'),
    ('fornecedores', 'forma_contato_alternativa', 'ALTER TABLE fornecedores ADD COLUMN forma_contato_alternativa TEXT'),

    # v4.0/4.1 Compras Enterprise — Pedidos
    ('pedidos_compra', 'valor_unitario_estimado', 'ALTER TABLE pedidos_compra ADD COLUMN valor_unitario_estimado NUMERIC(12, 2)'),
    ('pedidos_compra', 'valor_total_estimado', 'ALTER TABLE pedidos_compra ADD COLUMN valor_total_estimado NUMERIC(12, 2)'),
    ('pedidos_compra', 'tier_aprovacao', 'ALTER TABLE pedidos_compra ADD COLUMN tier_aprovacao INTEGER'),
    ('pedidos_compra', 'data_entrega_prevista', 'ALTER TABLE pedidos_compra ADD COLUMN data_entrega_prevista DATETIME'),
    ('pedidos_compra', 'data_recebimento', 'ALTER TABLE pedidos_compra ADD COLUMN data_recebimento DATETIME'),
    ('pedidos_compra', 'rating_fornecedor', 'ALTER TABLE pedidos_compra ADD COLUMN rating_fornecedor INTEGER'),
    ('pedidos_compra', 'tipo_pedido', "ALTER TABLE pedidos_compra ADD COLUMN tipo_pedido VARCHAR(20) DEFAULT 'catalogo'"),

    # v4.2 WhatsApp — Configuração e Regras
    ('whatsapp_configuracao', 'ativar_saudacao_nativa', 'ALTER TABLE whatsapp_configuracao ADD COLUMN activar_saudacao_nativa BOOLEAN DEFAULT 1'),
    ('whatsapp_configuracao', 'acao_fallback_padrao', "ALTER TABLE whatsapp_configuracao ADD COLUMN acao_fallback_padrao VARCHAR(50) DEFAULT 'ignorar'"),
    ('whatsapp_configuracao', 'mensagem_fallback_padrao', 'ALTER TABLE whatsapp_configuracao ADD COLUMN mensagem_fallback_padrao TEXT'),
    ('whatsapp_configuracao', 'palavras_saudacao', "ALTER TABLE whatsapp_configuracao ADD COLUMN palavras_saudacao TEXT DEFAULT 'OI,OLA,OLÁ,MENU,#MENU,BOM DIA,BOA TARDE,BOA NOITE'"),
    
    ('whatsapp_regras_automacao', 'tipo_resposta', "ALTER TABLE whatsapp_regras_automacao ADD COLUMN tipo_resposta VARCHAR(30) DEFAULT 'texto'"),
    ('whatsapp_regras_automacao', 'resposta_estruturada', 'ALTER TABLE whatsapp_regras_automacao ADD COLUMN resposta_estruturada TEXT'),
    ('whatsapp_regras_automacao', 'para_terceirizados', 'ALTER TABLE whatsapp_regras_automacao ADD COLUMN para_terceirizados BOOLEAN DEFAULT 1'),
    ('whatsapp_regras_automacao', 'para_usuarios', 'ALTER TABLE whatsapp_regras_automacao ADD COLUMN para_usuarios BOOLEAN DEFAULT 1'),

    ('whatsapp_estados_conversa', 'usuario_tipo', 'ALTER TABLE whatsapp_estados_conversa ADD COLUMN usuario_tipo VARCHAR(20)'),
    ('whatsapp_estados_conversa', 'usuario_id', 'ALTER TABLE whatsapp_estados_conversa ADD COLUMN usuario_id INTEGER'),
    ('whatsapp_estados_conversa', 'ordem_servico_id', 'ALTER TABLE whatsapp_estados_conversa ADD COLUMN ordem_servico_id INTEGER'),
]


def create_new_tables(conn):
    """Cria tabelas novas que ainda não existem no banco de produção."""
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS listas_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome VARCHAR(100) NOT NULL,
            descricao TEXT,
            periodicidade_dias INTEGER,
            criador_id INTEGER REFERENCES usuarios(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ativo BOOLEAN DEFAULT 1
        )
    '''))
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS lista_compra_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lista_id INTEGER NOT NULL REFERENCES listas_compra(id),
            estoque_id INTEGER REFERENCES estoque(id),
            descricao_livre VARCHAR(300),
            quantidade NUMERIC(10,3) NOT NULL DEFAULT 1,
            categoria_compra VARCHAR(50),
            fornecedor_id INTEGER REFERENCES fornecedores(id)
        )
    '''))
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS ordens_compra_lista (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lista_id INTEGER REFERENCES listas_compra(id),
            nome VARCHAR(200) NOT NULL,
            solicitante_id INTEGER REFERENCES usuarios(id),
            unidade_destino_id INTEGER REFERENCES unidades(id),
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            observacao TEXT
        )
    '''))
    
    # Compras Enterprise v4.0 Tables
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS aprovacoes_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL REFERENCES pedidos_compra(id),
            aprovador_id INTEGER NOT NULL REFERENCES usuarios(id),
            acao VARCHAR(20) NOT NULL,
            observacao TEXT,
            via VARCHAR(20) DEFAULT 'web',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS faturamentos_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL UNIQUE REFERENCES pedidos_compra(id),
            numero_nf VARCHAR(50),
            valor_faturado NUMERIC(12, 2),
            data_vencimento_boleto DATE,
            linha_digitavel VARCHAR(100),
            arquivo_nf VARCHAR(300),
            arquivo_boleto VARCHAR(300),
            registrado_por_id INTEGER REFERENCES usuarios(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS orcamentos_unidade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unidade_id INTEGER NOT NULL REFERENCES unidades(id),
            ano INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            categoria VARCHAR(50),
            valor_orcado NUMERIC(12, 2) NOT NULL DEFAULT 0,
            criado_por_id INTEGER REFERENCES usuarios(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS cotacoes_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL REFERENCES pedidos_compra(id),
            fornecedor_nome VARCHAR(200) NOT NULL,
            valor_total NUMERIC(12, 2) NOT NULL,
            prazo_dias INTEGER,
            observacao TEXT,
            selecionada BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    
    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS configuracao_compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tier1_limite NUMERIC(12, 2) DEFAULT 500,
            tier2_limite NUMERIC(12, 2) DEFAULT 5000,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by_id INTEGER REFERENCES usuarios(id)
        )
    '''))

    conn.execute(db.text('''
        CREATE TABLE IF NOT EXISTS comunicacoes_fornecedor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_compra_id INTEGER NOT NULL REFERENCES pedidos_compra(id),
            fornecedor_id INTEGER NOT NULL REFERENCES fornecedores(id),
            tipo_comunicacao VARCHAR(20) NOT NULL,
            direcao VARCHAR(10) NOT NULL,
            mensagem TEXT,
            status VARCHAR(20) DEFAULT 'pendente',
            resposta TEXT,
            data_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_resposta DATETIME
        )
    '''))
    
    print('  [ok]   Tabelas Enterprise (CREATE IF NOT EXISTS)')


def fix_registros_ponto_unidade_nullable(conn):
    """
    Torna unidade_id nullable em registros_ponto (ponto agora é opcional).
    SQLite não suporta ALTER COLUMN — recria a tabela.
    """
    result = conn.execute(db.text('PRAGMA table_info(registros_ponto)'))
    rows = result.fetchall()

    unidade_col = next((r for r in rows if r[1] == 'unidade_id'), None)
    if unidade_col is None:
        print('  [skip] registros_ponto.unidade_id (coluna não encontrada)')
        return
    if unidade_col[3] == 0:
        print('  [skip] registros_ponto.unidade_id já é nullable')
        return

    print('  [fix]  registros_ponto.unidade_id — removendo NOT NULL...')
    col_names = [r[1] for r in rows]
    cols_sql = ', '.join(col_names)

    conn.execute(db.text('PRAGMA foreign_keys = OFF'))
    conn.execute(db.text(f'''
        CREATE TABLE registros_ponto_new (
            id INTEGER PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            unidade_id INTEGER REFERENCES unidades(id),
            data_hora_entrada DATETIME NOT NULL,
            data_hora_saida DATETIME,
            ip_origem_entrada VARCHAR(45),
            ip_origem_saida VARCHAR(45),
            latitude NUMERIC(10,8),
            longitude NUMERIC(11,8),
            observacoes TEXT
        )
    '''))
    conn.execute(db.text(f'INSERT INTO registros_ponto_new ({cols_sql}) SELECT {cols_sql} FROM registros_ponto'))
    conn.execute(db.text('DROP TABLE registros_ponto'))
    conn.execute(db.text('ALTER TABLE registros_ponto_new RENAME TO registros_ponto'))
    conn.execute(db.text('PRAGMA foreign_keys = ON'))
    print('  [ok]   registros_ponto recriada com unidade_id nullable')


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

            # Migração especial: tornar unidade_id nullable em registros_ponto
            fix_registros_ponto_unidade_nullable(conn)

            # Criar novas tabelas (listas de compra padrão)
            create_new_tables(conn)

            conn.commit()
        print(f'\nConcluído: {ok} colunas adicionadas, {skip} já existiam.')


if __name__ == '__main__':
    run()
