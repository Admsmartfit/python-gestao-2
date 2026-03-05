# Manual de Teste: Módulo Compras Enterprise (v4.0)

Este guia descreve como validar as correções e as novas funcionalidades do módulo de compras no seu ambiente local Windows utilizando o próprio Antigravity.

## 1. Validar Sincronização Automática (Self-Healing)

A maneira mais fácil de testar é simplesmente iniciar a aplicação. O sistema agora verifica o banco de dados na inicialização.

1.  Abra um terminal na pasta do projeto: `c:\Users\ralan\python gestao 2\gmm`
2.  Ative o ambiente virtual:
    ```powershell
    .\venv\Scripts\activate
    ```
3.  Inicie o servidor Flask:
    ```powershell
    python run.py
    ```
4.  **O que observar:** No console, você não deve ver erros de `OperationalError`. Se o banco estivesse desatualizado, você veria mensagens de log informando que as colunas foram adicionadas.

## 2. Verificação Técnica do Banco de Dados

Para ter certeza absoluta de que todas as 7 colunas e as 6 novas tabelas estão lá, você pode usar o script de diagnóstico que preparei:

1.  No terminal (com venv ativo), execute:
    ```powershell
    python check_all_tables.py
    ```
2.  **Resultado esperado:** Todas as tabelas (`aprovacoes_pedido`, `cotacoes_compra`, etc.) devem retornar `✓ Tudo OK`.

## 3. Teste Funcional da Rota de Aprovações

O erro original acontecia ao acessar o painel de aprovações.

1.  Com o servidor rodando (`python run.py`), abra seu navegador.
2.  Acesse a URL: [http://localhost:5010/compras/aprovacoes](http://localhost:5010/compras/aprovacoes)
3.  **O que observar:**
    - A página deve carregar sem o erro `Internal Server Error`.
    - Se houver pedidos pendentes (Tier 2 ou Tier 3), eles serão listados corretamente.
    - Como agora a coluna `tipo_pedido` existe, a consulta SQL não falhará mais.

## 4. Teste de Configuração de Tiers

O novo módulo exige limites de aprovação (Tier 1 e Tier 2).

1.  Acesse o banco via script rápido para ver se a configuração inicial foi criada:
    ```powershell
    python -c "from app import create_app; from app.models.estoque_models import ConfiguracaoCompras; app=create_app(); [print(f'Tier 1: {c.tier1_limite}, Tier 2: {c.tier2_limite}') for c in ConfiguracaoCompras.query.all()]"
    ```
2.  **Resultado esperado:** Deve imprimir `Tier 1: 500.00, Tier 2: 5000.00`.

---

## 🛠️ Resumo Técnico das Alterações
- **Arquivo de Auto-Cura:** `app/utils/schema_checker.py` (adicionado ao `app/__init__.py`)
- **Script de Migração Oficial:** `migrate.py` (atualizado com v4.0)
- **Tabelas Criadas:** `aprovacoes_pedido`, `faturamentos_compra`, `orcamentos_unidade`, `cotacoes_compra`, `configuracao_compras`, `comunicacoes_fornecedor`.
