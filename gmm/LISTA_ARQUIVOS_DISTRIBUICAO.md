# LISTA DE ARQUIVOS PARA DISTRIBUIÇÃO - SISTEMA GMM

## 📦 CHECKLIST DE PREPARAÇÃO DO PACOTE

Este documento lista EXATAMENTE quais arquivos e pastas você deve copiar do projeto de desenvolvimento para criar um pacote de distribuição/instalação em outro computador.

---

## ✅ ARQUIVOS OBRIGATÓRIOS

### 📄 Arquivos Raiz
```
✅ config.py                        # Configuração principal do Flask
✅ run.py                           # Ponto de entrada da aplicação
✅ requirements.txt                 # Dependências Python
✅ seed_db.py                       # Script de inicialização do banco
✅ init_saldos_estoque.py          # Inicialização de saldos
✅ .env.example                     # Template de configuração
✅ GUIA_INSTALACAO.md              # Guia de instalação completo
✅ LISTA_ARQUIVOS_DISTRIBUICAO.md  # Este arquivo
✅ install_windows.bat              # Instalador Windows
✅ install_linux.sh                 # Instalador Linux
✅ start_windows.bat                # Inicializador Windows
✅ start_linux.sh                   # Inicializador Linux
```

### 📁 Pasta `app/` (COMPLETA)
```
✅ app/
   ✅ __init__.py                   # Factory da aplicação
   ✅ extensions.py                 # Extensões Flask

   ✅ models/                       # Todos os modelos
      ✅ __init__.py
      ✅ models.py
      ✅ estoque_models.py
      ✅ terceirizados_models.py
      ✅ whatsapp_models.py

   ✅ routes/                       # Todas as rotas
      ✅ __init__.py
      ✅ admin.py
      ✅ admin_whatsapp.py
      ✅ analytics.py
      ✅ auth.py
      ✅ compras.py
      ✅ equipamentos.py
      ✅ estoque.py
      ✅ notifications.py
      ✅ os.py
      ✅ ponto.py
      ✅ search.py
      ✅ terceirizados.py
      ✅ webhook.py
      ✅ whatsapp.py

   ✅ services/                     # Todos os serviços
      ✅ alerta_service.py
      ✅ analytics_service.py
      ✅ circuit_breaker.py
      ✅ comando_executores.py
      ✅ comando_parser.py
      ✅ email_service.py
      ✅ estado_service.py
      ✅ estoque_service.py
      ✅ media_downloader_service.py
      ✅ nlp_service.py
      ✅ os_service.py
      ✅ pdf_generator_service.py
      ✅ qr_service.py
      ✅ rate_limiter.py
      ✅ roteamento_service.py
      ✅ sms_service.py
      ✅ template_service.py
      ✅ whatsapp_service.py
      ✅ README_WHATSAPP.md          # Documentação do módulo WhatsApp

   ✅ tasks/                        # Tarefas Celery
      ✅ __init__.py
      ✅ system_tasks.py
      ✅ whatsapp_tasks.py

   ✅ utils/                        # Utilitários
      ✅ decorators.py

   ✅ templates/                    # TODOS os templates HTML
      ✅ base.html
      ✅ login.html
      ✅ registrar.html
      ✅ dashboard.html
      ✅ ponto.html
      ✅ chamados.html
      ✅ chamado_detalhe.html
      ✅ os_nova.html
      ✅ os_detalhes.html
      ✅ equipamentos_lista.html
      ✅ equipamento_detalhe.html
      ✅ estoque.html
      ✅ admin_config.html
      ✅ admin_unidades.html
      ✅ compras.html

      ✅ admin/                     # Templates admin
         ✅ chat_central.html
         ✅ relatorio_movimentacoes.html
         ✅ transferencias.html
         ✅ whatsapp_config.html
         ✅ whatsapp_dashboard.html
         ✅ whatsapp_regras.html

      ✅ analytics/                 # Templates analytics
         ✅ dashboard.html
         ✅ performance_tecnica.html

      ✅ compras/                   # Templates compras
         ✅ detalhes.html
         ✅ lista.html
         ✅ novo.html

      ✅ estoque/                   # Templates estoque
         ✅ dashboard.html
         ✅ movimentacoes.html

      ✅ terceirizados/             # Templates terceirizados
         ✅ central_mensagens.html
         ✅ listar_prestadores.html

      ✅ whatsapp/                  # Templates WhatsApp
         ✅ confirmacao.html
         ✅ erro.html

   ✅ static/                       # Arquivos estáticos
      ✅ css/
         ✅ style.css               # CSS principal

      ✅ uploads/                   # Criar pastas VAZIAS
         ✅ audios/                 # (vazia)
         ✅ chamados/               # (vazia)
         ✅ os/                     # (vazia)
```

### 📁 Pasta `config/`
```
✅ config/
   ✅ celery_beat_schedule.py      # Agendamento Celery
```

### 📁 Pasta `migrations/` (CRÍTICO!)
```
✅ migrations/                      # Sistema de migrações Alembic
   ✅ env.py
   ✅ script.py.mako
   ✅ alembic.ini

   ✅ versions/                     # TODAS as migrações
      ✅ 01f80cfb9012_adiciona_abrangencia_e_unidades_a_.py
      ✅ 1414d4af1853_add_health_status_to_.py
      ✅ 3a53dda54dd3_add_criado_em_to_historiconotificacao.py
      ✅ 415b1ea5b49d_add_routing_fields_to_regrasautomacao.py
      ✅ 4ac78186cf98_allow_nullable_chamado_id_in_.py
      ✅ 5294e772d5ef_add_ssid_wifi_to_unidades.py
      ✅ add_pedido_compra_fields.py
      ✅ add_v3_1_fields.py
      ✅ afacfdb19cc8_add_unidade_id_to_terceirizado.py
      ✅ c54b967eeaeb_add_whatsapp_module_models.py
      ✅ f9d8c9ff71cf_modulo_3_terceirizados.py
```

---

## ❌ ARQUIVOS QUE NÃO DEVEM SER COPIADOS

### 🚫 Pastas Geradas (serão criadas automaticamente)
```
❌ venv/                           # Ambiente virtual (criar novo)
❌ instance/                       # Banco de dados (criar novo)
❌ __pycache__/                    # Cache Python
❌ *.pyc                           # Arquivos compilados
❌ .pytest_cache/                  # Cache de testes
❌ logs/                           # Logs (criar se necessário)
```

### 🚫 Arquivos de Configuração Local
```
❌ .env                            # Configurações locais (criar novo com .env.example)
❌ .env.backup.*                   # Backups de configuração
❌ celerybeat-schedule             # Agendamento Celery (será criado)
❌ celerybeat-schedule.db          # Base de dados do Beat
```

### 🚫 Controle de Versão e IDE
```
❌ .git/                           # Repositório Git
❌ .gitignore
❌ .claude/                        # Arquivos Claude Code
❌ .vscode/                        # Configurações VSCode
❌ .idea/                          # Configurações PyCharm
```

### 🚫 Documentação e Testes (OPCIONAL)
```
⚠️  tests/                         # Testes unitários (opcional)
⚠️  Doc/                           # Documentação (opcional)
⚠️  CLAUDE.md                      # Guia Claude (opcional)
⚠️  prd.md, prd 2.txt              # Documentos PRD (opcional)
⚠️  *.md (outros)                  # Outros markdowns (opcional)
```

### 🚫 Scripts de Atualização (desenvolvimento)
```
❌ seed_modulo2.py                 # Seeding específico
❌ update_db_schema.py             # Atualizações de schema
❌ update_db_unidades.py           # Atualizações de unidades
```

---

## 📋 PROCEDIMENTO DE PREPARAÇÃO DO PACOTE

### Método 1: Cópia Manual (Recomendado para primeira vez)

1. **Crie uma pasta limpa para distribuição:**
   ```bash
   # Windows
   mkdir C:\gmm-distribuicao

   # Linux
   mkdir ~/gmm-distribuicao
   ```

2. **Copie os arquivos obrigatórios seguindo a lista acima**

3. **Crie as pastas vazias:**
   ```bash
   # Windows
   mkdir app\static\uploads\audios
   mkdir app\static\uploads\chamados
   mkdir app\static\uploads\os
   mkdir instance

   # Linux
   mkdir -p app/static/uploads/{audios,chamados,os}
   mkdir -p instance
   ```

4. **Verifique se TODAS as migrações estão presentes**

5. **Comprima para distribuição:**
   - Windows: Clique direito > Enviar para > Pasta compactada
   - Linux: `tar -czf gmm-sistema.tar.gz gmm-distribuicao/`

### Método 2: Script Automatizado (Windows)

Crie um arquivo `preparar_pacote.bat`:

```batch
@echo off
set DEST=C:\gmm-distribuicao
echo Criando pacote de distribuicao...

mkdir "%DEST%"

REM Copiar arquivos raiz
xcopy /Y config.py "%DEST%\"
xcopy /Y run.py "%DEST%\"
xcopy /Y requirements.txt "%DEST%\"
xcopy /Y seed_db.py "%DEST%\"
xcopy /Y init_saldos_estoque.py "%DEST%\"
xcopy /Y .env.example "%DEST%\"
xcopy /Y *.md "%DEST%\"
xcopy /Y *.bat "%DEST%\"
xcopy /Y *.sh "%DEST%\"

REM Copiar pastas
xcopy /E /I /Y app "%DEST%\app"
xcopy /E /I /Y config "%DEST%\config"
xcopy /E /I /Y migrations "%DEST%\migrations"

REM Criar pastas vazias
mkdir "%DEST%\instance"
mkdir "%DEST%\app\static\uploads\audios"
mkdir "%DEST%\app\static\uploads\chamados"
mkdir "%DEST%\app\static\uploads\os"

REM Limpar cache
del /S /Q "%DEST%\*.pyc" 2>nul
for /d /r "%DEST%" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo Pacote criado em: %DEST%
echo Agora compacte a pasta para distribuicao
pause
```

### Método 3: Script Automatizado (Linux)

Crie um arquivo `preparar_pacote.sh`:

```bash
#!/bin/bash

DEST=~/gmm-distribuicao
echo "Criando pacote de distribuicao..."

mkdir -p "$DEST"

# Copiar arquivos raiz
cp config.py run.py requirements.txt seed_db.py init_saldos_estoque.py "$DEST/"
cp .env.example *.md *.bat *.sh "$DEST/" 2>/dev/null || true

# Copiar pastas
cp -r app config migrations "$DEST/"

# Criar pastas vazias
mkdir -p "$DEST/instance"
mkdir -p "$DEST/app/static/uploads"/{audios,chamados,os}

# Limpar cache
find "$DEST" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -type f -name "*.pyc" -delete 2>/dev/null || true

# Comprimir
cd ~
tar -czf gmm-sistema.tar.gz gmm-distribuicao/

echo "Pacote criado e comprimido: ~/gmm-sistema.tar.gz"
echo "Tamanho do pacote:"
ls -lh ~/gmm-sistema.tar.gz
```

Dar permissão e executar:
```bash
chmod +x preparar_pacote.sh
./preparar_pacote.sh
```

---

## 📦 ESTRUTURA FINAL DO PACOTE

Após seguir o procedimento, sua pasta de distribuição deve ter esta estrutura:

```
gmm-distribuicao/
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models/          (4 arquivos .py)
│   ├── routes/          (13 arquivos .py)
│   ├── services/        (18 arquivos .py + 1 .md)
│   ├── tasks/           (3 arquivos .py)
│   ├── utils/           (1 arquivo .py)
│   ├── templates/       (32+ arquivos .html)
│   └── static/
│       ├── css/style.css
│       └── uploads/     (pastas vazias)
├── config/
│   └── celery_beat_schedule.py
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   ├── alembic.ini
│   └── versions/        (11 arquivos de migração)
├── instance/            (pasta vazia)
├── config.py
├── run.py
├── requirements.txt
├── seed_db.py
├── init_saldos_estoque.py
├── .env.example
├── GUIA_INSTALACAO.md
├── LISTA_ARQUIVOS_DISTRIBUICAO.md
├── install_windows.bat
├── install_linux.sh
├── start_windows.bat
└── start_linux.sh
```

---

## ✅ CHECKLIST DE VERIFICAÇÃO FINAL

Antes de distribuir, verifique:

- [ ] Todos os arquivos `.py` da pasta `app/` estão presentes
- [ ] Todos os 13 arquivos de rotas estão na pasta `routes/`
- [ ] Todos os 18 serviços estão na pasta `services/`
- [ ] Todos os templates HTML estão presentes (32+ arquivos)
- [ ] O arquivo `style.css` está em `app/static/css/`
- [ ] Todas as 11 migrações estão em `migrations/versions/`
- [ ] O arquivo `requirements.txt` está presente
- [ ] Os scripts de instalação (.bat e .sh) estão presentes
- [ ] Os scripts de inicialização (.bat e .sh) estão presentes
- [ ] O arquivo `.env.example` está presente (NÃO o .env!)
- [ ] O `GUIA_INSTALACAO.md` está presente
- [ ] As pastas vazias foram criadas (instance, uploads)
- [ ] NÃO há pasta `venv/` no pacote
- [ ] NÃO há arquivos `.pyc` ou `__pycache__/`
- [ ] NÃO há arquivo `.env` (apenas .env.example)
- [ ] NÃO há pasta `.git/`

---

## 📊 TAMANHO ESPERADO DO PACOTE

**Descomprimido**: ~2-5 MB
**Comprimido (.zip ou .tar.gz)**: ~500 KB - 1 MB

Se o tamanho for muito maior, provavelmente incluiu pastas desnecessárias como `venv/` ou `.git/`.

---

## 🚀 PRÓXIMOS PASSOS APÓS CRIAR O PACOTE

1. **Teste em um ambiente limpo:**
   - Crie uma VM ou use outro computador
   - Descompacte o pacote
   - Execute o instalador
   - Verifique se tudo funciona

2. **Documente versão:**
   - Anote a data de criação do pacote
   - Se usar Git, anote o commit hash
   - Crie um arquivo `VERSAO.txt` com essas informações

3. **Distribua:**
   - Compartilhe o arquivo comprimido
   - Inclua o `GUIA_INSTALACAO.md` separadamente se necessário
   - Forneça suporte inicial se possível

---

**Data de criação deste documento**: Janeiro 2026
**Versão**: 1.0
