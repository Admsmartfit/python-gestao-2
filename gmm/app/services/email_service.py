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
    def _extrair_email_remetente(msg):
        """Extrai o endereco de email do campo From."""
        import re
        from_header = msg.get("From", "")
        # Extrair email de formatos como "Nome <email@dominio.com>" ou "email@dominio.com"
        match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', from_header)
        return match.group(0).lower() if match else None

    @staticmethod
    def _strip_quoted_reply(text: str) -> str:
        """Remove conteúdo citado de respostas de email (Gmail, Outlook, etc.)."""
        import re
        if not text:
            return text

        # Padrões de início de citação (linha que marca início do conteúdo original)
        quote_patterns = [
            # Gmail PT: "Em seg., 24 de fev. de 2025 às 10:30, Nome <email> escreveu:"
            r'^Em\s+\w+\.?,\s+\d+\s+de\s+\w+\.?\s+de\s+\d{4}',
            # Gmail EN: "On Mon, Feb 24, 2025 at 10:30 AM Name <email> wrote:"
            r'^On\s+\w+,\s+\w+\s+\d+,\s+\d{4}',
            # Generic "wrote:" pattern
            r'.+escreveu\s*:\s*$',
            r'.+wrote\s*:\s*$',
            # Outlook / standard separators
            r'^[-_]{4,}',
            r'^_{4,}',
            # "De:", "From:" headers (Outlook forward style)
            r'^De:\s+.+',
            r'^From:\s+.+',
            # "Mensagem original" separators
            r'^-+\s*Mensagem original\s*-+',
            r'^-+\s*Original [Mm]essage\s*-+',
            r'^-+\s*Forwarded message\s*-+',
        ]

        lines = text.splitlines()
        result_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Linhas que começam com > são citação direta
            if stripped.startswith('>'):
                break

            # Verificar padrões de início de bloco citado
            is_quote_start = False
            for pattern in quote_patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    is_quote_start = True
                    break

            if is_quote_start:
                break

            result_lines.append(line)

        result = '\n'.join(result_lines).strip()
        # Se ficou vazio (padrão não reconhecido), retornar texto original
        return result if result else text.strip()

    @staticmethod
    def _extrair_corpo_email(msg):
        """Extrai o corpo do email, preferindo text/plain, fallback para text/html."""
        import html
        corpo = ""
        if msg.is_multipart():
            texto_plain = ""
            texto_html = ""
            for part in msg.walk():
                content_type = part.get_content_type()
                charset = part.get_content_charset() or 'utf-8'
                if content_type == "text/plain" and not texto_plain:
                    try:
                        texto_plain = part.get_payload(decode=True).decode(charset, errors='replace')
                    except Exception:
                        texto_plain = part.get_payload(decode=True).decode('utf-8', errors='replace')
                elif content_type == "text/html" and not texto_html:
                    try:
                        raw = part.get_payload(decode=True).decode(charset, errors='replace')
                        # Remover tags HTML basicas
                        import re
                        texto_html = re.sub(r'<[^>]+>', ' ', raw)
                        texto_html = html.unescape(texto_html)
                        texto_html = re.sub(r'\s+', ' ', texto_html).strip()
                    except Exception:
                        pass
            corpo = texto_plain or texto_html
        else:
            charset = msg.get_content_charset() or 'utf-8'
            try:
                corpo = msg.get_payload(decode=True).decode(charset, errors='replace')
            except Exception:
                corpo = msg.get_payload(decode=True).decode('utf-8', errors='replace')

        return EmailService._strip_quoted_reply(corpo)

    @staticmethod
    def fetch_and_process_replies():
        """
        Monitora a caixa postal (IMAP) em busca de respostas de fornecedores.
        Vincula respostas ao ComunicacaoFornecedor pelo assunto (Ref: Pedido #X)
        e identifica o fornecedor pelo email remetente.
        """
        import imaplib
        import email
        import re
        from datetime import datetime
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

            # Buscar emails não lidos E emails recentes com "Re:" no assunto (últimos 3 dias)
            # Isso cobre casos onde o usuário abriu o email no Gmail antes da task rodar
            from email.utils import parsedate_to_datetime
            import time as _time

            ids_vistos = set()
            all_nums = []

            # 1. Não lidos
            status, msgs_unseen = mail.search(None, '(UNSEEN)')
            if status == 'OK' and msgs_unseen[0]:
                all_nums.extend(msgs_unseen[0].split())

            # 2. Lidos recentes (últimos 3 dias) com "Re:" no assunto — captura quem abriu no Gmail
            since_date = __import__('datetime').datetime.now() - __import__('datetime').timedelta(days=3)
            since_str = since_date.strftime('%d-%b-%Y')
            status2, msgs_since = mail.search(None, f'(SINCE "{since_str}" SUBJECT "Re:")')
            if status2 == 'OK' and msgs_since[0]:
                for n in msgs_since[0].split():
                    if n not in all_nums:
                        all_nums.append(n)

            logger.info(f"[Email] {len(all_nums)} email(s) para processar")

            for num in all_nums:
                if num in ids_vistos:
                    continue
                ids_vistos.add(num)

                status, data = mail.fetch(num, '(BODY.PEEK[])')
                if status != 'OK':
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decodificar assunto
                subject_raw = msg.get("Subject", "")
                subject_parts = decode_header(subject_raw)
                subject = ""
                for part, enc in subject_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors='replace')
                    else:
                        subject += part

                logger.info(f"Processando email: {subject}")
                
                # Tentar identificar Pedido ou Chamado pelo assunto
                pedido_match = re.search(r"Ref:\s*Pedido\s*#(\d+)", subject, re.IGNORECASE)
                chamado_match = re.search(r"Ref:\s*Chamado\s*#([\w-]+)", subject, re.IGNORECASE)

                if pedido_match:
                    pedido_id = int(pedido_match.group(1))
                    logger.info(f"Identificado padrao Pedido #{pedido_id}")
                    pedido = PedidoCompra.query.get(pedido_id)

                    if pedido:
                        # Extrair email do remetente e corpo
                        email_remetente = EmailService._extrair_email_remetente(msg)
                        corpo = EmailService._extrair_corpo_email(msg)

                        # Identificar fornecedor pelo email remetente
                        fornecedor_id = None
                        if email_remetente:
                            fornecedor = Fornecedor.query.filter(
                                db.func.lower(Fornecedor.email) == email_remetente,
                                Fornecedor.ativo == True
                            ).first()
                            if fornecedor:
                                fornecedor_id = fornecedor.id
                                logger.info(f"Fornecedor identificado pelo email: {fornecedor.nome}")

                        # Fallback: usar fornecedor do pedido
                        if not fornecedor_id and pedido.fornecedor_id:
                            fornecedor_id = pedido.fornecedor_id

                        if not fornecedor_id:
                            logger.warning(f"Nao foi possivel identificar fornecedor para email de {email_remetente} no Pedido #{pedido_id}")
                            # Marcar como lido mesmo assim para nao reprocessar
                            mail.store(num, '+FLAGS', '\\Seen')
                            continue

                        # Atualizar comunicacao original (enviada) com a resposta
                        comunicacao_original = ComunicacaoFornecedor.query.filter(
                            ComunicacaoFornecedor.pedido_compra_id == pedido.id,
                            ComunicacaoFornecedor.fornecedor_id == fornecedor_id,
                            ComunicacaoFornecedor.tipo_comunicacao == 'email',
                            ComunicacaoFornecedor.direcao == 'enviado',
                            ComunicacaoFornecedor.status.in_(['enviado', 'entregue', 'pendente'])
                        ).order_by(ComunicacaoFornecedor.data_envio.desc()).first()

                        if comunicacao_original:
                            comunicacao_original.resposta = corpo[:2000]
                            comunicacao_original.status = 'respondido'
                            comunicacao_original.data_resposta = datetime.now()

                        # Evitar duplicatas: checar se já existe entrada 'recebido' com mesmo conteúdo
                        corpo_trunc = corpo[:200]
                        ja_existe = ComunicacaoFornecedor.query.filter(
                            ComunicacaoFornecedor.pedido_compra_id == pedido.id,
                            ComunicacaoFornecedor.fornecedor_id == fornecedor_id,
                            ComunicacaoFornecedor.direcao == 'recebido',
                            ComunicacaoFornecedor.mensagem.like(f"{corpo_trunc}%")
                        ).first()

                        if ja_existe:
                            logger.debug(f"Email já processado para Pedido #{pedido_id}, ignorando.")
                        else:
                            com = ComunicacaoFornecedor(
                                pedido_compra_id=pedido.id,
                                fornecedor_id=fornecedor_id,
                                tipo_comunicacao='email',
                                direcao='recebido',
                                mensagem=corpo[:2000],
                                status='respondido',
                                data_envio=datetime.now()
                            )
                            db.session.add(com)
                            db.session.commit()
                            logger.info(f"Resposta email arquivada para Pedido #{pedido_id}")

                elif chamado_match:
                    from app.models.terceirizados_models import ChamadoExterno, HistoricoNotificacao
                    
                    numero_chamado = chamado_match.group(1)
                    logger.info(f"Identificado padrao Chamado #{numero_chamado}")
                    chamado = ChamadoExterno.query.filter_by(numero_chamado=numero_chamado).first()
                    
                    if chamado:
                        email_remetente = EmailService._extrair_email_remetente(msg)
                        corpo = EmailService._extrair_corpo_email(msg)
                        
                        # Criar registro de resposta no histórico de notificações
                        hist = HistoricoNotificacao(
                            chamado_id=chamado.id,
                            tipo='resposta',
                            mensagem=corpo[:2000],
                            direcao='inbound',
                            status_envio='entregue',
                            remetente=email_remetente[:20],
                            criado_em=datetime.now()
                        )
                        db.session.add(hist)
                        db.session.commit()
                        logger.info(f"Resposta email arquivada para Chamado #{numero_chamado}")
                    else:
                        logger.warning(f"Chamado #{numero_chamado} nao encontrado no banco.")
                else:
                    logger.debug(f"Padrão Pedido/Chamado não encontrado no assunto: {subject}")

                # Marcar como lido para nao reprocessar
                mail.store(num, '+FLAGS', '\\Seen')

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Erro ao monitorar IMAP: {str(e)}")

