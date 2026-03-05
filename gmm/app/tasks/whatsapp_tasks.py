from celery import shared_task
from datetime import datetime, timedelta
import json
import hashlib
from app.extensions import db
from app.models.terceirizados_models import HistoricoNotificacao
from app.models.whatsapp_models import EstadoConversa, MetricasWhatsApp, ConfiguracaoWhatsApp
from app.services.whatsapp_service import WhatsAppService
from app.services.roteamento_service import RoteamentoService
from app.services.media_downloader_service import MediaDownloaderService
import logging

logger = logging.getLogger(__name__)

from app.services.alerta_service import AlertaService

@shared_task
def verificar_saude_whatsapp():
    """Verifica saúde do sistema e dispara alertas."""
    AlertaService.verificar_saude()

def _processar_onetap_compra(remetente: str, texto: str) -> bool:
    """Detecta e processa One-Tap de aprovação/rejeição via WhatsApp. Retorna True se tratado."""
    import re
    from app.models.models import Usuario
    from app.models.estoque_models import PedidoCompra, AprovacaoPedido

    m_apr = re.match(r'^aprovar_pedido_(\d+)$', texto.strip(), re.IGNORECASE)
    m_rej = re.match(r'^rejeitar_pedido_(\d+)$', texto.strip(), re.IGNORECASE)
    if not (m_apr or m_rej):
        return False

    pedido_id = int((m_apr or m_rej).group(1))
    pedido = PedidoCompra.query.get(pedido_id)
    if not pedido:
        WhatsAppService.enviar_mensagem(remetente, f"❌ Pedido #{pedido_id} não encontrado.")
        return True

    tel_norm = WhatsAppService.normalizar_telefone(remetente)
    usuario = Usuario.query.filter(
        db.or_(Usuario.telefone == tel_norm, Usuario.telefone == remetente)
    ).first()
    if not usuario or usuario.tipo not in ('admin', 'gerente', 'diretor'):
        WhatsAppService.enviar_mensagem(remetente, "❌ Sem permissão para aprovar pedidos.")
        return True

    item = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido_id}')

    if m_apr:
        if pedido.status not in ('solicitado', 'aguardando_diretoria'):
            WhatsAppService.enviar_mensagem(remetente, f"ℹ️ Pedido #{pedido_id} já está '{pedido.status}'.")
            return True
        if AprovacaoPedido.query.filter_by(pedido_id=pedido_id, aprovador_id=usuario.id, acao='aprovado').first():
            WhatsAppService.enviar_mensagem(remetente, f"ℹ️ Você já aprovou o Pedido #{pedido_id}.")
            return True
        db.session.add(AprovacaoPedido(pedido_id=pedido_id, aprovador_id=usuario.id, acao='aprovado', via='whatsapp'))
        total = AprovacaoPedido.query.filter_by(pedido_id=pedido_id, acao='aprovado').count() + 1
        if (pedido.tier_aprovacao or 2) <= 2 or total >= 2:
            pedido.status = 'aprovado'
            pedido.aprovador_id = usuario.id
            db.session.commit()
            enviar_pedido_fornecedor.delay(pedido_id)
            WhatsAppService.enviar_mensagem(remetente, f"✅ Pedido *#{pedido_id}* aprovado!\nItem: {item}")
            if pedido.solicitante and pedido.solicitante.telefone:
                WhatsAppService.enviar_mensagem(pedido.solicitante.telefone,
                    f"✅ Pedido *#{pedido_id}* ({item}) aprovado por {usuario.nome}.")
        else:
            db.session.commit()
            WhatsAppService.enviar_mensagem(remetente, f"✅ Aprovação registrada ({total}/2). Aguardando segundo diretor.")
    else:
        if pedido.status in ('recebido', 'cancelado', 'recusado'):
            WhatsAppService.enviar_mensagem(remetente, f"ℹ️ Pedido #{pedido_id} já está '{pedido.status}'.")
            return True
        db.session.add(AprovacaoPedido(pedido_id=pedido_id, aprovador_id=usuario.id, acao='rejeitado', via='whatsapp'))
        pedido.status = 'recusado'
        db.session.commit()
        WhatsAppService.enviar_mensagem(remetente, f"❌ Pedido *#{pedido_id}* rejeitado.")
        if pedido.solicitante and pedido.solicitante.telefone:
            WhatsAppService.enviar_mensagem(pedido.solicitante.telefone,
                f"❌ Pedido *#{pedido_id}* ({item}) recusado por {usuario.nome}.")
    return True


@shared_task
def processar_mensagem_inbound(remetente: str, texto: str, timestamp: float):
    """
    Processa mensagem recebida (Inbound) assincronamente.
    """
    try:
        # One-Tap de aprovação de compras (deve ser verificado antes do roteamento)
        if _processar_onetap_compra(remetente, texto):
            return {'status': 'onetap_compra'}

        # Rotear
        resultado = RoteamentoService.processar(remetente, texto)
        
        # Executar ação
        if resultado.get('acao') == 'responder':
            tipo_resposta = resultado.get('tipo_resposta', 'texto')

            if tipo_resposta == 'lista_interativa' and resultado.get('resposta_estruturada'):
                try:
                    dados = json.loads(resultado['resposta_estruturada'])
                    WhatsAppService.send_list_message(
                        phone=remetente,
                        header=dados.get('header', ''),
                        body=dados.get('body', ''),
                        sections=dados.get('sections', []),
                        button_text=dados.get('button_text', 'Ver Opções')
                    )
                except Exception as e:
                    logger.error(f"Erro ao enviar lista interativa: {e}")
                    if resultado.get('resposta'):
                        WhatsAppService.enviar_mensagem(remetente, resultado['resposta'])

            elif tipo_resposta == 'botoes' and resultado.get('resposta_estruturada'):
                try:
                    dados = json.loads(resultado['resposta_estruturada'])
                    WhatsAppService.send_buttons_message(
                        phone=remetente,
                        body=dados.get('body', ''),
                        buttons=dados.get('buttons', [])
                    )
                except Exception as e:
                    logger.error(f"Erro ao enviar botões: {e}")
                    if resultado.get('resposta'):
                        WhatsAppService.enviar_mensagem(remetente, resultado['resposta'])

            elif resultado.get('resposta'):
                WhatsAppService.enviar_mensagem(remetente, resultado['resposta'])
        
        elif resultado.get('acao') == 'executar_funcao':
             # Em um cenário real, chamariamos a funcão dinamicamente o u via mapping
             # Ex: executar_funcao_sistema(resultado['funcao'], remetente, texto)
             # Por enquanto vamos apenas confirmar que foi "executado"
             WhatsAppService.enviar_mensagem(remetente, f"Comando {resultado.get('funcao', 'sistema')} acionado.")

        elif resultado.get('acao') == 'encaminhar':
             # Simula encaminhamento
            WhatsAppService.enviar_mensagem(remetente, "Sua mensagem foi encaminhada para um atendente.")
            
            # Aqui notificariamos o admin/gerente (Ex: Email, ou msg no WhatsApp do Admin)
            # destino = resultado['destino'] # gerente, etc
            
    except Exception as e:
        logger.error(f"Erro ao processar inbound: {e}")
        WhatsAppService.enviar_mensagem(remetente, "❌ Erro ao processar sua mensagem. Tente novamente.")

@shared_task(bind=True, max_retries=3)
def enviar_whatsapp_task(self, notificacao_id: int):
    """
    Task assíncrona para envio de WhatsApp.
    - Busca notificação no banco
    - Chama WhatsAppService.enviar_mensagem()
    - Atualiza status e tentativas
    - Retry com backoff exponencial: 1min, 5min, 25min (baseado na fórmula do PRD)
    """
    notificacao = HistoricoNotificacao.query.get(notificacao_id)
    if not notificacao:
        return {"error": "Notificação não encontrada"}

    # Gere um hash da mensagem para auditoria se não existir
    if not notificacao.mensagem_hash:
        notificacao.mensagem_hash = hashlib.sha256(notificacao.mensagem.encode()).hexdigest()

    sucesso, resposta = WhatsAppService.enviar_mensagem(
        telefone=notificacao.destinatario,
        texto=notificacao.mensagem,
        prioridade=notificacao.prioridade,
        notificacao_id=notificacao.id
    )

    # Se foi enfileirado pelo Rate Limiter, a task atual termina com sucesso
    # pois uma nova já foi agendada.
    if sucesso and isinstance(resposta, dict) and resposta.get('status') == 'enfileirado':
        return {"status": "enfileirado", "notificacao_id": notificacao_id}

    notificacao.tentativas += 1
    notificacao.resposta_api = json.dumps(resposta) if isinstance(resposta, dict) else str(resposta)

    if sucesso:
        notificacao.status_envio = 'enviado'
        notificacao.enviado_em = datetime.utcnow()
        db.session.commit()
        return {"status": "success", "notificacao_id": notificacao_id}
    else:
        # Retry logic: 1min, 5min, 25min
        if notificacao.tentativas < self.max_retries:
            delay = 60 * (5 ** (notificacao.tentativas - 1))
            db.session.commit()
            raise self.retry(countdown=delay)
        else:
            notificacao.status_envio = 'falhou'
            db.session.commit()
            return {"status": "failed", "error": resposta}

@shared_task
def limpar_estados_expirados():
    """Limpa estados de conversa com mais de 24 horas de inatividade."""
    limite = datetime.utcnow() - timedelta(hours=24)
    removidos = EstadoConversa.query.filter(EstadoConversa.updated_at < limite).delete()
    db.session.commit()
    return {"removidos": removidos}

@shared_task
def agregar_metricas_horarias():
    """Calcula métricas de envio e performance da última hora."""
    fim = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    inicio = fim - timedelta(hours=1)
    
    total = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.enviado_em >= inicio,
        HistoricoNotificacao.enviado_em < fim,
        HistoricoNotificacao.status_envio == 'enviado'
    ).count()

    falhas = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.enviado_em >= inicio,
        HistoricoNotificacao.enviado_em < fim,
        HistoricoNotificacao.status_envio == 'falhou'
    ).count()

    total_tentativas = total + falhas
    taxa = (total / total_tentativas * 100) if total_tentativas > 0 else 0

    metrica = MetricasWhatsApp(
        data_hora=inicio,
        total_enviadas=total,
        taxa_entrega=taxa,
        periodo='hora'
    )
    db.session.add(metrica)
    db.session.commit()
    return {"data_hora": inicio.isoformat(), "total": total, "taxa": taxa}


# ==================== NOVAS TASKS V3.1 ====================

@shared_task(bind=True, max_retries=3)
def baixar_midia_task(self, notificacao_id, url_megaapi, tipo_conteudo):
    """
    Task assíncrona para download de mídias da MegaAPI.

    Args:
        notificacao_id: ID da notificação no banco
        url_megaapi: URL temporária da mídia na MegaAPI
        tipo_conteudo: 'image', 'audio', 'document'

    Retry: 3 tentativas com backoff exponencial (1min, 5min, 25min)
    """
    try:
        # Busca credenciais (DB ou .env)
        config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
        bearer_token = None
        if config and config.api_key_encrypted:
            try:
                from flask import current_app
                fernet_key = current_app.config.get('FERNET_KEY')
                bearer_token = config.decrypt_key(fernet_key)
            except Exception:
                pass

        if not bearer_token:
            from flask import current_app
            bearer_token = current_app.config.get('MEGA_API_TOKEN')

        if not bearer_token:
            raise Exception("MEGA_API_TOKEN não encontrado (DB ou .env)")

        # Download
        logger.info(f"Iniciando download de mídia para notificação {notificacao_id}")
        filepath = MediaDownloaderService.download(url_megaapi, tipo_conteudo, bearer_token)

        # Atualiza banco
        notificacao = HistoricoNotificacao.query.get(notificacao_id)
        if not notificacao:
            raise Exception(f"Notificação {notificacao_id} não encontrada")

        notificacao.url_midia_local = filepath
        db.session.commit()

        logger.info(f"Mídia baixada com sucesso: {filepath}")

        # Se for áudio, dispara transcrição
        if tipo_conteudo == 'audio':
            transcrever_audio_task.delay(notificacao_id)

        return {"status": "success", "filepath": filepath}

    except Exception as exc:
        logger.error(f"Erro ao baixar mídia (tentativa {self.request.retries + 1}): {exc}")

        # Retry com backoff: 1min, 5min, 25min
        if self.request.retries < self.max_retries:
            delay = 60 * (5 ** self.request.retries)
            raise self.retry(exc=exc, countdown=delay)
        else:
            # Marca como falha no banco
            try:
                notificacao = HistoricoNotificacao.query.get(notificacao_id)
                if notificacao:
                    notificacao.status_envio = 'falha_download'
                    db.session.commit()
            except:
                pass

            return {"status": "failed", "error": str(exc)}


@shared_task(bind=True, max_retries=3)
def transcrever_audio_task(self, notificacao_id):
    """
    Task assíncrona para transcrição de áudio via OpenAI Whisper.

    Args:
        notificacao_id: ID da notificação no banco
    """
    try:
        from flask import current_app
        import requests
        import os
        
        notificacao = HistoricoNotificacao.query.get(notificacao_id)
        if not notificacao or not notificacao.url_midia_local:
            return {"error": "Notificação ou arquivo não encontrado"}

        # Caminho absoluto do arquivo
        # url_midia_local começa com /static/...
        filepath = os.path.join(current_app.root_path, notificacao.url_midia_local.lstrip('/'))
        
        if not os.path.exists(filepath):
             raise Exception(f"Arquivo não encontrado no disco: {filepath}")

        # Configurações OpenAI
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY não configurada. Transcrição impossível.")
            return {"status": "skipped", "reason": "no_api_key"}

        # Chamada Whisper API
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        logger.info(f"Enviando arquivo {filepath} para Whisper")
        
        with open(filepath, 'rb') as audio_file:
            files = {
                'file': (os.path.basename(filepath), audio_file),
            }
            data = {
                'model': 'whisper-1',
                'language': 'pt'
            }
            response = requests.post(url, headers=headers, files=files, data=data, timeout=60)

        if response.status_code != 200:
            raise Exception(f"Erro na API OpenAI: {response.status_code} - {response.text}")

        transcricao = response.json().get('text')
        
        if transcricao:
            notificacao.mensagem = f"[ÁUDIO] {transcricao}"
            db.session.commit()
            
            logger.info(f"Transcrição concluída para {notificacao_id}: {transcricao[:50]}...")
            
            # Após transcrever, processar o texto resultante como se fosse um inbound de texto
            # para acionar NLP e roteamento
            processar_mensagem_inbound.delay(notificacao.remetente, transcricao, datetime.utcnow().timestamp())

        return {"status": "success", "transcription": transcricao}

    except Exception as exc:
        logger.error(f"Erro na transcrição (tentativa {self.request.retries + 1}): {exc}")
        if self.request.retries < self.max_retries:
            delay = 60 * (5 ** self.request.retries)
            raise self.retry(exc=exc, countdown=delay)
        return {"status": "failed", "error": str(exc)}
@shared_task(bind=True, max_retries=3)
def enviar_pedido_fornecedor(self, pedido_id):
    """Gera PDF do pedido e envia para fornecedor via WhatsApp e Email."""
    from app.models.estoque_models import PedidoCompra
    from app.services.pdf_generator_service import PDFGeneratorService
    from app.services.whatsapp_service import WhatsAppService
    from app.services.email_service import EmailService
    from app.extensions import db

    try:
        pedido = PedidoCompra.query.get(pedido_id)
        if not pedido:
            return {"error": "Pedido não encontrado"}

        # 1. Gerar PDF
        pdf_path = PDFGeneratorService.gerar_pdf_pedido(pedido_id)

        # 2. Enviar via WhatsApp (se fornecedor tem telefone)
        if pedido.fornecedor and pedido.fornecedor.telefone:
            mensagem = f"📦 *PEDIDO DE COMPRA*\n\n*Número:* {pedido.numero_pedido or pedido.id}\n*Data:* {pedido.data_solicitacao.strftime('%d/%m/%Y')}\n*Valor Total:* R$ {pedido.valor_total or 0:.2f}\n\nSegue em anexo o pedido completo."
            WhatsAppService.enviar_mensagem(
                telefone=pedido.fornecedor.telefone,
                texto=mensagem,
                prioridade=1,
                arquivo_path=pdf_path,
                tipo_midia="document",
                caption=f"Pedido {pedido.numero_pedido or pedido.id}"
            )

        # 3. Enviar via Email (se fornecedor tem email)
        if pedido.fornecedor and pedido.fornecedor.email:
            try:
                EmailService.enviar_email(
                    destinatario=pedido.fornecedor.email,
                    assunto=f"Pedido de Compra {pedido.numero_pedido or pedido.id}",
                    corpo=f"Prezado(a) {pedido.fornecedor.nome},\n\nSegue em anexo o Pedido de Compra {pedido.numero_pedido or pedido.id}.\n\nValor Total: R$ {pedido.valor_total or 0:.2f}\n\nPor favor, confirme o recebimento.",
                    anexos=[pdf_path]
                )
            except Exception as e:
                logger.error(f"Erro ao enviar email para fornecedor: {e}")

        # 4. Atualizar status do pedido
        pedido.status = "pedido"
        db.session.commit()
        return {"status": "success"}

    except Exception as exc:
        logger.error(f"Erro ao enviar pedido para fornecedor: {exc}")
        if self.request.retries < self.max_retries:
            delay = 60 * (5 ** self.request.retries)
            raise self.retry(exc=exc, countdown=delay)
        return {"status": "failed", "error": str(exc)}
