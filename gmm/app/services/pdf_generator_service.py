"""
PDF Generator Service
Generates PDF documents for purchase orders using ReportLab
"""
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


class PDFGeneratorService:
    """Service for generating PDF documents"""

    @staticmethod
    def gerar_pdf_pedido_compra(pedido):
        """
        Generates a purchase order PDF document.

        Args:
            pedido: PedidoCompra model instance

        Returns:
            BytesIO: PDF file buffer
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Container for elements
        elements = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a5490'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        subtitle_style = ParagraphStyle(
            'CustomSubTitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=20
        )

        # Title
        title = Paragraph("PEDIDO DE COMPRA", title_style)
        elements.append(title)

        # Subtitle with ID and date
        subtitle_text = f"Pedido #{pedido.id} | Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
        subtitle = Paragraph(subtitle_text, subtitle_style)
        elements.append(subtitle)

        elements.append(Spacer(1, 0.5*cm))

        # Purchase order info table
        data_info = [
            ['Status:', pedido.status.replace('_', ' ').title()],
            ['Data Solicitação:', pedido.data_solicitacao.strftime('%d/%m/%Y %H:%M')],
            ['Solicitante:', pedido.solicitante.nome if pedido.solicitante else 'N/A'],
            ['Aprovador:', pedido.aprovador.nome if pedido.aprovador else 'Pendente'],
        ]

        table_info = Table(data_info, colWidths=[5*cm, 12*cm])
        table_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(table_info)
        elements.append(Spacer(1, 1*cm))

        # Item details
        item_title = Paragraph("<b>DETALHES DO ITEM</b>", styles['Heading2'])
        elements.append(item_title)
        elements.append(Spacer(1, 0.3*cm))

        # Calculate values
        valor_unitario = float(pedido.peca.valor_unitario) if pedido.peca.valor_unitario else 0.0
        quantidade = float(pedido.quantidade)
        valor_total = valor_unitario * quantidade

        data_item = [
            ['Código', 'Nome', 'Unidade', 'Qtd', 'Valor Unit.', 'Valor Total'],
            [
                pedido.peca.codigo,
                pedido.peca.nome,
                pedido.peca.unidade_medida,
                f'{quantidade:.2f}',
                f'R$ {valor_unitario:.2f}',
                f'R$ {valor_total:.2f}'
            ]
        ]

        table_item = Table(data_item, colWidths=[3*cm, 5*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm])
        table_item.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))

        elements.append(table_item)
        elements.append(Spacer(1, 0.5*cm))

        # Total summary (aligned right)
        total_style = ParagraphStyle(
            'TotalStyle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#1a5490')
        )
        total_text = f"VALOR TOTAL: R$ {valor_total:.2f}"
        total_paragraph = Paragraph(total_text, total_style)
        elements.append(total_paragraph)

        elements.append(Spacer(1, 1*cm))

        # Supplier info (if available)
        if pedido.fornecedor:
            fornecedor_title = Paragraph("<b>FORNECEDOR</b>", styles['Heading2'])
            elements.append(fornecedor_title)
            elements.append(Spacer(1, 0.3*cm))

            data_fornecedor = [
                ['Nome:', pedido.fornecedor.nome],
                ['Email:', pedido.fornecedor.email],
                ['Telefone:', pedido.fornecedor.telefone or 'N/A'],
                ['Prazo Médio:', f'{pedido.fornecedor.prazo_medio_entrega_dias:.0f} dias'],
            ]

            table_fornecedor = Table(data_fornecedor, colWidths=[5*cm, 12*cm])
            table_fornecedor.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            elements.append(table_fornecedor)
            elements.append(Spacer(1, 1*cm))

        # Justification (if exists)
        if pedido.justificativa:
            justif_title = Paragraph("<b>JUSTIFICATIVA</b>", styles['Heading2'])
            elements.append(justif_title)
            elements.append(Spacer(1, 0.3*cm))

            justif_text = Paragraph(pedido.justificativa, styles['Normal'])
            elements.append(justif_text)
            elements.append(Spacer(1, 1*cm))

        # Footer with signatures (if approved)
        if pedido.status == 'aprovado':
            elements.append(Spacer(1, 2*cm))

            signature_data = [
                ['_' * 40, '_' * 40],
                ['Solicitante', 'Aprovador'],
                [
                    pedido.solicitante.nome if pedido.solicitante else 'N/A',
                    pedido.aprovador.nome if pedido.aprovador else 'N/A'
                ]
            ]

            signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
            signature_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('TOPPADDING', (0, 1), (-1, -1), 10),
            ]))

            elements.append(signature_table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        return buffer

    @staticmethod
    def salvar_pdf_pedido(pedido, caminho):
        """
        Saves purchase order PDF to a file.

        Args:
            pedido: PedidoCompra model instance
            caminho: Full file path to save PDF

        Returns:
            bool: True if successful
        """
        try:
            buffer = PDFGeneratorService.gerar_pdf_pedido_compra(pedido)
            with open(caminho, 'wb') as f:
                f.write(buffer.getvalue())
            return True
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error saving PDF: {e}")
            return False
