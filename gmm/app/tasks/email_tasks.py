from app.extensions import db
from app.services.email_service import EmailService
from flask import current_app
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(name='app.tasks.email_tasks.monitorar_email_task')
def monitorar_email_task():
    """
    Task periódica para verificar novas respostas de fornecedores por email.
    """
    try:
        logger.info("Iniciando monitoramento de emails (IMAP)...")
        EmailService.fetch_and_process_replies()
        return True
    except Exception as e:
        logger.error(f"Erro na task de monitoramento de email: {e}")
        return False
