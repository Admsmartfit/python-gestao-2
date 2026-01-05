import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)

class SMSService:
    """
    Serviço de SMS para redundância (Fallback).
    RF-013: Contingência e Resiliência.
    """
    
    @staticmethod
    def enviar_sms(telefone, mensagem):
        """
        Envia SMS via provedor redundante.
        
        Args:
            telefone (str): Telefone no formato 5511999999999
            mensagem (str): Texto da mensagem.
            
        Returns:
            tuple: (sucesso: bool, resposta: str)
        """
        # Formata telefone se necessário (Provedores de SMS costumam usar apenas DDI+DDD+NUM)
        # Ex: 5511999999999
        
        logger.info(f"FALLBACK SMS acionado para {telefone}")
        
        # Em produção, aqui integraria com Twilio, AWS SNS ou similar.
        # Exemplo Mock:
        try:
             # Simulação de chamada externa
             # requests.post("https://api.sms-provider.com/send", ...)
             
             logger.info(f"SMS enviado com sucesso via Mock: {mensagem[:30]}...")
             return True, "Enviado via Fallback SMS"
             
        except Exception as e:
            logger.error(f"Erro ao enviar SMS de fallback: {e}")
            return False, str(e)
