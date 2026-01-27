import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    
    # Detecção automática: Se houver DATABASE_URL (Render/Heroku/AWS), usa Postgres.
    # Senão, usa SQLite local.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///gmm.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    MEGA_API_KEY = os.environ.get('MEGA_API_KEY')
    MEGA_API_URL = "https://api.megaapi.com.br/v1/messages/send"
    
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
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
