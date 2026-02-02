# GUIA DE INSTALAÇÃO - SISTEMA GMM (Gestão Moderna de Manutenção)

## 📋 SUMÁRIO
1. [Visão Geral](#visão-geral)
2. [Requisitos de Sistema](#requisitos-de-sistema)
3. [Arquivos Necessários](#arquivos-necessários)
4. [Instalação Windows](#instalação-windows)
5. [Instalação Linux](#instalação-linux)
6. [Configuração Inicial](#configuração-inicial)
7. [Inicialização do Sistema](#inicialização-do-sistema)
8. [Verificação da Instalação](#verificação-da-instalação)
9. [Solução de Problemas](#solução-de-problemas)

---

## 📖 VISÃO GERAL

O Sistema GMM é uma aplicação Flask para gestão de manutenção com integração WhatsApp, controle de estoque, ordens de serviço e gestão de terceirizados.

**Características principais:**
- Backend: Flask + SQLAlchemy
- Tarefas assíncronas: Celery + Redis
- Banco de dados: SQLite (desenvolvimento) ou PostgreSQL (produção)
- Integração: WhatsApp via MegaAPI
- Interface web responsiva

---

## 💻 REQUISITOS DE SISTEMA

### Windows
- **Sistema Operacional**: Windows 10/11 ou Windows Server 2016+
- **Python**: 3.9 ou superior
- **Redis**: 5.0 ou superior (via WSL ou Windows build)
- **RAM**: Mínimo 2GB, recomendado 4GB
- **Disco**: 500MB livres (mínimo)
- **Rede**: Acesso à internet para instalação de dependências

### Linux
- **Sistema Operacional**: Ubuntu 20.04+, Debian 11+, CentOS 8+, ou similar
- **Python**: 3.9 ou superior
- **Redis**: 5.0 ou superior
- **RAM**: Mínimo 2GB, recomendado 4GB
- **Disco**: 500MB livres (mínimo)
- **Rede**: Acesso à internet para instalação de dependências

### Opcional (Produção)
- **PostgreSQL**: 12+ (para ambiente de produção)
- **Servidor Web**: Nginx ou Apache (para proxy reverso)
- **Supervisor/Systemd**: Para gerenciar processos em produção

---

## 📦 ARQUIVOS NECESSÁRIOS

### Estrutura de Distribuição

Copie APENAS os seguintes arquivos e pastas do projeto original:

```
gmm/
├── app/                          # Aplicação completa
│   ├── __init__.py
│   ├── extensions.py
│   ├── models/                   # Todos os arquivos
│   ├── routes/                   # Todos os arquivos
│   ├── services/                 # Todos os arquivos
│   ├── tasks/                    # Todos os arquivos
│   ├── utils/                    # Todos os arquivos
│   ├── templates/                # Todas as pastas e arquivos
│   └── static/                   # Todos os arquivos CSS
│       ├── css/
│       └── uploads/              # Criar pastas vazias
│           ├── audios/
│           ├── chamados/
│           └── os/
├── config/
│   └── celery_beat_schedule.py
├── migrations/                   # Todos os arquivos (importante!)
│   ├── env.py
│   ├── script.py.mako
│   ├── alembic.ini
│   └── versions/                 # Todas as migrações
├── config.py                     # Configuração principal
├── run.py                        # Ponto de entrada
├── seed_db.py                    # Script de inicialização
├── init_saldos_estoque.py
├── requirements.txt              # Dependências Python
├── .env.example                  # Template de configuração (criar)
├── install_windows.bat           # Script de instalação Windows
├── install_linux.sh              # Script de instalação Linux
├── start_windows.bat             # Script de inicialização Windows
├── start_linux.sh                # Script de inicialização Linux
└── GUIA_INSTALACAO.md            # Este documento
```

### ❌ NÃO COPIAR
- `venv/` - Ambiente virtual (será criado na instalação)
- `instance/` - Será criado automaticamente
- `.git/` - Repositório Git
- `.claude/` - Arquivos do Claude Code
- `__pycache__/` - Cache Python
- `*.pyc` - Arquivos compilados
- `.env` - Arquivo de configuração local (criar novo)
- `tests/` - Testes (opcional)
- `Doc/` - Documentação (opcional)

---

## 🪟 INSTALAÇÃO WINDOWS

### Método 1: Instalação Automatizada (RECOMENDADO)

1. **Copie os arquivos** listados acima para a máquina destino
2. **Execute o instalador** como Administrador:
   ```cmd
   install_windows.bat
   ```

O script irá:
- ✅ Verificar instalação do Python
- ✅ Criar ambiente virtual
- ✅ Instalar dependências
- ✅ Verificar/instalar Redis
- ✅ Criar arquivo `.env` com configurações padrão
- ✅ Criar estrutura de pastas necessárias
- ✅ Inicializar banco de dados
- ✅ Criar usuário admin padrão

### Método 2: Instalação Manual

#### Passo 1: Instalar Python
1. Baixe Python 3.9+ de [python.org](https://www.python.org/downloads/)
2. Execute o instalador e marque "Add Python to PATH"
3. Verifique a instalação:
   ```cmd
   python --version
   ```

#### Passo 2: Instalar Redis
**Opção A - Redis para Windows:**
1. Baixe Redis para Windows de [github.com/tporadowski/redis/releases](https://github.com/tporadowski/redis/releases)
2. Extraia e execute `redis-server.exe`

**Opção B - Redis via WSL2:**
1. Instale WSL2: `wsl --install`
2. No Ubuntu WSL: `sudo apt update && sudo apt install redis-server`
3. Inicie Redis: `sudo service redis-server start`

#### Passo 3: Criar Ambiente Virtual
```cmd
cd caminho\para\gmm
python -m venv venv
venv\Scripts\activate
```

#### Passo 4: Instalar Dependências
```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

#### Passo 5: Configurar Variáveis de Ambiente
1. Copie `.env.example` para `.env`
2. Edite `.env` com suas configurações (ver seção [Configuração Inicial](#configuração-inicial))

#### Passo 6: Criar Estrutura de Pastas
```cmd
mkdir app\static\uploads\audios
mkdir app\static\uploads\chamados
mkdir app\static\uploads\os
mkdir instance
```

#### Passo 7: Inicializar Banco de Dados
```cmd
flask db upgrade
python seed_db.py
python init_saldos_estoque.py
```

---

## 🐧 INSTALAÇÃO LINUX

### Método 1: Instalação Automatizada (RECOMENDADO)

1. **Copie os arquivos** listados acima para a máquina destino
2. **Dê permissão de execução** e execute:
   ```bash
   chmod +x install_linux.sh
   sudo ./install_linux.sh
   ```

O script irá:
- ✅ Verificar/instalar Python 3.9+
- ✅ Verificar/instalar Redis
- ✅ Criar ambiente virtual
- ✅ Instalar dependências
- ✅ Criar arquivo `.env` com configurações padrão
- ✅ Criar estrutura de pastas necessárias
- ✅ Inicializar banco de dados
- ✅ Criar usuário admin padrão
- ✅ Configurar serviços systemd (opcional)

### Método 2: Instalação Manual

#### Passo 1: Instalar Dependências do Sistema

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**CentOS/RHEL:**
```bash
sudo yum install -y python39 python39-pip redis
sudo systemctl start redis
sudo systemctl enable redis
```

#### Passo 2: Verificar Instalações
```bash
python3 --version  # Deve ser 3.9+
redis-cli ping     # Deve retornar "PONG"
```

#### Passo 3: Criar Ambiente Virtual
```bash
cd /caminho/para/gmm
python3 -m venv venv
source venv/bin/activate
```

#### Passo 4: Instalar Dependências Python
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Passo 5: Configurar Variáveis de Ambiente
```bash
cp .env.example .env
nano .env  # Edite com suas configurações
```

#### Passo 6: Criar Estrutura de Pastas
```bash
mkdir -p app/static/uploads/{audios,chamados,os}
mkdir -p instance
```

#### Passo 7: Ajustar Permissões
```bash
chmod -R 755 app/static/uploads
chmod -R 755 instance
```

#### Passo 8: Inicializar Banco de Dados
```bash
export FLASK_APP=run.py
flask db upgrade
python seed_db.py
python init_saldos_estoque.py
```

---

## ⚙️ CONFIGURAÇÃO INICIAL

### Arquivo `.env`

Crie o arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```bash
# Flask
SECRET_KEY=sua-chave-secreta-super-aleatoria-aqui-mude-isso
FLASK_APP=run.py
FLASK_ENV=production

# Banco de Dados
# Para SQLite (desenvolvimento/pequenas instalações):
# DATABASE_URL=sqlite:///instance/gmm.db

# Para PostgreSQL (produção):
# DATABASE_URL=postgresql://usuario:senha@localhost:5432/gmm

# Redis (Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# WhatsApp MegaAPI (obtenha suas credenciais)
MEGA_API_KEY=sua-chave-api-megaapi-aqui
MEGA_API_URL=https://api.megaapi.com.br/v1/messages

# Criptografia (gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
FERNET_KEY=sua-chave-fernet-32-bytes-aqui

# Email (opcional - para notificações)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-app-gmail
MAIL_DEFAULT_SENDER=seu-email@gmail.com
PURCHASE_EMAIL=compras@suaempresa.com

# Slack (opcional - para alertas)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/seu/webhook/aqui

# OpenAI (opcional - para NLP)
OPENAI_API_KEY=sua-chave-openai-aqui
```

### Gerar Chaves Secretas

**SECRET_KEY:**
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

**FERNET_KEY:**
```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Configurar Rede Local

#### Windows - Permitir Acesso na Rede
1. Abra o Firewall do Windows
2. Adicione regra de entrada para porta 5010 (TCP)
3. Ou execute:
   ```cmd
   netsh advfirewall firewall add rule name="Flask GMM" dir=in action=allow protocol=TCP localport=5010
   ```

#### Linux - Configurar Firewall
```bash
# UFW (Ubuntu)
sudo ufw allow 5010/tcp

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=5010/tcp
sudo firewall-cmd --reload
```

### Descobrir IP da Máquina

**Windows:**
```cmd
ipconfig
```
Procure por "Endereço IPv4" (ex: 192.168.1.100)

**Linux:**
```bash
ip addr show
# ou
hostname -I
```

---

## 🚀 INICIALIZAÇÃO DO SISTEMA

### Windows

#### Método 1: Script Automatizado
```cmd
start_windows.bat
```

Este script abre 3 janelas do terminal:
1. **Flask** - Servidor web na porta 5010
2. **Celery Worker** - Processamento de tarefas
3. **Celery Beat** - Agendador de tarefas

#### Método 2: Manual
Abra 3 terminais separados:

**Terminal 1 - Flask:**
```cmd
cd caminho\para\gmm
venv\Scripts\activate
python run.py
```

**Terminal 2 - Celery Worker:**
```cmd
cd caminho\para\gmm
venv\Scripts\activate
celery -A app.celery worker --loglevel=info --pool=solo
```

**Terminal 3 - Celery Beat:**
```cmd
cd caminho\para\gmm
venv\Scripts\activate
celery -A app.celery beat --loglevel=info
```

### Linux

#### Método 1: Script Automatizado (Foreground)
```bash
chmod +x start_linux.sh
./start_linux.sh
```

#### Método 2: Usando Systemd (Produção)

**Criar arquivo de serviço Flask:**
```bash
sudo nano /etc/systemd/system/gmm-flask.service
```

Conteúdo:
```ini
[Unit]
Description=GMM Flask Application
After=network.target redis.service

[Service]
Type=simple
User=seu-usuario
WorkingDirectory=/caminho/para/gmm
Environment="PATH=/caminho/para/gmm/venv/bin"
ExecStart=/caminho/para/gmm/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Criar arquivo de serviço Celery Worker:**
```bash
sudo nano /etc/systemd/system/gmm-celery.service
```

Conteúdo:
```ini
[Unit]
Description=GMM Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=seu-usuario
WorkingDirectory=/caminho/para/gmm
Environment="PATH=/caminho/para/gmm/venv/bin"
ExecStart=/caminho/para/gmm/venv/bin/celery -A app.celery worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

**Criar arquivo de serviço Celery Beat:**
```bash
sudo nano /etc/systemd/system/gmm-celery-beat.service
```

Conteúdo:
```ini
[Unit]
Description=GMM Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=seu-usuario
WorkingDirectory=/caminho/para/gmm
Environment="PATH=/caminho/para/gmm/venv/bin"
ExecStart=/caminho/para/gmm/venv/bin/celery -A app.celery beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

**Ativar e iniciar serviços:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable gmm-flask gmm-celery gmm-celery-beat
sudo systemctl start gmm-flask gmm-celery gmm-celery-beat
```

**Verificar status:**
```bash
sudo systemctl status gmm-flask
sudo systemctl status gmm-celery
sudo systemctl status gmm-celery-beat
```

---

## ✅ VERIFICAÇÃO DA INSTALAÇÃO

### 1. Verificar Redis
```bash
redis-cli ping
# Deve retornar: PONG
```

### 2. Verificar Flask
Abra o navegador e acesse:
- **Mesmo computador**: http://localhost:5010
- **Outro computador na rede**: http://IP-DO-SERVIDOR:5010

Exemplo: http://192.168.1.100:5010

### 3. Login Padrão
- **Usuário**: admin
- **Senha**: admin123

**⚠️ IMPORTANTE**: Altere a senha padrão imediatamente após o primeiro login!

### 4. Verificar Celery Worker
No terminal do Celery Worker, você deve ver:
```
[tasks]
  . app.tasks.whatsapp_tasks.enviar_whatsapp_task
  . app.tasks.whatsapp_tasks.processar_mensagem_inbound
  . app.tasks.whatsapp_tasks.verificar_saude_whatsapp
  ...
```

### 5. Verificar Logs

**Windows:**
- Flask: Console do terminal 1
- Celery: Console do terminal 2

**Linux com systemd:**
```bash
sudo journalctl -u gmm-flask -f
sudo journalctl -u gmm-celery -f
sudo journalctl -u gmm-celery-beat -f
```

### 6. Testar Funcionalidades Básicas
1. ✅ Login com usuário admin
2. ✅ Criar uma unidade
3. ✅ Criar um técnico
4. ✅ Registrar ponto (entrada/saída)
5. ✅ Criar uma ordem de serviço
6. ✅ Visualizar dashboard

---

## 🔧 SOLUÇÃO DE PROBLEMAS

### Problema: "Python não reconhecido"
**Solução:**
- Windows: Reinstale Python marcando "Add to PATH"
- Linux: `sudo apt install python3` ou `sudo yum install python39`

### Problema: "redis-cli: command not found"
**Solução:**
- Windows: Instale Redis for Windows ou use WSL2
- Linux: `sudo apt install redis-server` ou `sudo yum install redis`

### Problema: "Cannot connect to Redis"
**Solução:**
1. Verifique se Redis está rodando:
   ```bash
   redis-cli ping
   ```
2. Se não responder, inicie Redis:
   - Windows: Execute `redis-server.exe`
   - Linux: `sudo systemctl start redis-server`

### Problema: "Port 5010 already in use"
**Solução:**
1. Encontre o processo usando a porta:
   - Windows: `netstat -ano | findstr :5010`
   - Linux: `sudo lsof -i :5010`
2. Mate o processo ou altere a porta em `run.py`:
   ```python
   app.run(debug=True, port=5001)  # Use porta 5001
   ```

### Problema: "OperationalError: unable to open database file"
**Solução:**
1. Verifique permissões da pasta `instance/`:
   ```bash
   chmod -R 755 instance/
   ```
2. Certifique-se que a pasta existe:
   ```bash
   mkdir -p instance
   ```

### Problema: "No module named 'app'"
**Solução:**
1. Certifique-se que está na pasta raiz do projeto
2. Ative o ambiente virtual:
   - Windows: `venv\Scripts\activate`
   - Linux: `source venv/bin/activate`
3. Reinstale dependências: `pip install -r requirements.txt`

### Problema: Celery não processa tarefas
**Solução:**
1. Verifique se Redis está rodando: `redis-cli ping`
2. Verifique se CELERY_BROKER_URL está correto no `.env`
3. Reinicie Celery Worker

### Problema: Não consigo acessar de outro computador
**Solução:**
1. Verifique firewall (veja [Configurar Rede Local](#configurar-rede-local))
2. Execute Flask em todas as interfaces:
   Edite `run.py`:
   ```python
   app.run(debug=True, host='0.0.0.0', port=5010)
   ```
3. Certifique-se que os computadores estão na mesma rede

### Problema: Erro ao enviar WhatsApp
**Solução:**
1. Verifique se MEGA_API_KEY está configurado no `.env`
2. Verifique se FERNET_KEY foi gerado corretamente
3. Teste a API manualmente com `curl` ou Postman

### Problema: Upload de arquivos falha
**Solução:**
1. Verifique permissões da pasta uploads:
   ```bash
   chmod -R 755 app/static/uploads/
   ```
2. Certifique-se que as subpastas existem:
   ```bash
   mkdir -p app/static/uploads/{audios,chamados,os}
   ```

---

## 📱 ACESSO REMOTO (REDE LOCAL)

### Descobrir IP do Servidor

**Windows:**
```cmd
ipconfig
```
Procure "Endereço IPv4" (exemplo: 192.168.1.100)

**Linux:**
```bash
hostname -I
```

### Acessar de Outros Dispositivos

Em qualquer navegador na mesma rede, acesse:
```
http://IP-DO-SERVIDOR:5010
```

Exemplo:
```
http://192.168.1.100:5010
```

### Testar Conectividade

De outro computador, teste se consegue alcançar o servidor:

**Windows:**
```cmd
ping 192.168.1.100
```

**Linux:**
```bash
ping 192.168.1.100
```

---

## 🔒 SEGURANÇA - CHECKLIST PÓS-INSTALAÇÃO

- [ ] Alterar senha do usuário `admin`
- [ ] Alterar `SECRET_KEY` no `.env`
- [ ] Gerar novo `FERNET_KEY`
- [ ] Configurar HTTPS (produção)
- [ ] Restringir acesso por IP (firewall)
- [ ] Configurar backup automático do banco de dados
- [ ] Desabilitar `debug=True` em produção
- [ ] Configurar níveis de log apropriados
- [ ] Revisar permissões de arquivos e pastas

---

## 📞 SUPORTE

### Logs de Sistema

**Verificar erros:**
- Windows: Verifique os terminais do Flask e Celery
- Linux systemd: `sudo journalctl -u gmm-flask -n 100`

### Comandos Úteis

**Parar todos os processos:**
- Windows: Feche os terminais ou `Ctrl+C` em cada um
- Linux systemd: `sudo systemctl stop gmm-flask gmm-celery gmm-celery-beat`

**Reiniciar sistema:**
- Windows: Feche e execute `start_windows.bat` novamente
- Linux systemd: `sudo systemctl restart gmm-flask gmm-celery gmm-celery-beat`

**Verificar versões:**
```bash
python --version
redis-cli --version
pip list | grep -i flask
```

---

## 🎯 PRÓXIMOS PASSOS

Após a instalação bem-sucedida:

1. **Configurar Unidades**
   - Acesse: Admin > Gestão de Unidades
   - Cadastre suas unidades/filiais

2. **Criar Usuários**
   - Acesse: Admin > Gestão de Usuários
   - Crie técnicos e usuários comuns

3. **Configurar WhatsApp**
   - Acesse: Admin > Configuração WhatsApp
   - Insira sua API Key do MegaAPI
   - Configure regras de automação

4. **Cadastrar Equipamentos**
   - Acesse: Equipamentos
   - Cadastre equipamentos por unidade

5. **Cadastrar Itens de Estoque**
   - Acesse: Estoque
   - Cadastre materiais e ferramentas

6. **Cadastrar Fornecedores**
   - Acesse: Compras > Fornecedores
   - Cadastre fornecedores e catálogo

7. **Cadastrar Terceirizados**
   - Acesse: Terceirizados
   - Cadastre prestadores de serviço externos

---

## 📄 LICENÇA

Sistema GMM - Gestão Moderna de Manutenção
Todos os direitos reservados.

---

**Data da última atualização**: Janeiro 2026
**Versão do documento**: 1.0
