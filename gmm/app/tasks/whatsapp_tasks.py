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

@shared_task
def processar_mensagem_inbound(remetente: str, texto: str, timestamp: float):
    """
    Processa mensagem recebida (Inbound) assincronamente.
    """
    try:
        # Rotear
        resultado = RoteamentoService.processar(remetente, texto)
        
        # Executar ação
        if resultado.get('acao') == 'responder':
            if 'resposta' in resultado and resultado['resposta']:
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
        # Busca configuração
        config = ConfiguracaoWhatsApp.query.first()
        if not config:
            raise Exception("Configuração do WhatsApp não encontrada")

        bearer_token = config.api_key_decrypted

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
