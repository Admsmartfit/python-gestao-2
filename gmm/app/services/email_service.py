import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_email(subject, recipient, body_html, cc=None):
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
            if cc:
                msg['Cc'] = cc

            msg.attach(MIMEText(body_html, 'html'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            if config.get('MAIL_USE_TLS'):
                server.starttls()
            
            server.login(smtp_user, smtp_pass)
            
            # Destinatários para o comando de envio
            recipients = [recipient]
            if cc:
                if isinstance(cc, list):
                    recipients.extend(cc)
                else:
                    recipients.append(cc)
                    
            server.send_message(msg, to_addrs=recipients)
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

    @staticmethod
    def enviar_solicitacao_orcamento(pedido, fornecedor, mensagem, cc=None):
        """
        Envia solicitação de orçamento para um fornecedor.
        Inclui ID do pedido e OS no assunto para rastreamento.
        """
        item_nome = pedido.peca.nome
        os_ref = f"OS #{pedido.ordem_servico.numero_os}" if hasattr(pedido, 'ordem_servico') and pedido.ordem_servico else "N/A"
        
        subject = f"🛒 Solicitação de Orçamento [Ref: Pedido #{pedido.id}] [Ref: {os_ref}] - {item_nome}"
        
        body = f"""
        <html>
            <body>
                <div style="font-family: sans-serif; line-height: 1.6;">
                    <h2 style="color: #0d6efd;">Solicitação de Orçamento</h2>
                    <p>Olá <strong>{fornecedor.nome}</strong>,</p>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #0d6efd;">
                        {mensagem.replace('\n', '<br>')}
                    </div>
                    <p style="color: #6c757d; font-size: 0.9em; margin-top: 20px;">
                        Por favor, responda este email com sua proposta. 
                        Mantenha o assunto original para que possamos processar sua resposta automaticamente.
                    </p>
                </div>
            </body>
        </html>
        """
        return EmailService.send_email(subject, fornecedor.email, body, cc=cc)

    @staticmethod
    def enviar_solicitacao_terceirizado(chamado, terceirizado, mensagem, cc=None):
        """
        Envia solicitação para um prestador terceirizado.
        """
        os_ref = f"OS #{chamado.os_origem.numero_os}" if chamado.os_origem else "N/A"
        subject = f"🔧 Chamado Externo [Ref: Chamado #{chamado.numero_chamado}] [Ref: {os_ref}] - {chamado.titulo}"
        
        body = f"""
        <html>
            <body>
                <div style="font-family: sans-serif; line-height: 1.6;">
                    <h2 style="color: #198754;">Nova Ordem de Serviço / Chamado</h2>
                    <p>Olá <strong>{terceirizado.nome}</strong>,</p>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #198754;">
                        {mensagem.replace('\n', '<br>')}
                    </div>
                    <p style="color: #6c757d; font-size: 0.9em; margin-top: 20px;">
                        Por favor, responda este email para confirmar ou enviar atualizações.
                    </p>
                </div>
            </body>
        </html>
        """
        return EmailService.send_email(subject, terceirizado.email, body, cc=cc)

    @staticmethod
    def fetch_and_process_replies():
        """
        Monitora a caixa postal (IMAP) em busca de respostas.
        """
        import imaplib
        import email
        import re
        from email.header import decode_header
        from app.models.estoque_models import ComunicacaoFornecedor, PedidoCompra, Fornecedor
        from app.extensions import db

        config = current_app.config
        imap_server = config.get('MAIL_IMAP_SERVER')
        imap_user = config.get('MAIL_IMAP_USERNAME')
        imap_pass = config.get('MAIL_IMAP_PASSWORD')

        if not all([imap_server, imap_user, imap_pass]):
            logger.warning("Configurações IMAP incompletas.")
            return

        try:
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")

            # Buscar emails não lidos
            status, messages = mail.search(None, '(UNSEEN)')
            if status != 'OK':
                return

            for num in messages[0].split():
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK':
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Decodificar assunto
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8")
                
                logger.info(f"Processando email: {subject}")

                # Tentar identificar Pedido ou Chamado pelo assunto
                pedido_match = re.search(r"Ref: Pedido #(\d+)", subject)
                
                if pedido_match:
                    pedido_id = int(pedido_match.group(1))
                    pedido = PedidoCompra.query.get(pedido_id)
                    
                    if pedido:
                        # Extrair corpo da mensagem
                        corpo = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    corpo = part.get_payload(decode=True).decode()
                                    break
                        else:
                            corpo = msg.get_payload(decode=True).decode()

                        # Salvar como resposta recebida
                        com = ComunicacaoFornecedor(
                            pedido_compra_id=pedido.id,
                            fornecedor_id=pedido.fornecedor_id,
                            tipo_comunicacao='email',
                            direcao='recebido',
                            mensagem=corpo[:1000], # Limitar tamanho
                            status='respondido',
                            data_envio=datetime.now()
                        )
                        db.session.add(com)
                        
                        # Atualizar status do pedido se necessário
                        # pedido.status = 'cotado' 
                        
                        db.session.commit()
                        logger.info(f"Resposta arquivada para Pedido #{pedido_id}")
                
                # Marcar como lido (imaplib faz isso por padrão no fetch RFC822 se não especificado o contrário, 
                # mas garantimos aqui)
                # mail.store(num, '+FLAGS', '\\Seen')

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Erro ao monitorar IMAP: {str(e)}")

