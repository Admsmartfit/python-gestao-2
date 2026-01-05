import requests
import json
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class NLPService:
    """
    Serviço de Processamento de Linguagem Natural (NLP) usando OpenAI.
    Destinado a extrair entidades estruturadas de mensagens informais ou transcrições.
    """
    
    @staticmethod
    def extrair_entidades(texto):
        """
        Extrai entidades (Equipamento, Local, Urgência) de um texto.
        
        Args:
            texto (str): O texto original ou transcrição.
            
        Returns:
            dict: Dicionário com 'equipamento', 'local', 'urgencia', 'descricao' ou None.
        """
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY não configurada. NLP via OpenAI desativado.")
            return None

        prompt = f"""
        Analise o relato de manutenção abaixo e extraia as informações em formato JSON válido.
        Se uma informação não for encontrada, use null.
        
        Campos:
        - equipamento: O objeto que precisa de reparo (ex: ar condicionado, bebedouro, luz).
        - local: Onde se encontra o problema (ex: recepção, sala 202, estacionamento).
        - urgencia: Classifique em 'baixa', 'media', 'alta' ou 'urgente'.
        - resumo: Um resumo técnico curto e direto do defeito citado.

        Relato: "{texto}"

        Retorne APENAS o objeto JSON.
        """

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 150
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            content = response.json()['choices'][0]['message']['content']
            # Remove possíveis marcações de markdown do JSON
            content = content.replace('```json', '').replace('```', '').strip()
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"Erro ao chamar OpenAI para NLP: {e}")
            return None
