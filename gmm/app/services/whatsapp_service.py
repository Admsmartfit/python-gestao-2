import requests
import json
import re
import time
import logging
from flask import current_app
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class WhatsAppService:

    @staticmethod
    def validar_telefone(telefone: str) -> bool:
        """Valida formato: 5511999999999 (13 dígitos)"""
        return bool(re.match(r'^55\d{11}$', str(telefone)))

    @classmethod
    def enviar_mensagem(cls, telefone: str, texto: str, prioridade: int = 0, notificacao_id: int = None):
        """
        Envia mensagem via MegaAPI com resiliência:
        1. Validação de Telefone
        2. Circuit Breaker check
        3. Rate Limiting check (exceto para prioridade 2/Urgente)
        4. API Request com Error Handling
        """
        # 1. Validação
        if not cls.validar_telefone(telefone):
            return False, {"error": "Telefone inválido"}

        # 2. Circuit Breaker
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN", "code": "CIRCUIT_OPEN"}

        # 3. Rate Limit (ignorar se prioridade urgente >= 2)
        if prioridade < 2:
            pode_enviar, restantes = RateLimiter.check_limit()
            if not pode_enviar:
                logger.info(f"Rate limit reached. Enqueueing notification {notificacao_id} for later.")
                if notificacao_id:
                    # Circular import avoidance: import inside method
                    from app.tasks.whatsapp_tasks import enviar_whatsapp_task
                    enviar_whatsapp_task.apply_async(args=[notificacao_id], countdown=60)
                return True, {"status": "enfileirado"}

        # 4. Get Credentials
        from app.models.whatsapp_models import ConfiguracaoWhatsApp
        config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
        
        if config and config.api_key_encrypted:
            try:
                fernet_key = current_app.config.get('FERNET_KEY')
                api_key = config.decrypt_key(fernet_key)
                url = current_app.config.get('MEGA_API_URL')
            except Exception as e:
                logger.error(f"Error decrypting API Key: {str(e)}")
                return False, {"error": "Decryption failed"}
        else:
            url = current_app.config.get('MEGA_API_URL')
            api_key = current_app.config.get('MEGA_API_KEY')

        if not url or not api_key:
            return False, {"error": "MegaAPI configuration missing"}

        # 5. API Request
        try:
            response = requests.post(
                url,
                json={"phone": telefone, "message": texto},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                CircuitBreaker.record_success()
                RateLimiter.increment()
                return True, response.json()
            else:
                CircuitBreaker.record_failure()
                logger.warning(f"MegaAPI failure: {response.status_code} - {response.text}")
                return False, {"status": response.status_code, "text": response.text}
                
        except requests.exceptions.RequestException as e:
            CircuitBreaker.record_failure()
            logger.error(f"MegaAPI request exception: {str(e)}")
            return False, {"error": str(e)}

    # ==================== MÉTODOS V3.1 - MENSAGENS INTERATIVAS ====================

    @classmethod
    def send_list_message(cls, phone: str, header: str, body: str, sections: list):
        """
        Envia mensagem com lista interativa (menu nativo do WhatsApp).

        Args:
            phone: Telefone no formato 5511999999999
            header: Cabeçalho da mensagem
            body: Corpo da mensagem
            sections: Lista de seções com opções
                Exemplo: [
                    {
                        "title": "Menu Principal",
                        "rows": [
                            {"id": "minhas_os", "title": "Minhas OSs", "description": "Ver ordens abertas"},
                            {"id": "solicitar_peca", "title": "Solicitar Peça"}
                        ]
                    }
                ]

        Returns:
            tuple: (sucesso: bool, resposta: dict)
        """
        # Validação
        if not cls.validar_telefone(phone):
            return False, {"error": "Telefone inválido"}

        # Circuit Breaker
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN"}

        # Construir payload MegaAPI
        payload = {
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "button": "Ver Opções",
                    "sections": sections
                }
            }
        }

        return cls._send_request(payload)

    @classmethod
    def send_buttons_message(cls, phone: str, body: str, buttons: list):
        """
        Envia mensagem com botões interativos (máximo 3 botões).

        Args:
            phone: Telefone no formato 5511999999999
            body: Texto da mensagem
            buttons: Lista de botões (máx 3)
                Exemplo: [
                    {"type": "reply", "reply": {"id": "aprovar_123", "title": "✅ Aprovar"}},
                    {"type": "reply", "reply": {"id": "rejeitar_123", "title": "❌ Rejeitar"}}
                ]

        Returns:
            tuple: (sucesso: bool, resposta: dict)
        """
        # Validações
        if not cls.validar_telefone(phone):
            return False, {"error": "Telefone inválido"}

        if len(buttons) > 3:
            return False, {"error": "Máximo de 3 botões permitido"}

        # Circuit Breaker
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN"}

        # Construir payload MegaAPI
        payload = {
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": buttons}
            }
        }

        return cls._send_request(payload)

    @classmethod
    def enviar_documento(cls, phone: str, document_url: str, filename: str, caption: str = None):
        """
        Envia documento (PDF, etc) via WhatsApp.

        Args:
            phone: Telefone no formato 5511999999999
            document_url: URL pública do documento
            filename: Nome do arquivo
            caption: Legenda opcional

        Returns:
            tuple: (sucesso: bool, resposta: dict)
        """
        # Validação
        if not cls.validar_telefone(phone):
            return False, {"error": "Telefone inválido"}

        # Circuit Breaker
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN"}

        # Construir payload MegaAPI
        payload = {
            "to": phone,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": filename
            }
        }

        if caption:
            payload["document"]["caption"] = caption

        return cls._send_request(payload)

    @classmethod
    def _send_request(cls, payload: dict):
        """
        Método interno para enviar requisição à MegaAPI.

        Args:
            payload: Payload completo da requisição

        Returns:
            tuple: (sucesso: bool, resposta: dict)
        """
        # Get Credentials
        from app.models.whatsapp_models import ConfiguracaoWhatsApp
        config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()

        if config and config.api_key_encrypted:
            try:
                fernet_key = current_app.config.get('FERNET_KEY')
                api_key = config.decrypt_key(fernet_key)
                url = current_app.config.get('MEGA_API_URL')
            except Exception as e:
                logger.error(f"Error decrypting API Key: {str(e)}")
                return False, {"error": "Decryption failed"}
        else:
            url = current_app.config.get('MEGA_API_URL')
            api_key = current_app.config.get('MEGA_API_KEY')

        if not url or not api_key:
            return False, {"error": "MegaAPI configuration missing"}

        # API Request
        try:
            response = requests.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                timeout=5
            )

            if response.status_code in [200, 201]:
                CircuitBreaker.record_success()
                RateLimiter.increment()
                return True, response.json()
            else:
                CircuitBreaker.record_failure()
                logger.warning(f"MegaAPI failure: {response.status_code} - {response.text}")
                return False, {"status": response.status_code, "text": response.text}

        except requests.exceptions.RequestException as e:
            CircuitBreaker.record_failure()
            logger.error(f"MegaAPI request exception: {str(e)}")
            return False, {"error": str(e)}