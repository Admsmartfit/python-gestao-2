import re

class ComandoParser:
    """
    Parses structured commands from text messages.
    Supports:
    - #COMPRA [CODE] [QUANTITY]
    - #PECA [CODE] [QUANTITY] - Request parts for OS
    - #STATUS [ANDAMENTO|CONCLUIDO|PAUSADO] - Update OS status
    - #SEPARADO [CODE] - Confirm part separation
    - #CONCLUIDO - Finish current OS
    - #AGENDA [DATE] - Schedule OS
    - #AJUDA
    """

    COMANDOS = {
        # Purchase request: #COMPRA ITEM-123 10
        '#COMPRA': r'#COMPRA\s+([A-Z0-9\-]+)\s+(\d+\.?\d*)',

        # Part request: #PECA ITEM-123 5
        '#PECA': r'#PECA\s+([A-Z0-9\-]+)\s+(\d+\.?\d*)',

        # Status update with optional state: #STATUS or #STATUS ANDAMENTO
        '#STATUS': r'#STATUS(?:\s+(ANDAMENTO|CONCLUIDO|PAUSADO|EM_ANDAMENTO))?',

        # Confirm separation: #SEPARADO ITEM-123
        '#SEPARADO': r'#SEPARADO\s+([A-Z0-9\-]+)',

        # Conclude OS: #CONCLUIDO or #CONCLUIDO with optional comment
        '#CONCLUIDO': r'#CONCLUIDO(?:\s+(.+))?',

        # Schedule: #AGENDA 25/12 or #AGENDA 25/12/2024
        '#AGENDA': r'#AGENDA\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',

        # Help command
        '#AJUDA': r'#AJUDA',

        # Menu command
        '#MENU': r'#MENU',

        # Cancel current operation
        '#CANCELAR': r'#CANCELAR'
    }

    @staticmethod
    def parse(texto: str) -> dict:
        """
        Parses the text and returns a dictionary with the command and parameters.
        Returns None if no command is found.
        Example return:
        {
            'comando': 'COMPRA',
            'params': {'item': 'CABO-10MM', 'quantidade': 50.0},
            'texto_original': '#COMPRA ...'
        }
        """
        if not texto:
            return None

        texto = texto.strip().upper()

        for cmd, pattern in ComandoParser.COMANDOS.items():
            match = re.match(pattern, texto)
            if match:
                resultado = {
                    'comando': cmd.replace('#', ''),
                    'texto_original': texto
                }

                # Parse parameters based on command type
                if cmd == '#COMPRA':
                    resultado['params'] = {
                        'item': match.group(1),
                        'quantidade': float(match.group(2))
                    }

                elif cmd == '#PECA':
                    resultado['params'] = {
                        'item': match.group(1),
                        'quantidade': float(match.group(2))
                    }

                elif cmd == '#STATUS':
                    novo_status = match.group(1) if match.lastindex >= 1 else None
                    resultado['params'] = {
                        'novo_status': novo_status
                    }

                elif cmd == '#SEPARADO':
                    resultado['params'] = {
                        'item': match.group(1)
                    }

                elif cmd == '#CONCLUIDO':
                    observacao = match.group(1) if match.lastindex >= 1 else None
                    resultado['params'] = {
                        'observacao': observacao
                    }

                elif cmd == '#AGENDA':
                    resultado['params'] = {
                        'data': match.group(1)
                    }

                else:
                    resultado['params'] = {}

                return resultado

        return None

    @staticmethod
    def is_command(texto: str) -> bool:
        """
        Checks if the text starts with a command character.
        """
        if not texto:
            return False
        texto = texto.strip()
        return texto.startswith('#')

    @staticmethod
    def extract_confirmation(texto: str) -> str:
        """
        Extracts confirmation response (ACEITO, RECUSO, SIM, NAO).
        Returns the normalized confirmation or None.
        """
        if not texto:
            return None

        texto = texto.strip().upper()

        confirmacoes = {
            'ACEITO': 'ACEITO',
            'ACEITAR': 'ACEITO',
            'SIM': 'ACEITO',
            'OK': 'ACEITO',
            'CONFIRMO': 'ACEITO',
            'RECUSO': 'RECUSO',
            'RECUSAR': 'RECUSO',
            'NAO': 'RECUSO',
            'NÃO': 'RECUSO',
            'NEGAR': 'RECUSO',
            'CANCELAR': 'CANCELAR'
        }

        return confirmacoes.get(texto)

    @staticmethod
    def extract_rating(texto: str) -> int:
        """
        Extracts a rating from 1-5 from the text.
        Returns the rating or None.
        """
        if not texto:
            return None

        texto = texto.strip()

        # Check for single digit 1-5
        if texto in ['1', '2', '3', '4', '5']:
            return int(texto)

        # Check for star emojis (⭐)
        stars = texto.count('⭐')
        if 1 <= stars <= 5:
            return stars

        # Check for written numbers
        numeros = {
            'UM': 1, 'UMA': 1,
            'DOIS': 2, 'DUAS': 2,
            'TRES': 3, 'TRÊS': 3,
            'QUATRO': 4,
            'CINCO': 5
        }

        texto_upper = texto.upper()
        for palavra, valor in numeros.items():
            if palavra in texto_upper:
                return valor

        return None

    @staticmethod
    def extract_date(texto: str) -> dict:
        """
        Extracts a date from text in formats: DD/MM, DD/MM/YY, DD/MM/YYYY
        Returns dict with day, month, year or None.
        """
        if not texto:
            return None

        # Pattern for dates
        pattern = r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?'
        match = re.search(pattern, texto)

        if match:
            from datetime import datetime
            day = int(match.group(1))
            month = int(match.group(2))
            year = match.group(3)

            if year:
                year = int(year)
                if year < 100:
                    year += 2000
            else:
                year = datetime.now().year

            return {
                'dia': day,
                'mes': month,
                'ano': year
            }

        return None
