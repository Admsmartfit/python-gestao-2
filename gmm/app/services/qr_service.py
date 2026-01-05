import qrcode
import os
from flask import current_app
from io import BytesIO

class QRService:
    """
    Serviço para geração de QR Codes para equipamentos e ativos.
    Conforme PRD v3.1, Seção 4.6.
    """
    
    @staticmethod
    def gerar_qr_memory(conteudo):
        """
        Gera um QR Code e retorna como BytesIO (PNG).
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(conteudo)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return img_buffer

    @staticmethod
    def gerar_etiqueta_equipamento(equipamento_id):
        """
        Gera e salva uma etiqueta de equipamento no disco.
        O QR Code aponta para o WhatsApp com o comando pré-preenchido.
        """
        # Obter número do WhatsApp do sistema (da config ou banco)
        # Fallback para um número genérico se não configurado
        whatsapp_number = os.environ.get('WHATSAPP_BOT_NUMBER', '5511999999999')
        
        # URL conforme seção 4.6.3 da Spec
        conteudo = f"https://wa.me/{whatsapp_number}?text=EQUIP:{equipamento_id}"
        
        img_buffer = QRService.gerar_qr_memory(conteudo)
        
        filename = f"qr_equip_{equipamento_id}.png"
        directory = os.path.join(current_app.root_path, 'static', 'uploads', 'qrcodes')
        
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        filepath = os.path.join(directory, filename)
        with open(filepath, 'wb') as f:
            f.write(img_buffer.getvalue())
            
        return f"/static/uploads/qrcodes/{filename}"

    @staticmethod
    def gerar_lote_zip(equipamentos_ids):
        """
        Gera um conjunto de QR Codes e poderia zipá-los. 
        Implementação simplificada: retorna lista de paths.
        """
        paths = []
        for eid in equipamentos_ids:
            paths.append(QRService.gerar_etiqueta_equipamento(eid))
        return paths
