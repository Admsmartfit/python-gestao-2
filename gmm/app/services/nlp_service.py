import requests
import json
import logging
import base64
import mimetypes
from flask import current_app

logger = logging.getLogger(__name__)

class NLPService:
    """
    Serviço de Processamento de Linguagem Natural (NLP).
    Suporta OpenAI (GPT) e Google Gemini.
    Destinado a extrair entidades estruturadas de mensagens informais ou transcrições.
    """

    @staticmethod
    def get_ai_provider():
        """Retorna o provedor de IA configurado (openai ou gemini)."""
        return current_app.config.get('AI_PROVIDER', 'openai').lower()

    @staticmethod
    def extrair_entidades(texto):
        """
        Extrai entidades (Equipamento, Local, Urgência) de um texto.

        Args:
            texto (str): O texto original ou transcrição.

        Returns:
            dict: Dicionário com 'equipamento', 'local', 'urgencia', 'descricao' ou None.
        """
        provider = NLPService.get_ai_provider()

        if provider == 'gemini':
            return NLPService._extrair_com_gemini(texto)
        else:
            return NLPService._extrair_com_openai(texto)

    @staticmethod
    def _get_prompt(texto):
        """Retorna o prompt padrão para extração de entidades."""
        return f"""
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

    @staticmethod
    def _extrair_com_openai(texto):
        """Extrai entidades usando OpenAI GPT."""
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY não configurada. NLP via OpenAI desativado.")
            return None

        prompt = NLPService._get_prompt(texto)

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

    @staticmethod
    def _extrair_com_gemini(texto):
        """Extrai entidades usando Google Gemini."""
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY não configurada. NLP via Gemini desativado.")
            return None

        prompt = NLPService._get_prompt(texto)

        # Gemini API endpoint
        model = current_app.config.get('GEMINI_MODEL', 'gemini-1.5-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 150
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            content = result['candidates'][0]['content']['parts'][0]['text']

            # Remove possíveis marcações de markdown do JSON
            content = content.replace('```json', '').replace('```', '').strip()

            return json.loads(content)
        except Exception as e:
            logger.error(f"Erro ao chamar Gemini para NLP: {e}")
            return None

    @staticmethod
    def transcrever_audio(audio_path):
        """
        Transcreve áudio para texto tentando múltiplos provedores.
        
        Args:
            audio_path (str): Caminho para o arquivo de áudio.
        Returns:
            str: Texto transcrito ou None em caso de erro.
        """
        provider = NLPService.get_ai_provider()
        
        # 1. Tentar transcrição nativa baseada no provedor principal
        if provider == 'gemini':
            texto = NLPService._transcrever_com_gemini_audio(audio_path)
            if texto: return texto
            
            # 2. Tentar Google Cloud STT como segunda opção para ecossistema Google
            texto = NLPService._transcrever_com_google_stt(audio_path)
            if texto: return texto
            
        # 3. Tentar OpenAI Whisper (como provedor principal ou fallback)
        return NLPService._transcrever_com_openai_whisper(audio_path)

    @staticmethod
    def _transcrever_com_openai_whisper(audio_path):
        """Transcreve áudio usando OpenAI Whisper."""
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            logger.debug("OPENAI_API_KEY não configurada para Whisper.")
            return None

        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            with open(audio_path, 'rb') as audio_file:
                files = {
                    'file': audio_file,
                    'model': (None, 'whisper-1')
                }
                response = requests.post(url, headers=headers, files=files, timeout=60)
                response.raise_for_status()
                return response.json().get('text', '')
        except Exception as e:
            logger.error(f"Erro ao transcrever com OpenAI Whisper: {e}")
            return None

    @staticmethod
    def _transcrever_com_gemini_audio(audio_path):
        """Transcreve áudio usando a capacidade multimodal nativa do Gemini 1.5."""
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return None

        try:
            mime_type, _ = mimetypes.guess_type(audio_path)
            if not mime_type: mime_type = 'audio/mpeg'
            
            with open(audio_path, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')

            model = current_app.config.get('GEMINI_MODEL', 'gemini-1.5-flash')
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Transcreva o áudio abaixo com precisão, mantendo pontuação e sem adicionar comentários extras."},
                        {"inline_data": {"mime_type": mime_type, "data": audio_data}}
                    ]
                }]
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            logger.warning(f"Erro na transcrição nativa do Gemini: {e}")
            return None

    @staticmethod
    def _transcrever_com_google_stt(audio_path):
        """Transcreve áudio usando Google Cloud Speech-to-Text API (REST)."""
        api_key = current_app.config.get('GOOGLE_STT_API_KEY')
        if not api_key:
            return None

        try:
            with open(audio_path, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')

            url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
            
            payload = {
                "config": {
                    "encoding": "MP3", # O WhatsApp envia OGG, mas convertemos ou usamos detecção
                    "sampleRateHertz": 16000,
                    "languageCode": "pt-BR",
                    "enableAutomaticPunctuation": True
                },
                "audio": {
                    "content": audio_data
                }
            }
            
            # Tentar detectar encoding pelo mime
            mime_type, _ = mimetypes.guess_type(audio_path)
            if 'ogg' in str(mime_type).lower():
                payload['config']['encoding'] = 'OGG_OPUS'
            elif 'wav' in str(mime_type).lower():
                payload['config']['encoding'] = 'LINEAR16'

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            if 'results' in result:
                return result['results'][0]['alternatives'][0]['transcript']
            return None
        except Exception as e:
            logger.warning(f"Erro na transcrição Google STT: {e}")
            return None

    @staticmethod
    def chat_completion(mensagem, contexto=None):
        """
        Gera uma resposta de chat usando IA.

        Args:
            mensagem (str): Mensagem do usuário.
            contexto (str, optional): Contexto adicional para a conversa.

        Returns:
            str: Resposta da IA ou None em caso de erro.
        """
        provider = NLPService.get_ai_provider()

        if provider == 'gemini':
            return NLPService._chat_com_gemini(mensagem, contexto)
        else:
            return NLPService._chat_com_openai(mensagem, contexto)

    @staticmethod
    def _chat_com_openai(mensagem, contexto=None):
        """Chat usando OpenAI GPT."""
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            return None

        messages = []
        if contexto:
            messages.append({"role": "system", "content": contexto})
        messages.append({"role": "user", "content": mensagem})

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Erro no chat OpenAI: {e}")
            return None

    @staticmethod
    def _chat_com_gemini(mensagem, contexto=None):
        """Chat usando Google Gemini."""
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return None

        prompt = mensagem
        if contexto:
            prompt = f"{contexto}\n\nUsuário: {mensagem}"

        model = current_app.config.get('GEMINI_MODEL', 'gemini-1.5-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            logger.error(f"Erro no chat Gemini: {e}")
            return None
