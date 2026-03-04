"""
Script de limpeza do banco de dados.
Apaga TODOS os dados operacionais, mantendo apenas o usuário admin.

Uso:
    python reset_db.py
    python reset_db.py --usuario admin   # especificar username do admin a manter
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db

app = create_app()

# Tabelas a limpar, na ordem correta (filhos antes de pais)
TABELAS_LIMPAR = [
    'movimentacoes_estoque',
    'solicitacoes_peca',
    'comunicacoes_fornecedor',
    'catalogo_fornecedores',
    'lista_compra_itens',
    'ordens_compra_lista',
    'listas_compra',
    'pedidos_compra',
    'solicitacoes_transferencia',
    'estoque_saldo',
    'estoque',
    'categorias_estoque',
    'anexos_os',
    'ordens_servico',
    'planos_manutencao',
    'equipamentos',
    'registros_ponto',
    'chamados_externos',
    'historico_notificacoes',
    'terceirizados_unidades',   # tabela de associação many-to-many
    'terceirizados',
    'fornecedores',
    'whatsapp_metricas',
    'whatsapp_estados_conversa',
    'whatsapp_tokens_acesso',
    'whatsapp_regras_automacao',
    'whatsapp_configuracao',
    'unidades',
]


def run():
    username_manter = 'admin'
    if '--usuario' in sys.argv:
        idx = sys.argv.index('--usuario')
        if idx + 1 < len(sys.argv):
            username_manter = sys.argv[idx + 1]

    with app.app_context():
        with db.engine.connect() as conn:
            # Salvar dados do admin ANTES de limpar
            result = conn.execute(
                db.text("SELECT * FROM usuarios WHERE username = :u OR tipo = 'admin' LIMIT 1"),
                {'u': username_manter}
            )
            admin_row = result.fetchone()

            if not admin_row:
                print(f"[ERRO] Usuário admin '{username_manter}' não encontrado. Abortando.")
                sys.exit(1)

            admin_cols = list(result.keys()) if hasattr(result, 'keys') else None
            # Guardar como dicionário
            if admin_cols:
                admin = dict(zip(admin_cols, admin_row))
            else:
                # fallback
                col_result = conn.execute(db.text("PRAGMA table_info(usuarios)"))
                cols = [row[1] for row in col_result.fetchall()]
                admin = dict(zip(cols, admin_row))

            print(f"\nAdmin encontrado: {admin.get('nome')} ({admin.get('username')}) — será mantido.\n")

            print("Desativando foreign keys...")
            conn.execute(db.text("PRAGMA foreign_keys = OFF"))

            # Limpar tabelas
            for tabela in TABELAS_LIMPAR:
                try:
                    conn.execute(db.text(f"DELETE FROM {tabela}"))
                    print(f"  [ok]   {tabela} limpa")
                except Exception as e:
                    print(f"  [skip] {tabela}: {e}")

            # Limpar usuários EXCETO o admin
            conn.execute(
                db.text("DELETE FROM usuarios WHERE id != :id"),
                {'id': admin['id']}
            )
            print(f"  [ok]   usuarios — mantido apenas '{admin['username']}'")

            conn.execute(db.text("PRAGMA foreign_keys = ON"))

            # Resetar sequences de autoincrement (SQLite usa sqlite_sequence)
            try:
                for tabela in TABELAS_LIMPAR:
                    conn.execute(
                        db.text("DELETE FROM sqlite_sequence WHERE name = :t"),
                        {'t': tabela}
                    )
                # Resetar sequence de usuarios mas manter o id do admin
                conn.execute(
                    db.text("UPDATE sqlite_sequence SET seq = :id WHERE name = 'usuarios'"),
                    {'id': admin['id']}
                )
                print("\n  [ok]   sequences resetadas")
            except Exception as e:
                print(f"\n  [skip] reset de sequences: {e}")

            conn.commit()

        print(f"\n✅ Banco limpo com sucesso!")
        print(f"   Admin mantido: {admin.get('nome')} / {admin.get('username')} (id={admin.get('id')})")
        print(f"\n⚠  Lembre de executar 'python migrate.py' no servidor para garantir colunas atualizadas.\n")


if __name__ == '__main__':
    resposta = input(
        "⚠️  ATENÇÃO: Isto apagará TODOS os dados operacionais do banco.\n"
        "   Somente o usuário admin será mantido.\n"
        "   Digite 'CONFIRMAR' para prosseguir: "
    )
    if resposta.strip().upper() != 'CONFIRMAR':
        print("Operação cancelada.")
        sys.exit(0)
    run()
