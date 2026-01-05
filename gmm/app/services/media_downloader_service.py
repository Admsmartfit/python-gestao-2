"""
Media Downloader Service
Responsável por baixar mídias (áudio, imagem, documento) da MegaAPI
"""
import requests
import os
from datetime import datetime
from uuid import uuid4
from flask import current_app


class MediaDownloaderService:
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    TIMEOUT = 30

    @staticmethod
    def download(url_megaapi, tipo_conteudo, bearer_token):
        """
        Baixa mídia da MegaAPI e salva localmente

        Args:
            url_megaapi: URL temporária da mídia na MegaAPI
            tipo_conteudo: 'image', 'audio', 'document'
            bearer_token: Token de autenticação da MegaAPI

        Returns:
            str: Caminho local do arquivo salvo

        Raises:
            ValueError: Se arquivo for muito grande
            Exception: Erros de download ou I/O
        """
        try:
            # Request com timeout
            response = requests.get(
                url_megaapi,
                headers={'Authorization': f'Bearer {bearer_token}'},
                timeout=MediaDownloaderService.TIMEOUT,
                stream=True
            )
            response.raise_for_status()

            # Valida tamanho
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > MediaDownloaderService.MAX_SIZE:
                raise ValueError(f"Arquivo muito grande: {content_length} bytes (max: {MediaDownloaderService.MAX_SIZE})")

            # Define caminho
            now = datetime.now()
            ano = now.strftime('%Y')
            mes = now.strftime('%m')
            ext = MediaDownloaderService._get_extension(tipo_conteudo, response.headers.get('Content-Type'))
            filename = f"{uuid4()}{ext}"

            # Caminho base da aplicação
            base_path = current_app.root_path
            directory = os.path.join(base_path, 'static', 'uploads', 'whatsapp', ano, mes)
            os.makedirs(directory, exist_ok=True)

            filepath = os.path.join(directory, filename)

            # Caminho relativo para salvar no banco
            relative_path = f"/static/uploads/whatsapp/{ano}/{mes}/{filename}"

            # Salva arquivo
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return relative_path

        except requests.exceptions.Timeout:
            raise Exception(f"Timeout ao baixar mídia (limite: {MediaDownloaderService.TIMEOUT}s)")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro HTTP ao baixar mídia: {str(e)}")
        except IOError as e:
            raise Exception(f"Erro ao salvar arquivo: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro inesperado ao baixar mídia: {str(e)}")

    @staticmethod
    def _get_extension(tipo_conteudo, mimetype):
        """
        Determina extensão do arquivo baseado no tipo de conteúdo e mimetype

        Args:
            tipo_conteudo: 'image', 'audio', 'document'
            mimetype: MIME type do arquivo (ex: 'audio/ogg')

        Returns:
            str: Extensão do arquivo (ex: '.ogg')
        """
        # Extensões baseadas no mimetype (preferência)
        if mimetype:
            mime_extensions = {
                'audio/ogg': '.ogg',
                'audio/mpeg': '.mp3',
                'audio/wav': '.wav',
                'audio/webm': '.webm',
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/webp': '.webp',
                'application/pdf': '.pdf',
                'application/msword': '.doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            }
            if mimetype in mime_extensions:
                return mime_extensions[mimetype]

        # Fallback baseado no tipo de conteúdo
        extensions = {
            'image': '.jpg',
            'audio': '.ogg',
            'document': '.pdf'
        }
        return extensions.get(tipo_conteudo, '.bin')

    @staticmethod
    def get_file_size(filepath):
        """
        Retorna o tamanho do arquivo em bytes

        Args:
            filepath: Caminho do arquivo

        Returns:
            int: Tamanho em bytes
        """
        try:
            return os.path.getsize(filepath)
        except:
            return 0
