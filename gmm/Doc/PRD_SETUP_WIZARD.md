# PRD: GMM Setup Wizard (Versão Linux)
**Versão:** 2.0
**Data:** 2026-01-27
**Autor:** Sistema GMM

---

## 1. Objetivo

Simplificar a implantação do GMM em servidores Linux, substituindo a edição manual de arquivos de texto por uma **interface web interativa** que:
- Valida conexões em tempo real
- Gera chaves de segurança automaticamente
- Testa configurações antes de salvar
- Previne configurações incorretas com validação passo a passo

---

## 2. Arquitetura do Módulo

### 2.1. Localização dos Arquivos

```
gmm/
├── app/
│   ├── __init__.py                    # ← Verificação inicial do .env
│   └── routes/
│       └── setup.py                   # ← NOVO: Blueprint do Setup Wizard
├── app/templates/
│   └── setup/
│       ├── welcome.html               # ← NOVO: Tela inicial
│       ├── step1_environment.html     # ← NOVO: Verificação de ambiente
│       ├── step2_security.html        # ← NOVO: Chaves de segurança
│       ├── step3_database.html        # ← NOVO: Configuração de DB
│       ├── step4_connectivity.html    # ← NOVO: WhatsApp e Email
│       ├── step5_ai.html              # ← NOVO: OpenAI (opcional)
│       └── complete.html              # ← NOVO: Finalização
├── instance/
│   ├── gmm.db                         # ← Banco SQLite (se escolhido)
│   └── setup.lock                     # ← Arquivo de trava (gerado)
├── .env                               # ← Arquivo de configuração (gerado)
└── run.py                             # ← Entry point modificado
```

### 2.2. Fluxo de Execução

```
┌─────────────────┐
│  Usuário inicia │
│   python run.py │
└────────┬────────┘
         │
         ▼
┌────────────────────┐
│ app/__init__.py    │ ◄── MODIFICAR AQUI
│ verifica .env      │
└────────┬───────────┘
         │
    ┌────┴────┐
    │ Existe? │
    └────┬────┘
         │
    ┌────┴────────────────┐
    │ SIM               NÃO│
    ▼                     ▼
┌─────────────┐   ┌──────────────────┐
│ Carrega app │   │ Redireciona para │
│ normalmente │   │ /setup           │
└─────────────┘   └────────┬─────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Setup Wizard    │ ◄── CRIAR NOVO
                  │ (setup.py)      │
                  └─────────────────┘
```

### 2.3. Gatilho de Ativação

**Modificar em:** `c:\Users\ralan\python gestao 2\gmm\app\__init__.py`

```python
import os
from flask import Flask, redirect, url_for, request
from pathlib import Path

def create_app():
    app = Flask(__name__)

    # VERIFICAÇÃO DE SETUP
    env_file = Path(__file__).parent.parent / '.env'
    setup_lock = Path(__file__).parent.parent / 'instance' / 'setup.lock'

    # Se .env não existe e não estamos na rota de setup, redirecionar
    @app.before_request
    def check_setup():
        if not env_file.exists() and not request.path.startswith('/setup'):
            return redirect(url_for('setup.welcome'))

        # Se setup já foi feito, bloquear acesso à rota /setup
        if env_file.exists() and request.path.startswith('/setup'):
            if setup_lock.exists():
                return "Setup já foi concluído. Delete o arquivo .env para reconfigurar.", 403

    # Registrar blueprint de setup ANTES de outros
    from app.routes.setup import bp as setup_bp
    app.register_blueprint(setup_bp)

    # Continua registro normal...
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        # ... resto da configuração

    return app
```

**Por que fazer assim?**
- `before_request`: Intercepta TODAS as requisições antes de processar
- Verifica `.env` ANTES de carregar configurações
- Permite que `/setup` funcione sem variáveis de ambiente

---

## 3. Requisitos Funcionais (Passo a Passo Detalhado)

### Etapa 1: Verificação de Ambiente Linux

#### 3.1.1. Objetivo
Garantir que o sistema tem os pré-requisitos mínimos para rodar o GMM.

#### 3.1.2. Implementação

**Criar arquivo:** `c:\Users\ralan\python gestao 2\gmm\app\routes\setup.py`

```python
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from pathlib import Path
import os
import sys
import subprocess
import secrets
from cryptography.fernet import Fernet

bp = Blueprint('setup', __name__, url_prefix='/setup')

@bp.route('/')
def welcome():
    """Tela inicial do Setup Wizard"""
    return render_template('setup/welcome.html')

@bp.route('/step1')
def step1_environment():
    """Verificação de ambiente e permissões"""
    checks = {
        'python_version': sys.version_info >= (3, 8),
        'write_permission': check_write_permission(),
        'redis_running': check_redis(),
        'disk_space': check_disk_space()
    }
    return render_template('setup/step1_environment.html', checks=checks)

def check_write_permission():
    """Verifica se pode escrever o arquivo .env"""
    env_path = Path(__file__).parent.parent.parent / '.env'
    try:
        # Tenta criar arquivo de teste
        test_file = env_path.parent / '.test_write'
        test_file.write_text('test')
        test_file.unlink()
        return True
    except Exception as e:
        return False

def check_redis():
    """Verifica se Redis está rodando"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        r.ping()
        return True
    except:
        return False

def check_disk_space():
    """Verifica espaço em disco (mínimo 1GB)"""
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        return free > 1_000_000_000  # 1GB
    except:
        return False
```

#### 3.1.3. Template de Exemplo

**Criar:** `c:\Users\ralan\python gestao 2\gmm\app\templates\setup\step1_environment.html`

```html
{% extends "base_setup.html" %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Etapa 1: Verificação de Ambiente</h4>
                </div>
                <div class="card-body">
                    <p class="text-muted">Verificando pré-requisitos do sistema...</p>

                    <!-- Checklist de Verificações -->
                    <ul class="list-group">
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span><i class="bi bi-python"></i> Python 3.8+</span>
                            {% if checks.python_version %}
                            <span class="badge bg-success">✓ OK</span>
                            {% else %}
                            <span class="badge bg-danger">✗ Erro</span>
                            {% endif %}
                        </li>

                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span><i class="bi bi-shield-lock"></i> Permissão de Escrita</span>
                            {% if checks.write_permission %}
                            <span class="badge bg-success">✓ OK</span>
                            {% else %}
                            <span class="badge bg-danger">✗ Erro</span>
                            <small class="text-danger d-block">Execute: chmod +w .</small>
                            {% endif %}
                        </li>

                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span><i class="bi bi-database"></i> Redis (Celery)</span>
                            {% if checks.redis_running %}
                            <span class="badge bg-success">✓ OK</span>
                            {% else %}
                            <span class="badge bg-warning">⚠ Opcional</span>
                            <small class="text-muted d-block">Inicie: sudo systemctl start redis</small>
                            {% endif %}
                        </li>

                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span><i class="bi bi-hdd"></i> Espaço em Disco (1GB+)</span>
                            {% if checks.disk_space %}
                            <span class="badge bg-success">✓ OK</span>
                            {% else %}
                            <span class="badge bg-danger">✗ Insuficiente</span>
                            {% endif %}
                        </li>
                    </ul>

                    <!-- Botões de Navegação -->
                    <div class="d-flex justify-content-between mt-4">
                        <a href="{{ url_for('setup.welcome') }}" class="btn btn-secondary">← Voltar</a>
                        {% if checks.python_version and checks.write_permission %}
                        <a href="{{ url_for('setup.step2_security') }}" class="btn btn-primary">Avançar →</a>
                        {% else %}
                        <button class="btn btn-primary" disabled>Corrija os erros para continuar</button>
                        {% endif %}
                    </div>
                </div>
            </div>

            <!-- Card de Ajuda -->
            <div class="card mt-3 border-info">
                <div class="card-body">
                    <h6 class="text-info"><i class="bi bi-info-circle"></i> Comandos Úteis Linux</h6>
                    <pre class="bg-light p-2 rounded"><code># Verificar Python
python3 --version

# Instalar Redis
sudo apt-get install redis-server
sudo systemctl start redis

# Dar permissão de escrita
sudo chown $USER:$USER /caminho/para/gmm
chmod +w /caminho/para/gmm</code></pre>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

#### 3.1.4. Exemplo de Uso

**Como o usuário vê:**
1. Acessa `http://localhost:5000/setup`
2. Vê checklist verde/vermelho em tempo real
3. Se algo falhar, vê comando exato para corrigir
4. Só pode avançar quando requisitos obrigatórios estão OK

---

### Etapa 2: Segurança e Chaves (Auto-Geradas)

#### 3.2.1. Objetivo
Gerar chaves criptográficas seguras automaticamente, sem depender do usuário.

#### 3.2.2. Implementação

**Adicionar em:** `c:\Users\ralan\python gestao 2\gmm\app\routes\setup.py`

```python
@bp.route('/step2', methods=['GET', 'POST'])
def step2_security():
    """Geração de chaves de segurança"""
    if request.method == 'POST':
        # Salvar na sessão para uso posterior
        from flask import session
        session['SECRET_KEY'] = request.form.get('secret_key')
        session['FERNET_KEY'] = request.form.get('fernet_key')
        return redirect(url_for('setup.step3_database'))

    # Gerar chaves automaticamente
    secret_key = secrets.token_hex(32)
    fernet_key = Fernet.generate_key().decode()

    return render_template('setup/step2_security.html',
                         secret_key=secret_key,
                         fernet_key=fernet_key)

@bp.route('/api/regenerate-keys', methods=['POST'])
def regenerate_keys():
    """API para regenerar chaves via AJAX"""
    return jsonify({
        'secret_key': secrets.token_hex(32),
        'fernet_key': Fernet.generate_key().decode()
    })
```

#### 3.2.3. Template de Exemplo

**Criar:** `c:\Users\ralan\python gestao 2\gmm\app\templates\setup\step2_security.html`

```html
{% extends "base_setup.html" %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Etapa 2: Chaves de Segurança</h4>
                </div>
                <div class="card-body">
                    <p class="text-muted">Chaves criptográficas geradas automaticamente</p>

                    <form method="POST">
                        <!-- SECRET_KEY -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">
                                <i class="bi bi-key"></i> SECRET_KEY
                                <small class="text-muted">(Flask Session)</small>
                            </label>
                            <div class="input-group">
                                <input type="text" class="form-control font-monospace"
                                       id="secretKey" name="secret_key"
                                       value="{{ secret_key }}" readonly>
                                <button type="button" class="btn btn-outline-secondary"
                                        onclick="copyToClipboard('secretKey')">
                                    <i class="bi bi-clipboard"></i>
                                </button>
                            </div>
                            <small class="form-text text-muted">
                                Usada para proteger sessões e cookies. Mantém usuários logados com segurança.
                            </small>
                        </div>

                        <!-- FERNET_KEY -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">
                                <i class="bi bi-shield-lock"></i> FERNET_KEY
                                <small class="text-muted">(Criptografia de Dados)</small>
                            </label>
                            <div class="input-group">
                                <input type="text" class="form-control font-monospace"
                                       id="fernetKey" name="fernet_key"
                                       value="{{ fernet_key }}" readonly>
                                <button type="button" class="btn btn-outline-secondary"
                                        onclick="copyToClipboard('fernetKey')">
                                    <i class="bi bi-clipboard"></i>
                                </button>
                            </div>
                            <small class="form-text text-muted">
                                Usada para criptografar senhas de SMTP, tokens de API, etc.
                            </small>
                        </div>

                        <!-- Botão de Regenerar -->
                        <div class="alert alert-warning">
                            <i class="bi bi-exclamation-triangle"></i>
                            <strong>Atenção:</strong> Guarde essas chaves em local seguro!
                            Se perdê-las, terá que reconfigurar tudo.
                        </div>

                        <button type="button" class="btn btn-warning btn-sm mb-3"
                                onclick="regenerateKeys()">
                            <i class="bi bi-arrow-clockwise"></i> Gerar Novas Chaves
                        </button>

                        <!-- Navegação -->
                        <div class="d-flex justify-content-between mt-4">
                            <a href="{{ url_for('setup.step1_environment') }}"
                               class="btn btn-secondary">← Voltar</a>
                            <button type="submit" class="btn btn-primary">Avançar →</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Card de Explicação -->
            <div class="card mt-3 border-info">
                <div class="card-body">
                    <h6 class="text-info"><i class="bi bi-info-circle"></i> O que são essas chaves?</h6>
                    <ul class="small mb-0">
                        <li><strong>SECRET_KEY:</strong> Protege cookies e sessões do Flask. Sem ela, hackers podem forjar logins.</li>
                        <li><strong>FERNET_KEY:</strong> Criptografa dados sensíveis no banco (senhas de email, tokens). Baseada em AES-128.</li>
                        <li><strong>Geração:</strong> Usa <code>secrets.token_hex(32)</code> e <code>Fernet.generate_key()</code> do Python.</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function copyToClipboard(elementId) {
    const input = document.getElementById(elementId);
    input.select();
    document.execCommand('copy');
    alert('Chave copiada!');
}

function regenerateKeys() {
    if (!confirm('Isso irá gerar novas chaves. Tem certeza?')) return;

    fetch('{{ url_for("setup.regenerate_keys") }}', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById('secretKey').value = data.secret_key;
        document.getElementById('fernetKey').value = data.fernet_key;
        alert('Novas chaves geradas!');
    });
}
</script>
{% endblock %}
```

#### 3.2.4. Exemplo de Valores Gerados

```bash
# Exemplo de SECRET_KEY
a3f2b9e1c4d6f8a1b3c5e7f9a1c3e5f7a9b1c3d5e7f9a1b3c5d7e9f1a3b5c7

# Exemplo de FERNET_KEY
kJw3jN8vY2xQ5pR7tZ9mB1nV4cX6fH8aS0dG2kL4wE6yU8iO0pA2sD4fG6hJ8=
```

---

### Etapa 3: Banco de Dados

#### 3.3.1. Objetivo
Permitir escolha entre SQLite (desenvolvimento) ou PostgreSQL (produção) com validação.

#### 3.3.2. Implementação

**Adicionar em:** `c:\Users\ralan\python gestao 2\gmm\app\routes\setup.py`

```python
@bp.route('/step3', methods=['GET', 'POST'])
def step3_database():
    """Configuração de banco de dados"""
    if request.method == 'POST':
        db_type = request.form.get('db_type')

        from flask import session
        if db_type == 'sqlite':
            # Caminho absoluto para SQLite
            db_path = Path(__file__).parent.parent.parent / 'instance' / 'gmm.db'
            session['DATABASE_URL'] = f"sqlite:///{db_path}"
        else:
            # PostgreSQL
            host = request.form.get('pg_host')
            port = request.form.get('pg_port', 5432)
            user = request.form.get('pg_user')
            password = request.form.get('pg_password')
            dbname = request.form.get('pg_database')

            session['DATABASE_URL'] = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

        return redirect(url_for('setup.step4_connectivity'))

    return render_template('setup/step3_database.html')

@bp.route('/api/test-db', methods=['POST'])
def test_database():
    """Testa conexão com banco de dados"""
    data = request.json
    db_type = data.get('db_type')

    try:
        if db_type == 'sqlite':
            import sqlite3
            db_path = Path(__file__).parent.parent.parent / 'instance' / 'gmm.db'
            db_path.parent.mkdir(exist_ok=True)
            conn = sqlite3.connect(db_path)
            conn.close()
            return jsonify({'success': True, 'message': 'SQLite OK'})

        elif db_type == 'postgresql':
            import psycopg2
            conn = psycopg2.connect(
                host=data.get('host'),
                port=data.get('port', 5432),
                user=data.get('user'),
                password=data.get('password'),
                database=data.get('database')
            )
            conn.close()
            return jsonify({'success': True, 'message': 'PostgreSQL conectado!'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
```

#### 3.3.3. Template de Exemplo

**Criar:** `c:\Users\ralan\python gestao 2\gmm\app\templates\setup\step3_database.html`

```html
{% extends "base_setup.html" %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Etapa 3: Banco de Dados</h4>
                </div>
                <div class="card-body">
                    <form method="POST" id="dbForm">
                        <!-- Escolha do Tipo -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">Escolha o Banco de Dados</label>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="db_type"
                                       id="dbSqlite" value="sqlite" checked
                                       onchange="toggleDbFields()">
                                <label class="form-check-label" for="dbSqlite">
                                    <strong>SQLite</strong>
                                    <small class="text-muted d-block">
                                        Ideal para desenvolvimento e projetos pequenos (até 50 usuários)
                                    </small>
                                </label>
                            </div>
                            <div class="form-check mt-2">
                                <input class="form-check-input" type="radio" name="db_type"
                                       id="dbPostgres" value="postgresql"
                                       onchange="toggleDbFields()">
                                <label class="form-check-label" for="dbPostgres">
                                    <strong>PostgreSQL</strong>
                                    <small class="text-muted d-block">
                                        Produção (alta concorrência, backups, replicação)
                                    </small>
                                </label>
                            </div>
                        </div>

                        <!-- Campos PostgreSQL (ocultos inicialmente) -->
                        <div id="postgresFields" class="d-none">
                            <div class="row">
                                <div class="col-md-8 mb-3">
                                    <label class="form-label">Host</label>
                                    <input type="text" class="form-control" name="pg_host"
                                           placeholder="localhost" value="localhost">
                                </div>
                                <div class="col-md-4 mb-3">
                                    <label class="form-label">Porta</label>
                                    <input type="number" class="form-control" name="pg_port"
                                           placeholder="5432" value="5432">
                                </div>
                            </div>

                            <div class="mb-3">
                                <label class="form-label">Nome do Banco</label>
                                <input type="text" class="form-control" name="pg_database"
                                       placeholder="gmm_producao">
                            </div>

                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">Usuário</label>
                                    <input type="text" class="form-control" name="pg_user"
                                           placeholder="postgres">
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">Senha</label>
                                    <input type="password" class="form-control" name="pg_password">
                                </div>
                            </div>

                            <!-- Botão de Teste -->
                            <button type="button" class="btn btn-info btn-sm"
                                    onclick="testDatabaseConnection()">
                                <i class="bi bi-plug"></i> Testar Conexão
                            </button>
                            <span id="testResult" class="ms-2"></span>
                        </div>

                        <!-- Navegação -->
                        <div class="d-flex justify-content-between mt-4">
                            <a href="{{ url_for('setup.step2_security') }}"
                               class="btn btn-secondary">← Voltar</a>
                            <button type="submit" class="btn btn-primary">Avançar →</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Card de Comandos -->
            <div class="card mt-3 border-info">
                <div class="card-body">
                    <h6 class="text-info"><i class="bi bi-terminal"></i> Como Instalar PostgreSQL no Linux</h6>
                    <pre class="bg-light p-2 rounded"><code># Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Criar banco e usuário
sudo -u postgres psql
CREATE DATABASE gmm_producao;
CREATE USER gmm_user WITH PASSWORD 'senha_segura';
GRANT ALL PRIVILEGES ON DATABASE gmm_producao TO gmm_user;
\q</code></pre>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function toggleDbFields() {
    const isPostgres = document.getElementById('dbPostgres').checked;
    document.getElementById('postgresFields').classList.toggle('d-none', !isPostgres);
}

function testDatabaseConnection() {
    const resultSpan = document.getElementById('testResult');
    resultSpan.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Testando...';

    const data = {
        db_type: document.querySelector('input[name="db_type"]:checked').value,
        host: document.querySelector('input[name="pg_host"]').value,
        port: document.querySelector('input[name="pg_port"]').value,
        user: document.querySelector('input[name="pg_user"]').value,
        password: document.querySelector('input[name="pg_password"]').value,
        database: document.querySelector('input[name="pg_database"]').value
    };

    fetch('{{ url_for("setup.test_database") }}', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(result => {
        if (result.success) {
            resultSpan.innerHTML = `<span class="badge bg-success">${result.message}</span>`;
        } else {
            resultSpan.innerHTML = `<span class="badge bg-danger">Erro: ${result.message}</span>`;
        }
    })
    .catch(err => {
        resultSpan.innerHTML = `<span class="badge bg-danger">Erro de conexão</span>`;
    });
}
</script>
{% endblock %}
```

#### 3.3.4. Exemplo de URLs Geradas

```bash
# SQLite (Desenvolvimento)
DATABASE_URL=sqlite:////home/usuario/gmm/instance/gmm.db

# PostgreSQL (Produção)
DATABASE_URL=postgresql://gmm_user:senha123@localhost:5432/gmm_producao
```

---

### Etapa 4: Conectividade (WhatsApp & E-mail)

#### 3.4.1. Objetivo
Configurar e **testar** integração com MegaAPI (WhatsApp) e SMTP/IMAP (Email).

#### 3.4.2. Implementação

**Adicionar em:** `c:\Users\ralan\python gestao 2\gmm\app\routes\setup.py`

```python
@bp.route('/step4', methods=['GET', 'POST'])
def step4_connectivity():
    """Configuração de WhatsApp e Email"""
    if request.method == 'POST':
        from flask import session

        # WhatsApp
        session['MEGA_API_KEY'] = request.form.get('mega_api_key')
        session['MEGA_API_URL'] = request.form.get('mega_api_url')

        # Email SMTP
        session['SMTP_SERVER'] = request.form.get('smtp_server')
        session['SMTP_PORT'] = request.form.get('smtp_port')
        session['SMTP_USER'] = request.form.get('smtp_user')
        session['SMTP_PASSWORD'] = request.form.get('smtp_password')

        # Email IMAP
        session['IMAP_SERVER'] = request.form.get('imap_server')
        session['IMAP_PORT'] = request.form.get('imap_port')

        return redirect(url_for('setup.step5_ai'))

    return render_template('setup/step4_connectivity.html')

@bp.route('/api/test-whatsapp', methods=['POST'])
def test_whatsapp():
    """Envia mensagem de teste via MegaAPI"""
    data = request.json

    try:
        import requests

        payload = {
            'number': data.get('test_number'),
            'message': '🎉 Olá! Este é um teste do GMM Setup Wizard.'
        }

        headers = {
            'Authorization': f"Bearer {data.get('api_key')}",
            'Content-Type': 'application/json'
        }

        response = requests.post(
            f"{data.get('api_url')}/send-message",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Mensagem enviada!'})
        else:
            return jsonify({'success': False, 'message': f'HTTP {response.status_code}'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@bp.route('/api/test-email', methods=['POST'])
def test_email():
    """Testa conexão SMTP"""
    data = request.json

    try:
        import smtplib
        from email.mime.text import MIMEText

        server = smtplib.SMTP(data.get('smtp_server'), int(data.get('smtp_port')))
        server.starttls()
        server.login(data.get('smtp_user'), data.get('smtp_password'))

        # Envia email de teste
        msg = MIMEText('Teste do GMM Setup Wizard')
        msg['Subject'] = 'GMM - Teste de Configuração'
        msg['From'] = data.get('smtp_user')
        msg['To'] = data.get('test_email')

        server.send_message(msg)
        server.quit()

        return jsonify({'success': True, 'message': 'Email enviado!'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
```

#### 3.4.3. Template de Exemplo

**Criar:** `c:\Users\ralan\python gestao 2\gmm\app\templates\setup\step4_connectivity.html`

```html
{% extends "base_setup.html" %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-10">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Etapa 4: Conectividade (WhatsApp & Email)</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="row">
                            <!-- WhatsApp -->
                            <div class="col-md-6 mb-4">
                                <h5 class="text-success"><i class="bi bi-whatsapp"></i> WhatsApp (MegaAPI)</h5>

                                <div class="mb-3">
                                    <label class="form-label">API Key</label>
                                    <input type="text" class="form-control" name="mega_api_key"
                                           id="megaApiKey" placeholder="sk_live_abc123...">
                                    <small class="text-muted">Obtenha em: mega.chat/dashboard</small>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label">API URL</label>
                                    <input type="url" class="form-control" name="mega_api_url"
                                           id="megaApiUrl" value="https://api.mega.chat/v1">
                                </div>

                                <!-- Teste WhatsApp -->
                                <div class="border-top pt-3">
                                    <label class="form-label text-muted">Teste (opcional)</label>
                                    <div class="input-group">
                                        <input type="tel" class="form-control" id="testWhatsappNumber"
                                               placeholder="5511999999999">
                                        <button type="button" class="btn btn-success"
                                                onclick="testWhatsApp()">
                                            Enviar Teste
                                        </button>
                                    </div>
                                    <span id="whatsappTestResult" class="small"></span>
                                </div>
                            </div>

                            <!-- Email -->
                            <div class="col-md-6 mb-4">
                                <h5 class="text-primary"><i class="bi bi-envelope"></i> Email (SMTP/IMAP)</h5>

                                <div class="row">
                                    <div class="col-8 mb-3">
                                        <label class="form-label">Servidor SMTP</label>
                                        <input type="text" class="form-control" name="smtp_server"
                                               id="smtpServer" placeholder="smtp.gmail.com">
                                    </div>
                                    <div class="col-4 mb-3">
                                        <label class="form-label">Porta</label>
                                        <input type="number" class="form-control" name="smtp_port"
                                               id="smtpPort" value="587">
                                    </div>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label">Usuário (Email)</label>
                                    <input type="email" class="form-control" name="smtp_user"
                                           id="smtpUser" placeholder="gmm@empresa.com">
                                </div>

                                <div class="mb-3">
                                    <label class="form-label">Senha / App Password</label>
                                    <input type="password" class="form-control" name="smtp_password"
                                           id="smtpPassword">
                                    <small class="text-muted">
                                        Gmail: Use "Senha de App" em myaccount.google.com
                                    </small>
                                </div>

                                <div class="row">
                                    <div class="col-8 mb-3">
                                        <label class="form-label">Servidor IMAP</label>
                                        <input type="text" class="form-control" name="imap_server"
                                               id="imapServer" placeholder="imap.gmail.com">
                                    </div>
                                    <div class="col-4 mb-3">
                                        <label class="form-label">Porta</label>
                                        <input type="number" class="form-control" name="imap_port"
                                               value="993">
                                    </div>
                                </div>

                                <!-- Teste Email -->
                                <div class="border-top pt-3">
                                    <label class="form-label text-muted">Teste (opcional)</label>
                                    <div class="input-group">
                                        <input type="email" class="form-control" id="testEmailAddress"
                                               placeholder="seu@email.com">
                                        <button type="button" class="btn btn-primary"
                                                onclick="testEmail()">
                                            Enviar Teste
                                        </button>
                                    </div>
                                    <span id="emailTestResult" class="small"></span>
                                </div>
                            </div>
                        </div>

                        <!-- Navegação -->
                        <div class="d-flex justify-content-between mt-4">
                            <a href="{{ url_for('setup.step3_database') }}"
                               class="btn btn-secondary">← Voltar</a>
                            <button type="submit" class="btn btn-primary">Avançar →</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Card de Ajuda -->
            <div class="card mt-3 border-info">
                <div class="card-body">
                    <h6 class="text-info"><i class="bi bi-info-circle"></i> Como Obter as Credenciais</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <strong>WhatsApp (MegaAPI):</strong>
                            <ol class="small">
                                <li>Acesse <a href="https://mega.chat" target="_blank">mega.chat</a></li>
                                <li>Crie uma conta gratuita</li>
                                <li>Conecte seu número WhatsApp Business</li>
                                <li>Copie a API Key do dashboard</li>
                            </ol>
                        </div>
                        <div class="col-md-6">
                            <strong>Gmail (Senha de App):</strong>
                            <ol class="small">
                                <li>Acesse myaccount.google.com/security</li>
                                <li>Ative "Verificação em 2 etapas"</li>
                                <li>Vá em "Senhas de app"</li>
                                <li>Gere senha para "Email" → "Outro (GMM)"</li>
                                <li>Use a senha de 16 dígitos gerada</li>
                            </ol>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function testWhatsApp() {
    const resultSpan = document.getElementById('whatsappTestResult');
    resultSpan.innerHTML = '<span class="text-info">Enviando...</span>';

    fetch('{{ url_for("setup.test_whatsapp") }}', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            api_key: document.getElementById('megaApiKey').value,
            api_url: document.getElementById('megaApiUrl').value,
            test_number: document.getElementById('testWhatsappNumber').value
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            resultSpan.innerHTML = `<span class="text-success">✓ ${data.message}</span>`;
        } else {
            resultSpan.innerHTML = `<span class="text-danger">✗ ${data.message}</span>`;
        }
    });
}

function testEmail() {
    const resultSpan = document.getElementById('emailTestResult');
    resultSpan.innerHTML = '<span class="text-info">Enviando...</span>';

    fetch('{{ url_for("setup.test_email") }}', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            smtp_server: document.getElementById('smtpServer').value,
            smtp_port: document.getElementById('smtpPort').value,
            smtp_user: document.getElementById('smtpUser').value,
            smtp_password: document.getElementById('smtpPassword').value,
            test_email: document.getElementById('testEmailAddress').value
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            resultSpan.innerHTML = `<span class="text-success">✓ ${data.message}</span>`;
        } else {
            resultSpan.innerHTML = `<span class="text-danger">✗ ${data.message}</span>`;
        }
    });
}
</script>
{% endblock %}
```

---

### Etapa 5: Inteligência Artificial (Opcional)

#### 3.5.1. Objetivo
Configurar OpenAI para transcrição de áudio e criação de OS por voz.

#### 3.5.2. Implementação

**Adicionar em:** `c:\Users\ralan\python gestao 2\gmm\app\routes\setup.py`

```python
@bp.route('/step5', methods=['GET', 'POST'])
def step5_ai():
    """Configuração de IA (opcional)"""
    if request.method == 'POST':
        from flask import session
        session['OPENAI_API_KEY'] = request.form.get('openai_api_key', '')
        return redirect(url_for('setup.complete'))

    return render_template('setup/step5_ai.html')

@bp.route('/api/test-openai', methods=['POST'])
def test_openai():
    """Testa API da OpenAI"""
    data = request.json

    try:
        import openai
        openai.api_key = data.get('api_key')

        # Teste simples de completion
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say test"}],
            max_tokens=5
        )

        return jsonify({'success': True, 'message': 'OpenAI conectada!'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
```

#### 3.5.3. Template de Exemplo

**Criar:** `c:\Users\ralan\python gestao 2\gmm\app\templates\setup\step5_ai.html`

```html
{% extends "base_setup.html" %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Etapa 5: Inteligência Artificial (Opcional)</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="alert alert-info">
                            <i class="bi bi-lightbulb"></i>
                            <strong>Esta etapa é opcional.</strong> Se não configurar agora,
                            as seguintes funcionalidades não estarão disponíveis:
                            <ul class="mb-0 mt-2">
                                <li>Transcrição automática de áudios do WhatsApp</li>
                                <li>Abertura de OS por comando de voz</li>
                                <li>Chatbot inteligente para responder dúvidas</li>
                            </ul>
                        </div>

                        <div class="mb-4">
                            <label class="form-label fw-bold">
                                <i class="bi bi-cpu"></i> OpenAI API Key
                            </label>
                            <input type="password" class="form-control" name="openai_api_key"
                                   id="openaiApiKey" placeholder="sk-proj-...">
                            <small class="text-muted">
                                Obtenha em: <a href="https://platform.openai.com/api-keys" target="_blank">
                                platform.openai.com/api-keys
                                </a>
                            </small>
                        </div>

                        <!-- Teste OpenAI -->
                        <button type="button" class="btn btn-info btn-sm"
                                onclick="testOpenAI()">
                            <i class="bi bi-plug"></i> Testar Conexão
                        </button>
                        <span id="openaiTestResult" class="ms-2"></span>

                        <!-- Navegação -->
                        <div class="d-flex justify-content-between mt-4">
                            <a href="{{ url_for('setup.step4_connectivity') }}"
                               class="btn btn-secondary">← Voltar</a>
                            <button type="submit" class="btn btn-success">Finalizar Setup →</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Card de Preços -->
            <div class="card mt-3 border-warning">
                <div class="card-body">
                    <h6 class="text-warning"><i class="bi bi-cash-coin"></i> Custos da OpenAI</h6>
                    <table class="table table-sm mb-0">
                        <thead>
                            <tr>
                                <th>Funcionalidade</th>
                                <th>Modelo</th>
                                <th>Custo Médio</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Transcrição de Áudio</td>
                                <td>Whisper</td>
                                <td>$0.006 / minuto</td>
                            </tr>
                            <tr>
                                <td>Chatbot / Abertura de OS</td>
                                <td>GPT-3.5 Turbo</td>
                                <td>$0.002 / 1K tokens</td>
                            </tr>
                            <tr>
                                <td colspan="2"><strong>Estimativa Mensal</strong> (100 áudios + 1000 msgs)</td>
                                <td><strong>~$5-10 USD</strong></td>
                            </tr>
                        </tbody>
                    </table>
                    <small class="text-muted">
                        Configure limites de gastos em platform.openai.com/settings/billing
                    </small>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function testOpenAI() {
    const apiKey = document.getElementById('openaiApiKey').value;
    if (!apiKey) {
        alert('Insira a API Key primeiro');
        return;
    }

    const resultSpan = document.getElementById('openaiTestResult');
    resultSpan.innerHTML = '<span class="text-info">Testando...</span>';

    fetch('{{ url_for("setup.test_openai") }}', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: apiKey})
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            resultSpan.innerHTML = `<span class="badge bg-success">${data.message}</span>`;
        } else {
            resultSpan.innerHTML = `<span class="badge bg-danger">Erro: ${data.message}</span>`;
        }
    });
}
</script>
{% endblock %}
```

---

## 4. Persistência e Segurança de Bloqueio

### 4.1. Geração do Arquivo .env

**Adicionar em:** `c:\Users\ralan\python gestao 2\gmm\app\routes\setup.py`

```python
@bp.route('/complete', methods=['GET', 'POST'])
def complete():
    """Finalização: Salva .env e cria setup.lock"""
    if request.method == 'POST':
        from flask import session

        # Montar conteúdo do .env
        env_content = f"""# GMM - Arquivo de Configuração
# Gerado automaticamente pelo Setup Wizard em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# === SEGURANÇA ===
SECRET_KEY={session.get('SECRET_KEY')}
FERNET_KEY={session.get('FERNET_KEY')}

# === BANCO DE DADOS ===
DATABASE_URL={session.get('DATABASE_URL')}

# === WHATSAPP (MegaAPI) ===
MEGA_API_KEY={session.get('MEGA_API_KEY', '')}
MEGA_API_URL={session.get('MEGA_API_URL', 'https://api.mega.chat/v1')}

# === EMAIL ===
SMTP_SERVER={session.get('SMTP_SERVER', '')}
SMTP_PORT={session.get('SMTP_PORT', 587)}
SMTP_USER={session.get('SMTP_USER', '')}
SMTP_PASSWORD={session.get('SMTP_PASSWORD', '')}
IMAP_SERVER={session.get('IMAP_SERVER', '')}
IMAP_PORT={session.get('IMAP_PORT', 993)}

# === INTELIGÊNCIA ARTIFICIAL ===
OPENAI_API_KEY={session.get('OPENAI_API_KEY', '')}

# === REDIS / CELERY ===
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# === FLASK ===
FLASK_ENV=production
FLASK_DEBUG=0
"""

        # Salvar arquivo .env
        env_path = Path(__file__).parent.parent.parent / '.env'
        env_path.write_text(env_content, encoding='utf-8')

        # Criar arquivo de trava
        lock_path = Path(__file__).parent.parent.parent / 'instance' / 'setup.lock'
        lock_path.parent.mkdir(exist_ok=True)
        lock_path.touch()

        # Limpar sessão
        session.clear()

        return render_template('setup/complete.html', env_path=str(env_path))

    # Exibe resumo antes de salvar
    from flask import session
    config_summary = {
        'database': session.get('DATABASE_URL', '').split('://')[0],
        'whatsapp': bool(session.get('MEGA_API_KEY')),
        'email': bool(session.get('SMTP_SERVER')),
        'ai': bool(session.get('OPENAI_API_KEY'))
    }
    return render_template('setup/complete.html', summary=config_summary)
```

### 4.2. Template de Finalização

**Criar:** `c:\Users\ralan\python gestao 2\gmm\app\templates\setup\complete.html`

```html
{% extends "base_setup.html" %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            {% if env_path %}
            <!-- Setup Concluído -->
            <div class="card shadow-sm border-success">
                <div class="card-header bg-success text-white">
                    <h4 class="mb-0"><i class="bi bi-check-circle"></i> Setup Concluído!</h4>
                </div>
                <div class="card-body">
                    <p class="lead">Configuração salva com sucesso em:</p>
                    <code class="bg-light p-2 d-block rounded">{{ env_path }}</code>

                    <div class="alert alert-warning mt-3">
                        <i class="bi bi-exclamation-triangle"></i>
                        <strong>IMPORTANTE:</strong> Reinicie o servidor Flask para aplicar as mudanças.
                    </div>

                    <h5 class="mt-4">Próximos Passos:</h5>
                    <ol>
                        <li><strong>Reinicie o serviço:</strong>
                            <pre class="bg-dark text-white p-2 rounded mt-2"><code># Se estiver usando systemd
sudo systemctl restart gmm

# Se estiver rodando diretamente
# Pressione Ctrl+C e execute novamente:
python run.py</code></pre>
                        </li>
                        <li><strong>Execute as migrações do banco:</strong>
                            <pre class="bg-dark text-white p-2 rounded"><code>flask db upgrade</code></pre>
                        </li>
                        <li><strong>Crie o usuário admin inicial:</strong>
                            <pre class="bg-dark text-white p-2 rounded"><code>flask create-admin</code></pre>
                        </li>
                        <li><strong>Acesse o sistema:</strong>
                            <a href="/login" class="btn btn-primary mt-2">Ir para Login</a>
                        </li>
                    </ol>

                    <div class="alert alert-info mt-4">
                        <i class="bi bi-shield-lock"></i>
                        <strong>Segurança:</strong> O setup está bloqueado. Para reconfigurar, delete o arquivo:
                        <code>rm {{ env_path }}</code>
                    </div>
                </div>
            </div>

            {% else %}
            <!-- Confirmação Final -->
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Revisão Final</h4>
                </div>
                <div class="card-body">
                    <p>Confirme as configurações antes de salvar:</p>

                    <table class="table table-bordered">
                        <tr>
                            <th>Banco de Dados</th>
                            <td>
                                <span class="badge bg-info">{{ summary.database.upper() }}</span>
                            </td>
                        </tr>
                        <tr>
                            <th>WhatsApp</th>
                            <td>
                                {% if summary.whatsapp %}
                                <span class="badge bg-success">✓ Configurado</span>
                                {% else %}
                                <span class="badge bg-secondary">Não configurado</span>
                                {% endif %}
                            </td>
                        </tr>
                        <tr>
                            <th>Email</th>
                            <td>
                                {% if summary.email %}
                                <span class="badge bg-success">✓ Configurado</span>
                                {% else %}
                                <span class="badge bg-secondary">Não configurado</span>
                                {% endif %}
                            </td>
                        </tr>
                        <tr>
                            <th>Inteligência Artificial</th>
                            <td>
                                {% if summary.ai %}
                                <span class="badge bg-success">✓ Configurado</span>
                                {% else %}
                                <span class="badge bg-warning">Opcional</span>
                                {% endif %}
                            </td>
                        </tr>
                    </table>

                    <form method="POST">
                        <div class="d-flex justify-content-between mt-4">
                            <a href="{{ url_for('setup.step5_ai') }}" class="btn btn-secondary">← Voltar</a>
                            <button type="submit" class="btn btn-success btn-lg">
                                <i class="bi bi-save"></i> Salvar e Finalizar
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}
```

---

## 5. Recomendações para Servidor Linux

### 5.1. Restart Automático (Systemd)

**Criar arquivo:** `/etc/systemd/system/gmm.service`

```ini
[Unit]
Description=GMM - Sistema de Gestão de Manutenção
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/home/usuario/gmm
Environment="PATH=/home/usuario/gmm/venv/bin"
ExecStart=/home/usuario/gmm/venv/bin/python run.py

# Reiniciar automaticamente se crashar
Restart=always
RestartSec=10

# Logs
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Comandos de gerenciamento:**
```bash
# Ativar e iniciar o serviço
sudo systemctl enable gmm
sudo systemctl start gmm

# Após o setup wizard salvar .env
sudo systemctl restart gmm

# Ver logs
sudo journalctl -u gmm -f
```

### 5.2. Caminhos Absolutos

O Wizard já converte automaticamente para caminhos absolutos:

```python
# ERRADO (relativo)
DATABASE_URL=sqlite:///instance/gmm.db

# CORRETO (absoluto - gerado pelo wizard)
DATABASE_URL=sqlite:////home/usuario/gmm/instance/gmm.db
```

### 5.3. Permissões de Arquivo

```bash
# Dar permissão ao usuário do serviço
sudo chown -R www-data:www-data /home/usuario/gmm
chmod 600 /home/usuario/gmm/.env  # Apenas leitura para o dono
chmod 755 /home/usuario/gmm       # Leitura/execução geral
```

---

## 6. Checklist de Implementação

### Para o Desenvolvedor:

- [ ] Criar `app/routes/setup.py` com todos os endpoints
- [ ] Criar templates em `app/templates/setup/`
- [ ] Modificar `app/__init__.py` para verificar `.env`
- [ ] Adicionar `base_setup.html` com layout limpo (sem sidebar)
- [ ] Testar em ambiente Linux real
- [ ] Documentar comandos de troubleshooting
- [ ] Criar arquivo `.env.example` com valores de exemplo

### Para o Usuário Final:

- [ ] Clone o repositório do GMM
- [ ] Instale dependências: `pip install -r requirements.txt`
- [ ] Inicie o Flask: `python run.py`
- [ ] Acesse `http://localhost:5000` (será redirecionado para `/setup`)
- [ ] Siga os 5 passos do wizard
- [ ] Clique em "Salvar e Finalizar"
- [ ] Reinicie o serviço
- [ ] Execute migrações: `flask db upgrade`
- [ ] Crie admin: `flask create-admin`
- [ ] Faça login e comece a usar!

---

## 7. Troubleshooting

### Problema: "Permission Denied" ao salvar .env

**Solução:**
```bash
sudo chown $USER:$USER /caminho/para/gmm
chmod +w /caminho/para/gmm
```

### Problema: Redis não conecta

**Solução:**
```bash
# Instalar Redis
sudo apt-get install redis-server

# Verificar status
sudo systemctl status redis

# Iniciar se estiver parado
sudo systemctl start redis
```

### Problema: PostgreSQL "Connection Refused"

**Solução:**
```bash
# Verificar se está rodando
sudo systemctl status postgresql

# Editar pg_hba.conf para permitir conexões locais
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Adicione esta linha:
# local   all   gmm_user   md5

# Reinicie PostgreSQL
sudo systemctl restart postgresql
```

### Problema: Setup já concluído, mas quero reconfigurar

**Solução:**
```bash
# Delete o .env e o lock
rm /caminho/para/gmm/.env
rm /caminho/para/gmm/instance/setup.lock

# Reinicie o Flask
sudo systemctl restart gmm
```

---

## 8. Exemplo de .env Gerado

```bash
# GMM - Arquivo de Configuração
# Gerado automaticamente pelo Setup Wizard em 2026-01-27 15:30:45

# === SEGURANÇA ===
SECRET_KEY=a3f2b9e1c4d6f8a1b3c5e7f9a1c3e5f7a9b1c3d5e7f9a1b3c5d7e9f1a3b5c7
FERNET_KEY=kJw3jN8vY2xQ5pR7tZ9mB1nV4cX6fH8aS0dG2kL4wE6yU8iO0pA2sD4fG6hJ8=

# === BANCO DE DADOS ===
DATABASE_URL=postgresql://gmm_user:senha123@localhost:5432/gmm_producao

# === WHATSAPP (MegaAPI) ===
MEGA_API_KEY=sk_live_abc123xyz456
MEGA_API_URL=https://api.mega.chat/v1

# === EMAIL ===
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=gmm@empresa.com
SMTP_PASSWORD=abcd efgh ijkl mnop
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# === INTELIGÊNCIA ARTIFICIAL ===
OPENAI_API_KEY=sk-proj-xyz789abc456

# === REDIS / CELERY ===
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# === FLASK ===
FLASK_ENV=production
FLASK_DEBUG=0
```

---

**Fim do PRD**
