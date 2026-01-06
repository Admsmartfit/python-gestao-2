from weasyprint import HTML
from jinja2 import Template
from flask import current_app
import os
from datetime import datetime

class PDFGeneratorService:
    """Service for generating PDF documents using WeasyPrint and Jinja2 templates"""

    @staticmethod
    def gerar_pdf_pedido(pedido_id):
        """
        Gera PDF profissional de pedido de compra.

        Args:
            pedido_id: ID do pedido

        Returns:
            str: Caminho do arquivo PDF gerado
        """
        from app.models.estoque_models import PedidoCompra

        # 1. Buscar pedido completo
        pedido = PedidoCompra.query.get(pedido_id)
        if not pedido:
            raise ValueError(f"Pedido {pedido_id} não encontrado")

        # 2. Template HTML
        template_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            color: #333;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #007bff;
            padding-bottom: 15px;
        }
        .header h1 {
            color: #007bff;
            margin: 10px 0;
            font-size: 24pt;
        }
        .info-container {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        .info-box {
            background-color: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-left: 5px solid #007bff;
            width: 100%;
        }
        .info-box h3 {
            margin-top: 0;
            margin-bottom: 10px;
            color: #007bff;
            font-size: 12pt;
            text-transform: uppercase;
        }
        .info-box p {
            margin: 5px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th {
            background-color: #007bff;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }
        td {
            border-bottom: 1px solid #dee2e6;
            padding: 10px;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .total-row {
            background-color: #e9ecef !important;
            font-weight: bold;
            font-size: 13pt;
        }
        .footer {
            margin-top: 50px;
            text-align: center;
            font-size: 9pt;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
            padding-top: 15px;
        }
        .text-right {
            text-align: right;
        }
        .status-stamp {
            position: absolute;
            top: 50px;
            right: 50px;
            border: 4px solid #28a745;
            color: #28a745;
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 18pt;
            font-weight: bold;
            transform: rotate(15deg);
            opacity: 0.8;
            text-transform: uppercase;
        }
    </style>
</head>
<body>
    {% if pedido.status == 'aprovado' or pedido.status == 'pedido' %}
    <div class="status-stamp">Aprovado</div>
    {% endif %}

    <div class="header">
        <h1>PEDIDO DE COMPRA</h1>
        <p><strong>Número:</strong> {{ pedido.numero_pedido or pedido.id }}</p>
        <p><strong>Data de Emissão:</strong> {{ pedido.data_solicitacao.strftime('%d/%m/%Y %H:%M') }}</p>
    </div>

    <div class="info-box">
        <h3>Fornecedor</h3>
        <p><strong>{{ pedido.fornecedor.nome if pedido.fornecedor else 'N/A' }}</strong></p>
        {% if pedido.fornecedor and pedido.fornecedor.cnpj %}
        <p>CNPJ: {{ pedido.fornecedor.cnpj }}</p>
        {% endif %}
        {% if pedido.fornecedor and pedido.fornecedor.endereco %}
        <p>Endereço: {{ pedido.fornecedor.endereco }}</p>
        {% endif %}
        <p>Telefone: {{ (pedido.fornecedor.telefone or pedido.fornecedor.whatsapp) if pedido.fornecedor else 'N/A' }}</p>
        <p>Email: {{ pedido.fornecedor.email if pedido.fornecedor else 'N/A' }}</p>
    </div>

    <div class="info-box">
        <h3>Dados do Pedido</h3>
        <p><strong>Solicitante:</strong> {{ pedido.solicitante.nome if pedido.solicitante else 'N/A' }}</p>
        <p><strong>Unidade de Destino:</strong> {{ pedido.unidade_destino.nome if pedido.unidade_destino else 'Não especificada' }}</p>
        {% if pedido.aprovador %}
        <p><strong>Aprovado por:</strong> {{ pedido.aprovador.nome }} em {{ pedido.data_aprovacao.strftime('%d/%m/%Y %H:%M') if pedido.data_aprovacao else 'N/A' }}</p>
        {% endif %}
    </div>

    <h3>Itens do Pedido</h3>
    <table>
        <thead>
            <tr>
                <th>Código</th>
                <th>Descrição</th>
                <th class="text-right">Quantidade</th>
                <th class="text-right">Valor Total</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{{ pedido.peca.codigo }}</td>
                <td>{{ pedido.peca.nome }}</td>
                <td class="text-right">{{ pedido.quantidade }} {{ pedido.peca.unidade_medida }}</td>
                <td class="text-right">R$ {{ "%.2f"|format(pedido.valor_total or 0) }}</td>
            </tr>
            <tr class="total-row">
                <td colspan="3" class="text-right">TOTAL DO PEDIDO</td>
                <td class="text-right">R$ {{ "%.2f"|format(pedido.valor_total or 0) }}</td>
            </tr>
        </tbody>
    </table>

    {% if pedido.justificativa %}
    <div class="info-box">
        <h3>Justificativa / Observações</h3>
        <p>{{ pedido.justificativa }}</p>
    </div>
    {% endif %}

    <div class="footer">
        <p>Este é um documento eletrônico gerado automaticamente pelo Sistema GMM</p>
        <p>Data de geração: {{ datetime.now().strftime('%d/%m/%Y %H:%M:%S') }}</p>
    </div>
</body>
</html>
        """

        # 3. Renderizar template
        template = Template(template_html)
        html_content = template.render(
            pedido=pedido,
            datetime=datetime
        )

        # 4. Garantir que pasta existe
        pasta_pedidos = os.path.join(
            current_app.root_path,
            'static', 'uploads', 'pedidos'
        )
        os.makedirs(pasta_pedidos, exist_ok=True)

        # 5. Gerar PDF
        filename = f"PEDIDO_{pedido.numero_pedido or pedido.id}.pdf"
        filepath = os.path.join(pasta_pedidos, filename)

        HTML(string=html_content).write_pdf(filepath)

        return filepath
