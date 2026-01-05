import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_email(subject, recipient, body_html):
        """
        Envia um email simples via SMTP usando as configurações do app.
        """
        if not recipient:
            logger.warning("Nenhum destinatário fornecido para o email.")
            return False

        config = current_app.config
        
        smtp_server = config.get('MAIL_SERVER')
        smtp_port = config.get('MAIL_PORT', 587)
        smtp_user = config.get('MAIL_USERNAME')
        smtp_pass = config.get('MAIL_PASSWORD')
        sender = config.get('MAIL_DEFAULT_SENDER') or smtp_user

        if not all([smtp_server, smtp_user, smtp_pass]):
            logger.error("Configurações de email incompletas (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD).")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = recipient
            msg['Subject'] = subject

            msg.attach(MIMEText(body_html, 'html'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            if config.get('MAIL_USE_TLS'):
                server.starttls()
            
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email enviado para {recipient}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar email para {recipient}: {str(e)}")
            return False

    @staticmethod
    def notify_purchase_request(pedido, item_nome, solicitante_nome):
        """
        Formata e envia a notificação de solicitação de compra.
        """
        # Obter destinatário (comprador configurado ou fallback)
        recipient = current_app.config.get('PURCHASE_EMAIL')
        if not recipient:
            logger.warning("PURCHASE_EMAIL não configurado. Fallback para MAIL_USERNAME.")
            recipient = current_app.config.get('MAIL_USERNAME')

        subject = f"🛒 Nova Solicitação de Compra: {item_nome}"
        
        body = f"""
        <html>
            <body>
                <h2>Nova Solicitação de Peça</h2>
                <p><strong>Pedido ID:</strong> #{pedido.id}</p>
                <p><strong>Item:</strong> {item_nome}</p>
                <p><strong>Quantidade:</strong> {pedido.quantidade}</p>
                <p><strong>Solicitante:</strong> {solicitante_nome}</p>
                <p><strong>Data:</strong> {pedido.data_solicitacao.strftime('%d/%m/%Y %H:%M')}</p>
                <hr>
                <p>Favor verificar no sistema GMM para aprovação.</p>
            </body>
        </html>
        """
        
        return EmailService.send_email(subject, recipient, body)
