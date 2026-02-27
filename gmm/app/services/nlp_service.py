import re
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

    # MIME types OGG que o WhatsApp usa
    _WHATSAPP_AUDIO_MIME = 'audio/ogg'

    @staticmethod
    def get_ai_provider():
        """Retorna o provedor de IA configurado (openai ou gemini)."""
        return current_app.config.get('AI_PROVIDER', 'openai').lower()

    # -------------------------------------------------------------------------
    # RF02 – Utilitários de parse JSON
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_json_seguro(content: str):
        """Extrai e faz parse do JSON mesmo que a IA inclua texto extra ou Markdown."""
        if not content:
            return None
        # Remove blocos Markdown
        content = content.replace('```json', '').replace('```', '').strip()
        # Extrai o primeiro objeto JSON encontrado no texto
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Falha ao decodificar JSON da IA. Conteúdo recebido: {content[:300]}")
            return None

    @staticmethod
    def _normalizar_dados_ia(dados: dict) -> dict:
        """Garante que os campos retornados pela IA são compatíveis com o banco."""
        if not dados:
            return dados

        urgencia_raw = str(dados.get('urgencia', '')).lower()
        if 'urgente' in urgencia_raw:
            dados['urgencia'] = 'urgente'
        elif 'alta' in urgencia_raw:
            dados['urgencia'] = 'alta'
        elif 'baixa' in urgencia_raw:
            dados['urgencia'] = 'baixa'
        else:
            dados['urgencia'] = 'media'

        return dados

    # -------------------------------------------------------------------------
    # RF01 – Detecção de MIME type para áudio
    # -------------------------------------------------------------------------

    @staticmethod
    def _detectar_mime_audio(audio_path: str) -> str:
        """
        Detecta o MIME type do áudio.
        WhatsApp envia OGG/Opus. Se não houver extensão clara, assume audio/ogg.
        """
        mime_type, _ = mimetypes.guess_type(audio_path)
        if mime_type:
            return mime_type
        # Fallback: extensões comuns sem mime registrado
        path_lower = audio_path.lower()
        if path_lower.endswith('.ogg') or path_lower.endswith('.opus'):
            return 'audio/ogg'
        if path_lower.endswith('.mp3'):
            return 'audio/mpeg'
        if path_lower.endswith('.wav'):
            return 'audio/wav'
        if path_lower.endswith('.m4a'):
            return 'audio/mp4'
        # WhatsApp salva áudio sem extensão clara — assume OGG Opus
        return NLPService._WHATSAPP_AUDIO_MIME

    # -------------------------------------------------------------------------
    # Extração de Entidades
    # -------------------------------------------------------------------------

    @staticmethod
    def extrair_entidades(texto):
        """
        Extrai entidades (Equipamento, Local, Urgência) de um texto.
        Returns dict com 'equipamento', 'local', 'urgencia', 'resumo' ou None.
        """
        provider = NLPService.get_ai_provider()

        if provider == 'gemini':
            resultado = NLPService._extrair_com_gemini(texto)
        else:
            resultado = NLPService._extrair_com_openai(texto)

        if resultado is None:
            # RF03: log crítico se nenhum provedor funcionou
            gemini_key = current_app.config.get('GEMINI_API_KEY')
            openai_key = current_app.config.get('OPENAI_API_KEY')
            if not gemini_key and not openai_key:
                logger.critical("NLPService: Nenhum provedor de IA configurado (GEMINI_API_KEY e OPENAI_API_KEY ausentes).")
            return None

        return NLPService._normalizar_dados_ia(resultado)

    @staticmethod
    def _get_prompt(texto):
        """Retorna o prompt para extração de entidades — instrui a IA a retornar APENAS JSON."""
        return f"""Analise o relato de manutenção abaixo e extraia as informações.

Retorne SOMENTE um objeto JSON válido, sem texto adicional, sem blocos de código Markdown, sem explicações.

Campos obrigatórios:
- "equipamento": O objeto que precisa de reparo (ex: "ar condicionado", "bebedouro", "luz"). Use null se não identificado.
- "local": Onde se encontra o problema (ex: "recepção", "sala 202"). Use null se não identificado.
- "urgencia": Classifique APENAS como um destes valores: "baixa", "media", "alta" ou "urgente".
- "resumo": Um resumo técnico curto e direto do defeito citado.

Relato: "{texto}"

JSON:"""

    @staticmethod
    def _extrair_com_openai(texto):
        """Extrai entidades usando OpenAI GPT."""
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY não configurada. NLP via OpenAI desativado.")
            return None

        prompt = NLPService._get_prompt(texto)
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 200
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            return NLPService._parse_json_seguro(content)
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
        model = current_app.config.get('GEMINI_MODEL', 'gemini-2.0-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}
        }

        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            result = response.json()
            content = result['candidates'][0]['content']['parts'][0]['text']
            return NLPService._parse_json_seguro(content)
        except requests.exceptions.Timeout:
            logger.error("Timeout ao chamar Gemini para NLP.")
            return None
        except Exception as e:
            logger.error(f"Erro ao chamar Gemini para NLP: {e}")
            return None

    # -------------------------------------------------------------------------
    # Transcrição de Áudio
    # -------------------------------------------------------------------------

    @staticmethod
    def transcrever_audio(audio_path):
        """
        Transcreve áudio para texto tentando múltiplos provedores.
        Returns str transcrito ou None.
        """
        provider = NLPService.get_ai_provider()

        if provider == 'gemini':
            texto = NLPService._transcrever_com_gemini_audio(audio_path)
            if texto:
                return texto
            # Fallback para Google Cloud STT apenas se chave configurada
            if current_app.config.get('GOOGLE_STT_API_KEY'):
                texto = NLPService._transcrever_com_google_stt(audio_path)
                if texto:
                    return texto

        # Fallback para OpenAI Whisper apenas se chave configurada
        if current_app.config.get('OPENAI_API_KEY'):
            return NLPService._transcrever_com_openai_whisper(audio_path)

        # RF03: nenhum provedor disponível
        logger.critical(
            "NLPService: Nenhum provedor de STT disponível. "
            "Configure GEMINI_API_KEY, OPENAI_API_KEY ou GOOGLE_STT_API_KEY."
        )
        return None

    @staticmethod
    def _transcrever_com_gemini_audio(audio_path):
        """Transcreve áudio usando a capacidade multimodal nativa do Gemini."""
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return None

        # RF01: detectar MIME corretamente (WhatsApp envia OGG Opus)
        mime_type = NLPService._detectar_mime_audio(audio_path)
        mime_tentativas = [mime_type]
        # Se o primeiro não for OGG, tenta OGG como alternativa
        if mime_type != 'audio/ogg':
            mime_tentativas.append('audio/ogg')
        # E vice-versa
        if mime_type == 'audio/ogg' and 'audio/mpeg' not in mime_tentativas:
            mime_tentativas.append('audio/mpeg')

        model = current_app.config.get('GEMINI_MODEL', 'gemini-2.0-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        try:
            with open(audio_path, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')
        except OSError as e:
            logger.error(f"Não foi possível ler o arquivo de áudio {audio_path}: {e}")
            return None

        for mime in mime_tentativas:
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Transcreva o áudio abaixo com precisão em português brasileiro, mantendo pontuação. Retorne somente o texto transcrito, sem comentários."},
                        {"inline_data": {"mime_type": mime, "data": audio_data}}
                    ]
                }]
            }
            try:
                response = requests.post(url, json=payload, timeout=60)
                if response.status_code == 400:
                    err = response.json().get('error', {}).get('message', '')
                    logger.warning(f"Gemini STT retornou 400 com mime={mime}: {err}. Tentando próximo MIME.")
                    continue
                response.raise_for_status()
                result = response.json()
                texto = result['candidates'][0]['content']['parts'][0]['text'].strip()
                if texto:
                    logger.info(f"Transcrição Gemini bem-sucedida com mime={mime} ({len(texto)} chars).")
                    return texto
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout na transcrição Gemini com mime={mime}.")
            except Exception as e:
                logger.warning(f"Erro na transcrição Gemini com mime={mime}: {e}")

        logger.error("Gemini STT falhou em todas as tentativas de MIME type.")
        return None

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
                files = {'file': audio_file, 'model': (None, 'whisper-1')}
                response = requests.post(url, headers=headers, files=files, timeout=60)
                response.raise_for_status()
                return response.json().get('text', '')
        except Exception as e:
            logger.error(f"Erro ao transcrever com OpenAI Whisper: {e}")
            return None

    @staticmethod
    def _transcrever_com_google_stt(audio_path):
        """Transcreve áudio usando Google Cloud Speech-to-Text API (REST)."""
        api_key = current_app.config.get('GOOGLE_STT_API_KEY')
        if not api_key:
            return None

        mime_type = NLPService._detectar_mime_audio(audio_path)
        encoding = 'MP3'
        if 'ogg' in mime_type:
            encoding = 'OGG_OPUS'
        elif 'wav' in mime_type:
            encoding = 'LINEAR16'

        try:
            with open(audio_path, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')

            url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
            payload = {
                "config": {
                    "encoding": encoding,
                    "sampleRateHertz": 16000,
                    "languageCode": "pt-BR",
                    "enableAutomaticPunctuation": True
                },
                "audio": {"content": audio_data}
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            if result.get('results'):
                return result['results'][0]['alternatives'][0]['transcript']
            return None
        except Exception as e:
            logger.warning(f"Erro na transcrição Google STT: {e}")
            return None

    # -------------------------------------------------------------------------
    # Chat
    # -------------------------------------------------------------------------

    @staticmethod
    def chat_completion(mensagem, contexto=None):
        """Gera uma resposta de chat usando IA."""
        provider = NLPService.get_ai_provider()
        if provider == 'gemini':
            return NLPService._chat_com_gemini(mensagem, contexto)
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
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {"model": "gpt-3.5-turbo", "messages": messages, "temperature": 0.7, "max_tokens": 500}

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

        prompt = f"{contexto}\n\nUsuário: {mensagem}" if contexto else mensagem
        model = current_app.config.get('GEMINI_MODEL', 'gemini-2.0-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
        }

        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except requests.exceptions.Timeout:
            logger.error("Timeout no chat Gemini.")
            return None
        except Exception as e:
            logger.error(f"Erro no chat Gemini: {e}")
            return None
