"""
reset_banco.py — Limpa dados operacionais do banco GMM.
Mantém: usuários, unidades e parâmetros de configuração.
Uso: python reset_banco.py
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Tabelas que NÃO serão apagadas
# ──────────────────────────────────────────────
TABELAS_PRESERVADAS = {
    'usuarios',               # Contas de usuário
    'unidades',               # Unidades / filiais
    'configuracao_compras',   # Tiers de aprovação (R$ mínimos)
    'whatsapp_configuracao',  # Configuração do bot WhatsApp
    'whatsapp_regras_automacao',  # Regras/menus do bot
    'whatsapp_tokens_acesso',     # Tokens de conexão WhatsApp
}

# ──────────────────────────────────────────────
# Ordem de deleção (filhos antes dos pais)
# para evitar conflitos de FK mesmo com OFF
# ──────────────────────────────────────────────
ORDEM_DELECAO = [
    'cotacoes_compra',
    'aprovacoes_pedido',
    'faturamentos_compra',
    'orcamentos_unidade',
    'ordens_compra_lista',
    'lista_compra_itens',
    'listas_compra',
    'solicitacoes_peca',
    'solicitacoes_transferencia',
    'movimentacoes_estoque',
    'pedidos_compra',
    'comunicacoes_fornecedor',
    'catalogo_fornecedores',
    'fornecedores',
    'estoque_saldo',
    'estoque',
    'categorias_estoque',
    'anexos_os',
    'ordens_servico',
    'planos_manutencao',
    'equipamentos',
    'historico_notificacoes',
    'chamados_externos',
    'terceirizados',
    'whatsapp_estados_conversa',
    'whatsapp_metricas',
    'registros_ponto',
]


def encontrar_banco() -> Path:
    """Localiza o arquivo .db a partir do DATABASE_URL ou caminho padrão."""
    load_dotenv(Path(__file__).parent / '.env')
    url = os.environ.get('DATABASE_URL', '')

    if url.startswith('sqlite:///'):
        caminho = url.replace('sqlite:///', '')
        p = Path(caminho)
        if not p.is_absolute():
            p = Path(__file__).parent / caminho
        return p

    # Caminho padrão
    return Path(__file__).parent / 'instance' / 'gmm.db'


def fazer_backup(db_path: Path) -> Path:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bkp = db_path.with_name(f'gmm_backup_{ts}.db')
    shutil.copy2(db_path, bkp)
    return bkp


def listar_tabelas(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def contar_registros(conn: sqlite3.Connection, tabela: str) -> int:
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM '{tabela}'")
        return cur.fetchone()[0]
    except Exception:
        return -1


def main():
    db_path = encontrar_banco()

    print("\n" + "═" * 58)
    print("  GMM — Reset de Banco de Dados")
    print("═" * 58)

    if not db_path.exists():
        print(f"\n❌  Banco não encontrado: {db_path}")
        sys.exit(1)

    print(f"\n  Banco      : {db_path}")
    print(f"  Tamanho    : {db_path.stat().st_size / 1024:.1f} KB")

    conn = sqlite3.connect(db_path)
    todas_tabelas = listar_tabelas(conn)

    # Descobrir tabelas a apagar (presentes no banco e não preservadas)
    apagar = [t for t in ORDEM_DELECAO if t in todas_tabelas]
    # Incluir tabelas não previstas na lista de ordem (se houver)
    extras = [t for t in todas_tabelas if t not in TABELAS_PRESERVADAS and t not in apagar]
    apagar += extras

    print("\n  ┌── TABELAS PRESERVADAS ─────────────────────────┐")
    for t in sorted(TABELAS_PRESERVADAS):
        if t in todas_tabelas:
            n = contar_registros(conn, t)
            print(f"  │  ✅  {t:<40} {n:>4} reg.")
    print("  └─────────────────────────────────────────────────┘")

    print("\n  ┌── TABELAS QUE SERÃO LIMPAS ────────────────────┐")
    totais = {}
    for t in apagar:
        n = contar_registros(conn, t)
        totais[t] = n
        flag = '⚠ ' if n > 0 else '  '
        print(f"  │ {flag} {t:<40} {n:>4} reg.")
    print("  └─────────────────────────────────────────────────┘")

    total_apagar = sum(v for v in totais.values() if v > 0)
    print(f"\n  Total de registros a remover: {total_apagar}")

    if total_apagar == 0:
        print("\n  ℹ️   Banco já está vazio. Nada a fazer.\n")
        conn.close()
        return

    print("\n  ⚠️   Esta operação é IRREVERSÍVEL após confirmar.")
    print("       Um backup automático será criado antes.")
    resp = input("\n  Digite CONFIRMAR para continuar: ").strip()

    if resp != 'CONFIRMAR':
        print("\n  ❌  Operação cancelada.\n")
        conn.close()
        return

    # Backup
    bkp = fazer_backup(db_path)
    print(f"\n  💾  Backup salvo em: {bkp.name}")

    # Deletar
    print("\n  🗑️   Apagando registros...")
    conn.execute("PRAGMA foreign_keys = OFF")
    erros = []
    for t in apagar:
        try:
            conn.execute(f"DELETE FROM '{t}'")
            # Resetar auto-increment
            conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        except Exception as e:
            erros.append((t, str(e)))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("VACUUM")
    conn.commit()
    conn.close()

    print("  ✅  Concluído!")
    if erros:
        print("\n  ⚠️   Erros (não críticos):")
        for t, e in erros:
            print(f"       {t}: {e}")

    db_final = db_path.stat().st_size / 1024
    print(f"\n  Tamanho final: {db_final:.1f} KB")
    print("\n  O sistema está pronto para ser populado com novos dados.")
    print("═" * 58 + "\n")


if __name__ == '__main__':
    main()
