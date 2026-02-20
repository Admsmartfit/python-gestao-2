import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    
    # Detecção automática: Se houver DATABASE_URL (Render/Heroku/AWS), usa Postgres.
    # Senão, usa SQLite local.
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    if SQLALCHEMY_DATABASE_URI:
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
        
        # Se for SQLite relativo, tornar absoluto baseado no basedir
        if SQLALCHEMY_DATABASE_URI.startswith("sqlite:///"):
            path = SQLALCHEMY_DATABASE_URI.replace("sqlite:///", "")
            # Verifica se não é absoluto (Linux ou Windows)
            if not os.path.isabs(path) and not path.startswith('/'):
                SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, path)
    else:
        # Fallback padrão
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'gmm.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    # WhatsApp (MegaAPI)
    MEGA_API_URL = os.environ.get('MEGA_API_URL') or 'https://apistart01.megaapi.com.br'
    MEGA_API_KEY = os.environ.get('MEGA_API_KEY')
    MEGA_API_TOKEN = os.environ.get('MEGA_API_TOKEN')
    MEGA_API_ID = os.environ.get('MEGA_API_ID')
    
    # Inteligência Artificial
    AI_PROVIDER = os.environ.get('AI_PROVIDER') or 'openai'  # 'openai' ou 'gemini'
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-1.5-flash'  # ou 'gemini-1.5-pro'
    GOOGLE_STT_API_KEY = os.environ.get('GOOGLE_STT_API_KEY')

    FERNET_KEY = os.environ.get('FERNET_KEY') or '00000000000000000000000000000000'
    
    CELERY_IMPORTS = ('app.tasks',)

    # Email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    PURCHASE_EMAIL = os.environ.get('PURCHASE_EMAIL') # Email do setor de compras
    
    # IMAP settings for monitoring responses
    MAIL_IMAP_SERVER = os.environ.get('MAIL_IMAP_SERVER') or 'imap.gmail.com'
    MAIL_IMAP_USERNAME = os.environ.get('MAIL_IMAP_USERNAME') or os.environ.get('MAIL_USERNAME')
    MAIL_IMAP_PASSWORD = os.environ.get('MAIL_IMAP_PASSWORD') or os.environ.get('MAIL_PASSWORD')


    # Celery Beat Schedule
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'morning-briefing-diario': {
            'task': 'app.tasks.system_tasks.enviar_morning_briefing_task',
            'schedule': crontab(hour=8, minute=0),
        },
        'verificar-estoque-critico': {
            'task': 'app.tasks.system_tasks.verificar_estoque_critico_task',
            'schedule': crontab(hour=9, minute=0),
        },
        'lembretes-chamados-externos': {
            'task': 'app.tasks.system_tasks.lembretes_automaticos_task',
            'schedule': crontab(hour=14, minute=0),
        },
        'anomalias-equipamentos': {
            'task': 'app.tasks.system_tasks.detectar_anomalias_equipamentos_task',
            'schedule': crontab(hour=10, minute=0, day_of_week='mon'),
        },
        'monitorar-respostas-email': {
            'task': 'app.tasks.email_tasks.monitorar_email_task',
            'schedule': crontab(minute='*/10'), # A cada 10 minutos
        },
    }
