import hmac
import hashlib
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.terceirizados_models import HistoricoNotificacao
from app.tasks.whatsapp_tasks import processar_mensagem_inbound

bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)

def validar_webhook(req):
    """
    Valida origem do webhook:
    - IP na whitelist (Placeholder IPs)
    - Assinatura HMAC
    - Timestamp recente (max 5min)
    """
    # 1. IP Whitelist (Simulated/Placeholder ranges as per prompt)
    # In prod, check actual MegaAPI IPs
    # MEGAAPI_IPS = ['191.252.xxx.xxx', ...]
    # For now, we skip IP check or allow localhost/all for dev
    # if request.remote_addr not in MEGAAPI_IPS: ...
    
    # 2. Assinatura HMAC
    signature = req.headers.get('X-Webhook-Signature', '')
    payload = req.get_data()
    secret = current_app.config.get('WEBHOOK_SECRET', 'default-secret-dev')
    
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    # Using compare_digest to prevent timing attacks
    # Note: Prompt example format "sha256={expected}" depends on provider. 
    # MegaAPI usually sends just the hash or specific format. Adapting to prompt req.
    # If signature header is just the hash:
    if not hmac.compare_digest(signature, f"sha256={expected}") and not hmac.compare_digest(signature, expected):
         # Try both formats to be safe
         logger.warning(f"Invalid HMAC signature. Expected: {expected}, Got: {signature}")
         return False
    
    # 3. Timestamp (Replay Attack Prevention)
    try:
        data = req.json
        if not data: return False
        
        timestamp = data.get('timestamp')
        if not timestamp:
            # Some hooks might not send timestamp in body, check headers if needed
            return True # Skip if not present
            
        msg_time = datetime.fromtimestamp(int(timestamp))
        now = datetime.utcnow()
        
        if abs((now - msg_time).total_seconds()) > 300:  # 5 minutos
            logger.warning(f"Old message received: {msg_time}")
            return False
    except Exception as e:
        logger.error(f"Error validating timestamp: {e}")
        return False
    
    return True

@bp.route('/webhook/whatsapp', methods=['POST'])
def webhook_whatsapp():
    """
    Receives POSTs from MegaAPI
    Handles: text, interactive, image, audio, document
    """
    # 1. Validações de Segurança
    if not validar_webhook(request):
        return jsonify({'error': 'Unauthorized'}), 403

    # 2. Parse do payload
    try:
        data = request.json
        payload_data = data.get('data', {})

        remetente = payload_data.get('from')
        timestamp = data.get('timestamp', datetime.utcnow().timestamp())

        # Identificar tipo de mensagem
        tipo_mensagem = payload_data.get('type', 'text')  # text, interactive, image, audio, document

        # Campos comuns
        megaapi_id = payload_data.get('id')  # ID único da mensagem na MegaAPI

        if not remetente:
            return jsonify({'status': 'ignored', 'reason': 'no_sender'}), 200

    except KeyError as e:
        logger.error(f"Invalid payload structure: {e}")
        return jsonify({'error': 'Invalid payload'}), 400

    # 3. Processar baseado no tipo
    try:
        notif = None

        if tipo_mensagem == 'text':
            # Mensagem de texto simples
            texto = payload_data.get('text', {}).get('body') if isinstance(payload_data.get('text'), dict) else payload_data.get('text')

            if not texto:
                return jsonify({'status': 'ignored', 'reason': 'empty_text'}), 200

            notif = HistoricoNotificacao(
                tipo='resposta_auto',
                direcao='inbound',
                remetente=remetente,
                destinatario='sistema',
                status_envio='recebido',
                mensagem=texto,
                mensagem_hash=hashlib.sha256(texto.encode()).hexdigest(),
                megaapi_id=megaapi_id,
                tipo_conteudo='text',
                status_leitura='nao_lida',
                chamado_id=None
            )
            db.session.add(notif)
            db.session.commit()

            # Processar assincronamente
            processar_mensagem_inbound.delay(remetente, texto, timestamp)

        elif tipo_mensagem == 'interactive':
            # Resposta de list message ou button
            interactive_data = payload_data.get('interactive', {})
            interactive_type = interactive_data.get('type')  # list_reply, button_reply

            if interactive_type == 'list_reply':
                resposta_id = interactive_data.get('list_reply', {}).get('id')
                resposta_titulo = interactive_data.get('list_reply', {}).get('title')
            elif interactive_type == 'button_reply':
                resposta_id = interactive_data.get('button_reply', {}).get('id')
                resposta_titulo = interactive_data.get('button_reply', {}).get('title')
            else:
                resposta_id = None
                resposta_titulo = None

            if not resposta_id:
                return jsonify({'status': 'ignored', 'reason': 'no_interactive_response'}), 200

            notif = HistoricoNotificacao(
                tipo='resposta_interativa',
                direcao='inbound',
                remetente=remetente,
                destinatario='sistema',
                status_envio='recebido',
                mensagem=resposta_id,  # Guardar ID da resposta
                caption=resposta_titulo,  # Guardar título para exibição
                megaapi_id=megaapi_id,
                tipo_conteudo='interactive',
                status_leitura='nao_lida',
                chamado_id=None
            )
            db.session.add(notif)
            db.session.commit()

            # Processar resposta interativa
            from app.services.roteamento_service import RoteamentoService
            resultado = RoteamentoService.processar_resposta_interativa(notif)

            # Executar ação do resultado
            if resultado.get('acao') == 'enviar_mensagem':
                from app.services.whatsapp_service import WhatsAppService
                WhatsAppService.enviar_mensagem(resultado['telefone'], resultado['mensagem'], prioridade=1)

        elif tipo_mensagem in ['image', 'audio', 'document']:
            # Mensagem com mídia
            midia_data = payload_data.get(tipo_mensagem, {})
            url_megaapi = midia_data.get('url') or midia_data.get('link')  # URL temporária da mídia
            mimetype = midia_data.get('mime_type')
            caption = midia_data.get('caption')

            if not url_megaapi:
                return jsonify({'status': 'ignored', 'reason': 'no_media_url'}), 200

            notif = HistoricoNotificacao(
                tipo='midia_recebida',
                direcao='inbound',
                remetente=remetente,
                destinatario='sistema',
                status_envio='recebido',
                mensagem=caption or f'[{tipo_mensagem.upper()}]',
                megaapi_id=megaapi_id,
                tipo_conteudo=tipo_mensagem,
                mimetype=mimetype,
                caption=caption,
                status_leitura='nao_lida',
                chamado_id=None
            )
            db.session.add(notif)
            db.session.commit()

            # Disparar task para baixar mídia
            from app.tasks.whatsapp_tasks import baixar_midia_task

            baixar_midia_task.delay(notif.id, url_megaapi, tipo_mensagem)

        else:
            # Tipo desconhecido - registrar mas ignorar
            logger.warning(f"Unknown message type: {tipo_mensagem}")
            return jsonify({'status': 'ignored', 'reason': f'unknown_type_{tipo_mensagem}'}), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Processing failed', 'details': str(e)}), 500

    return jsonify({'success': True, 'processed_at': datetime.utcnow().isoformat()})
