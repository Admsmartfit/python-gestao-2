from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from pathlib import Path
import os
import sys
import secrets
from cryptography.fernet import Fernet
from datetime import datetime

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
        # No Windows, usa o drive atual
        if sys.platform == 'win32':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p('.'), None, None, ctypes.pointer(free_bytes))
            return free_bytes.value > 1_000_000_000
        else:
            total, used, free = shutil.disk_usage("/")
            return free > 1_000_000_000  # 1GB
    except:
        return False

@bp.route('/step2', methods=['GET', 'POST'])
def step2_security():
    """Geração de chaves de segurança"""
    if request.method == 'POST':
        # Salvar na sessão para uso posterior
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

@bp.route('/step3', methods=['GET', 'POST'])
def step3_database():
    """Configuração de banco de dados"""
    if request.method == 'POST':
        db_type = request.form.get('db_type')

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

@bp.route('/step4', methods=['GET', 'POST'])
def step4_connectivity():
    """Configuração de WhatsApp e Email"""
    if request.method == 'POST':
        # Email SMTP
        session['SMTP_SERVER'] = request.form.get('smtp_server', '')
        session['SMTP_PORT'] = request.form.get('smtp_port', '587')
        session['SMTP_USER'] = request.form.get('smtp_user', '')
        session['SMTP_PASSWORD'] = request.form.get('smtp_password', '')

        # Email IMAP
        session['IMAP_SERVER'] = request.form.get('imap_server', '')
        session['IMAP_PORT'] = request.form.get('imap_port', '993')

        return redirect(url_for('setup.step5_ai'))

    return render_template('setup/step4_connectivity.html')

@bp.route('/api/test-whatsapp', methods=['POST'])
def test_whatsapp():
    """Envia mensagem de teste via MegaAPI"""
    data = request.json

    try:
        import requests as http_requests

        api_url = data.get('api_url', '').rstrip('/')
        api_token = data.get('api_token', '')
        instance_id = data.get('instance_id', '')
        test_number = data.get('test_number', '')

        if not all([api_url, api_token, instance_id, test_number]):
            return jsonify({'success': False, 'message': 'Preencha todos os campos'}), 400

        # Formatar telefone: 5511999999999 -> 5511999999999@s.whatsapp.net
        phone = test_number.strip().replace('+', '')
        recipient = f"{phone}@s.whatsapp.net"

        # Endpoint correto da MegaAPI
        endpoint = f"{api_url}/rest/sendMessage/{instance_id}/text"

        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }

        payload = {
            "messageData": {
                "to": recipient,
                "text": "Teste do GMM Setup Wizard - Conexao OK!"
            }
        }

        response = http_requests.post(endpoint, json=payload, headers=headers, timeout=10)

        if response.status_code in [200, 201]:
            return jsonify({'success': True, 'message': 'Mensagem enviada com sucesso!'})
        else:
            detail = response.text[:200] if response.text else f'HTTP {response.status_code}'
            return jsonify({'success': False, 'message': f'Erro {response.status_code}: {detail}'}), 400

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

@bp.route('/step5', methods=['GET', 'POST'])
def step5_ai():
    """Configuração de IA (opcional)"""
    if request.method == 'POST':
        # Provider selection
        ai_provider = request.form.get('ai_provider', 'openai')
        session['AI_PROVIDER'] = ai_provider

        if ai_provider == 'openai':
            session['OPENAI_API_KEY'] = request.form.get('openai_api_key', '')
            session['GEMINI_API_KEY'] = ''
            session['GEMINI_MODEL'] = ''
        else:
            # Gemini
            session['GEMINI_API_KEY'] = request.form.get('gemini_api_key', '')
            session['GEMINI_MODEL'] = request.form.get('gemini_model', 'gemini-1.5-flash')
            # Opções de transcrição para Gemini
            session['OPENAI_API_KEY'] = request.form.get('openai_api_key_whisper', '')
            session['GOOGLE_STT_API_KEY'] = request.form.get('google_stt_api_key', '')

        return redirect(url_for('setup.complete'))

    return render_template('setup/step5_ai.html')

@bp.route('/api/test-openai', methods=['POST'])
def test_openai():
    """Testa API da OpenAI"""
    data = request.json

    try:
        import requests as http_requests

        api_key = data.get('api_key')
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Say test"}],
            "max_tokens": 5
        }

        response = http_requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        return jsonify({'success': True, 'message': 'OpenAI conectada!'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@bp.route('/api/test-gemini', methods=['POST'])
def test_gemini():
    """Testa API do Google Gemini"""
    data = request.json

    try:
        import requests as http_requests

        api_key = data.get('api_key')
        model = data.get('model', 'gemini-1.5-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": "Say test"}]
            }],
            "generationConfig": {
                "maxOutputTokens": 10
            }
        }

        response = http_requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        return jsonify({'success': True, 'message': 'Gemini conectado!'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@bp.route('/api/test-google-stt', methods=['POST'])
def test_google_stt():
    """Testa API do Google Cloud STT"""
    data = request.json
    try:
        import requests as http_requests
        api_key = data.get('api_key')
        # Chamada mínima apenas para validar a chave (sem áudio real)
        url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
        # Payload vazio ou mal formatado apenas para ver se a API rejeita por "chave inválida" ou "corpo vazio"
        response = http_requests.post(url, json={}, timeout=10)
        
        # Se retornar 400 (Bad Request) com erro de 'audio' missing, a chave é válida.
        # Se retornar 403 (Forbidden), a chave é inválida.
        if response.status_code == 400 and 'audio' in response.text:
            return jsonify({'success': True, 'message': 'Google STT conectado (chave válida)!'})
        elif response.status_code == 403:
            return jsonify({'success': False, 'message': 'Chave Inválida ou Sem Permissão'}), 400
        else:
            return jsonify({'success': False, 'message': f'Erro: {response.text}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@bp.route('/complete', methods=['GET', 'POST'])
def complete():
    """Finalização: Salva .env e cria setup.lock"""
    if request.method == 'POST':
        # Montar conteúdo do .env
        env_content = f"""# GMM - Arquivo de Configuracao
# Gerado automaticamente pelo Setup Wizard em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# === SEGURANCA ===
SECRET_KEY={session.get('SECRET_KEY')}
FERNET_KEY={session.get('FERNET_KEY')}

# === BANCO DE DADOS ===
DATABASE_URL={session.get('DATABASE_URL')}

# === WHATSAPP (MegaAPI) ===
# Configure manualmente as variaveis abaixo:
MEGA_API_URL=
MEGA_API_TOKEN=
MEGA_API_ID=

# === EMAIL ===
SMTP_SERVER={session.get('SMTP_SERVER', '')}
SMTP_PORT={session.get('SMTP_PORT', 587)}
SMTP_USER={session.get('SMTP_USER', '')}
SMTP_PASSWORD={session.get('SMTP_PASSWORD', '')}
IMAP_SERVER={session.get('IMAP_SERVER', '')}
IMAP_PORT={session.get('IMAP_PORT', 993)}

# === INTELIGENCIA ARTIFICIAL ===
AI_PROVIDER={session.get('AI_PROVIDER', 'openai')}
OPENAI_API_KEY={session.get('OPENAI_API_KEY', '')}
GEMINI_API_KEY={session.get('GEMINI_API_KEY', '')}
GEMINI_MODEL={session.get('GEMINI_MODEL', 'gemini-1.5-flash')}
GOOGLE_STT_API_KEY={session.get('GOOGLE_STT_API_KEY', '')}

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
    ai_provider = session.get('AI_PROVIDER', 'openai')
    ai_configured = bool(session.get('OPENAI_API_KEY')) if ai_provider == 'openai' else bool(session.get('GEMINI_API_KEY'))

    config_summary = {
        'database': session.get('DATABASE_URL', '').split('://')[0] if session.get('DATABASE_URL') else 'nao configurado',
        'email': bool(session.get('SMTP_SERVER')),
        'ai': ai_configured,
        'ai_provider': ai_provider.upper() if ai_configured else None
    }
    return render_template('setup/complete.html', summary=config_summary)
