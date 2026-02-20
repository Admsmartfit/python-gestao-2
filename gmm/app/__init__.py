from flask import Flask, redirect, url_for, request
from app.extensions import db, login_manager, migrate
from app.models.models import Usuario
from celery import Celery
from datetime import datetime
from pathlib import Path
import os as os_module
from dotenv import load_dotenv

# Carregar variáveis de ambiente o mais cedo possível
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    load_dotenv(env_file)

from config import Config

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

def create_app():
    app = Flask(__name__)

    # VERIFICAÇÃO DE SETUP
    env_file = Path(__file__).parent.parent / '.env'
    setup_lock = Path(__file__).parent.parent / 'instance' / 'setup.lock'

    # Registrar blueprint de setup ANTES de verificar configurações
    from app.routes import setup as setup_module
    app.register_blueprint(setup_module.bp)

    # Configurar secret key temporária para o setup wizard
    app.config['SECRET_KEY'] = os_module.environ.get('SECRET_KEY', 'temporary-setup-key-change-me')

    # Se .env não existe e não estamos na rota de setup, redirecionar
    @app.before_request
    def check_setup():
        if not env_file.exists() and not request.path.startswith('/setup') and not request.path.startswith('/static'):
            return redirect(url_for('setup.welcome'))

        # Se setup já foi feito, bloquear acesso à rota /setup
        if env_file.exists() and request.path.startswith('/setup'):
            if setup_lock.exists():
                return "Setup já foi concluído. Delete o arquivo .env para reconfigurar.", 403

    # Se .env existe, configurar app
    if env_file.exists():
        app.config.from_object('config.Config')

        db.init_app(app)
        login_manager.init_app(app)
        migrate.init_app(app, db)

        # Inicializa Celery
        app.celery = make_celery(app)

        @app.context_processor
        def inject_now():
            return {'hoje': datetime.utcnow()}

        @login_manager.user_loader
        def load_user(user_id):
            return Usuario.query.get(int(user_id))

        # Registrar Blueprints
        # Importamos todos os módulos de rotas aqui para evitar erros de importação circular
        from app.routes import (
            auth,
            ponto,
            admin,
            os,
            terceirizados,
            analytics,
            whatsapp,
            webhook,
            admin_whatsapp,
            equipamentos,
            search,
            notifications,
            compras,
            estoque,
            manutencao
        )

        app.register_blueprint(auth.bp)
        app.register_blueprint(ponto.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(os.bp)
        app.register_blueprint(terceirizados.bp)
        app.register_blueprint(analytics.bp)
        app.register_blueprint(whatsapp.bp)
        app.register_blueprint(webhook.bp)
        app.register_blueprint(admin_whatsapp.bp)

        # Novo Módulo de Equipamentos
        app.register_blueprint(equipamentos.bp)

        # Módulos de Utilidade
        app.register_blueprint(search.bp)
        app.register_blueprint(notifications.bp)
        app.register_blueprint(compras.bp)
        app.register_blueprint(estoque.bp)
        app.register_blueprint(manutencao.bp)

        # Rota Raiz
        @app.route('/')
        def root():
            # Redireciona automaticamente para o login
            return redirect(url_for('auth.login'))
    else:
        # Modo setup - apenas rota raiz redireciona para setup
        @app.route('/')
        def root():
            return redirect(url_for('setup.welcome'))

    return app