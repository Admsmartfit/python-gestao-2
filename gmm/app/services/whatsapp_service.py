import requests
import re
import logging
from flask import current_app
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Serviço de envio de mensagens via MegaAPI.

    Formato dos endpoints:
        POST {MEGA_API_URL}/rest/sendMessage/{MEGA_API_ID}/{tipo}
        Headers: Authorization: Bearer {MEGA_API_TOKEN}
        Body: {"messageData": {"to": "5511999999999@s.whatsapp.net", ...}}
    """

    @staticmethod
    def validar_telefone(telefone: str) -> bool:
        """Valida formato: 5511999999999 (13 dígitos)"""
        return bool(re.match(r'^55\d{11}$', str(telefone)))

    @staticmethod
    def _get_credentials():
        """
        Retorna (url_base, instance_key, bearer_token) da MegaAPI.

        Na MegaAPI:
        - instance_key: identificador da instância na URL (ex: megastart-MkOyNxUpCFB)
        - bearer_token: token de autenticação no header Authorization
        - Normalmente ambos são o mesmo valor (MEGA_API_KEY)
        """
        # Tentar credenciais do banco (encriptadas)
        try:
            from app.models.whatsapp_models import ConfiguracaoWhatsApp
            config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
            if config and config.api_key_encrypted:
                fernet_key = current_app.config.get('FERNET_KEY')
                api_key = config.decrypt_key(fernet_key)
                url = current_app.config.get('MEGA_API_URL')
                if url and api_key:
                    return url, api_key, api_key
        except Exception as e:
            logger.debug(f"Credenciais do banco não disponíveis: {e}")

        # Fallback: credenciais do .env
        url = current_app.config.get('MEGA_API_URL')
        # MEGA_API_KEY é a chave da instância (ex: megastart-XXXXX)
        # Serve como instance_key na URL e como Bearer token
        api_key = current_app.config.get('MEGA_API_KEY')

        return url, api_key, api_key

    @staticmethod
    def _format_phone(telefone: str) -> str:
        """Formata telefone para o padrão MegaAPI: 5511999999999@s.whatsapp.net"""
        phone = re.sub(r'[^0-9]', '', str(telefone))
        return f"{phone}@s.whatsapp.net"

    @classmethod
    def enviar_mensagem(cls, telefone: str, texto: str, prioridade: int = 0, notificacao_id: int = None,
                       arquivo_path: str = None, tipo_midia: str = 'text', caption: str = None):
        """
        Envia mensagem via MegaAPI com resiliência e suporte a multimídia.

        Args:
            telefone: Número no formato 5511999999999
            texto: Texto da mensagem
            prioridade: 0=Normal, 1=Alta, 2=Urgente (ignora rate limit)
            notificacao_id: ID da notificação para tracking
            arquivo_path: Caminho do arquivo de mídia (opcional)
            tipo_midia: Tipo de mídia: 'text', 'image', 'audio', 'document'
            caption: Legenda para mídia (opcional)
        """
        # 1. Validação
        if not cls.validar_telefone(telefone):
            return False, {"error": "Telefone inválido"}

        # 2. Circuit Breaker
        if not CircuitBreaker.should_attempt():
            from app.services.sms_service import SMSService
            logger.warning(f"WhatsApp Indisponível (Circuit OPEN). Tentando SMS para {telefone}")
            sucesso_sms, res_sms = SMSService.enviar_sms(telefone, texto)
            if sucesso_sms:
                return True, {"status": "enviado_via_sms", "details": res_sms}
            return False, {"error": "Circuit breaker OPEN and SMS fallback failed", "code": "CIRCUIT_OPEN_NO_FALLBACK"}

        # 3. Rate Limit (ignorar se prioridade urgente >= 2)
        if prioridade < 2:
            pode_enviar, restantes = RateLimiter.check_limit()
            if not pode_enviar:
                logger.info(f"Rate limit reached. Enqueueing notification {notificacao_id} for later.")
                if notificacao_id:
                    from app.tasks.whatsapp_tasks import enviar_whatsapp_task
                    enviar_whatsapp_task.apply_async(args=[notificacao_id], countdown=60)
                return True, {"status": "enfileirado"}

        # 4. Enviar
        recipient = cls._format_phone(telefone)

        if arquivo_path and tipo_midia != 'text':
            return cls._send_media(recipient, arquivo_path, tipo_midia, caption or texto)
        else:
            payload = {
                "messageData": {
                    "to": recipient,
                    "text": texto
                }
            }
            return cls._send_request("text", payload)

    @classmethod
    def send_list_message(cls, phone: str, header: str, body: str, sections: list, button_text: str = "Ver Opções"):
        """
        Envia mensagem com lista interativa (menu nativo do WhatsApp).

        Args:
            phone: Telefone no formato 5511999999999
            header: Cabeçalho da mensagem
            body: Corpo da mensagem
            sections: Lista de seções com opções
            button_text: Texto do botão
        """
        if not cls.validar_telefone(phone):
            return False, {"error": "Telefone inválido"}
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN"}

        recipient = cls._format_phone(phone)

        payload = {
            "messageData": {
                "to": recipient,
                "buttonText": button_text,
                "text": body,
                "title": header,
                "sections": sections
            }
        }

        return cls._send_request("listMessage", payload)

    @classmethod
    def send_buttons_message(cls, phone: str, body: str, buttons: list):
        """
        Envia mensagem com botões interativos (máximo 3 botões).

        Args:
            phone: Telefone no formato 5511999999999
            body: Texto da mensagem
            buttons: Lista de botões (máx 3)
        """
        if not cls.validar_telefone(phone):
            return False, {"error": "Telefone inválido"}
        if len(buttons) > 3:
            return False, {"error": "Máximo de 3 botões permitido"}
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN"}

        recipient = cls._format_phone(phone)

        payload = {
            "messageData": {
                "to": recipient,
                "text": body,
                "buttons": buttons
            }
        }

        return cls._send_request("buttonMessage", payload)

    @classmethod
    def enviar_documento(cls, phone: str, document_url: str, filename: str, caption: str = None):
        """
        Envia documento (PDF, etc) via WhatsApp usando URL.

        Args:
            phone: Telefone no formato 5511999999999
            document_url: URL pública do documento
            filename: Nome do arquivo
            caption: Legenda opcional
        """
        if not cls.validar_telefone(phone):
            return False, {"error": "Telefone inválido"}
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN"}

        recipient = cls._format_phone(phone)

        payload = {
            "messageData": {
                "to": recipient,
                "url": document_url,
                "fileName": filename,
                "type": "document",
                "caption": caption or ""
            }
        }

        return cls._send_request("mediaUrl", payload)

    @classmethod
    def _send_media(cls, recipient: str, arquivo_path: str, tipo_midia: str, caption: str = None):
        """Envia mídia usando base64."""
        import os
        import base64
        import mimetypes

        if not os.path.exists(arquivo_path):
            return False, {"error": f"Arquivo não encontrado: {arquivo_path}"}

        try:
            mime_type, _ = mimetypes.guess_type(arquivo_path)
            if not mime_type:
                mime_type = 'application/octet-stream'

            with open(arquivo_path, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')

            base64_str = f"data:{mime_type};base64,{file_data}"

            payload = {
                "messageData": {
                    "to": recipient,
                    "base64": base64_str,
                    "fileName": os.path.basename(arquivo_path),
                    "type": tipo_midia,
                    "caption": caption or "",
                    "mimeType": mime_type
                }
            }

            return cls._send_request("mediaBase64", payload)

        except Exception as e:
            logger.error(f"Erro ao preparar mídia: {e}")
            return False, {"error": str(e)}

    @classmethod
    def _send_request(cls, endpoint_type: str, payload: dict):
        """
        Método interno para enviar requisição à MegaAPI.

        Args:
            endpoint_type: Tipo de endpoint (text, mediaBase64, listMessage, buttonMessage, etc.)
            payload: Payload completo da requisição

        Returns:
            tuple: (sucesso: bool, resposta: dict)
        """
        url, instance_key, bearer_token = cls._get_credentials()

        if not url or not instance_key:
            logger.error("Configuração MegaAPI incompleta. Verifique MEGA_API_URL e MEGA_API_KEY no .env")
            return False, {"error": "Configuração MegaAPI incompleta (URL ou MEGA_API_KEY ausente)"}

        # Montar URL: {base}/rest/sendMessage/{instance_key}/{type}
        base_url = url.rstrip('/')
        endpoint = f"{base_url}/rest/sendMessage/{instance_key}/{endpoint_type}"

        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 201]:
                CircuitBreaker.record_success()
                RateLimiter.increment()
                return True, response.json()
            else:
                CircuitBreaker.record_failure()
                logger.warning(f"MegaAPI failure [{endpoint_type}]: {response.status_code} - {response.text}")
                return False, {"status": response.status_code, "text": response.text}

        except requests.exceptions.RequestException as e:
            CircuitBreaker.record_failure()
            logger.error(f"MegaAPI request exception: {str(e)}")
            return False, {"error": str(e)}
