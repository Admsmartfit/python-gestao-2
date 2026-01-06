# PRD - IMPLEMENTAÇÃO DE GAPS DO SISTEMA GMM

**Product Requirements Document**

**Versão**: 1.0
**Data**: Janeiro 2026
**Status**: Planejamento
**Objetivo**: Implementar funcionalidades faltantes identificadas na análise de gap para atingir 100% de completude

---

## 📋 ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Sprint 1 - Funcionalidades Críticas](#2-sprint-1---funcionalidades-críticas-1-semana)
3. [Sprint 2 - Alertas e Notificações](#3-sprint-2---alertas-e-notificações-1-semana)
4. [Sprint 3 - QR Code Completo](#4-sprint-3---qr-code-completo-1-semana)
5. [Sprint 4 - Analytics Avançado](#5-sprint-4---analytics-avançado-1-semana)
6. [Infraestrutura e Configuração](#6-infraestrutura-e-configuração)
7. [Critérios de Aceitação](#7-critérios-de-aceitação)
8. [Riscos e Mitigações](#8-riscos-e-mitigações)

---

## 1. VISÃO GERAL

### 1.1 Contexto

O Sistema GMM está com **85% de completude** (76% completo + 9% parcial). Este PRD detalha a implementação dos **30 gaps identificados**, organizados em **4 sprints de 1 semana** cada, totalizando **~2.140 linhas de código**.

### 1.2 Objetivos

- ✅ Atingir **100% de completude funcional**
- ✅ Implementar alertas automatizados e notificações proativas
- ✅ Completar módulo QR Code com fluxo conversacional
- ✅ Expandir analytics com gráficos avançados
- ✅ Preparar sistema para produção

### 1.3 Priorização

| Sprint | Foco | Linhas de Código | Prioridade |
|--------|------|------------------|------------|
| Sprint 1 | Funcionalidades Críticas | ~380 linhas | 🔴 ALTA |
| Sprint 2 | Alertas Automatizados | ~330 linhas | 🔴 ALTA |
| Sprint 3 | QR Code Completo | ~330 linhas | 🟡 MÉDIA |
| Sprint 4 | Analytics Avançado | ~450 linhas | 🟡 MÉDIA |

### 1.4 Dependências

- **OpenAI API Key**: Para NLP e transcrição (já configurado)
- **MegaAPI WhatsApp**: Para envio de mensagens (já configurado)
- **Redis**: Para Circuit Breaker e Rate Limiter (já configurado)
- **WeasyPrint ou ReportLab**: Para geração de PDFs (instalar)
- **Celery Beat**: Para tasks agendadas (já configurado)

---

## 2. SPRINT 1 - FUNCIONALIDADES CRÍTICAS (1 semana)

**Objetivo**: Atingir 95% de completude nos módulos principais

### 2.1 US-001: Criação Automática de OS por Voz (Confirmação)

**Prioridade**: 🔴 ALTA
**Estimativa**: ~50 linhas de código
**Arquivo**: `app/services/roteamento_service.py`

#### Descrição

Completar o fluxo de criação automática de OS iniciado por áudio. Atualmente, o sistema transcreve o áudio, extrai entidades via NLP e envia mensagem de confirmação, mas não processa a resposta "SIM".

#### Requisitos Funcionais

1. **Processamento da Confirmação**
   - Quando usuário responde "SIM" (case-insensitive), criar OS automaticamente
   - Quando usuário responde "NÃO", cancelar fluxo e limpar estado
   - Aceitar variações: "sim", "SIM", "Sim", "s", "S", "yes"

2. **Busca de Equipamento**
   - Extrair nome do equipamento da entidade NLP
   - Buscar no catálogo usando ILIKE (case-insensitive, partial match)
   - Se múltiplos resultados, solicitar clarificação

3. **Criação da OS**
   - Criar `OrdemServico` com:
     - `numero_os`: Formato `OS-YYYYMMDDHHMMSS`
     - `equipamento_id`: Obtido da busca
     - `unidade_id`: Obtido da entidade NLP ou unidade padrão do técnico
     - `titulo`: Gerado automaticamente baseado em NLP
     - `descricao`: Resumo da entidade NLP
     - `prioridade`: Obtido da entidade NLP
     - `origem_criacao`: **'whatsapp_bot'**
     - `status`: 'aberta'
     - `created_by`: ID do terceirizado/técnico

4. **Notificação de Sucesso**
   - Enviar mensagem WhatsApp confirmando criação:
     ```
     ✅ *OS CRIADA COM SUCESSO*

     *Número:* OS-20260106120000
     *Equipamento:* Esteira 3
     *Local:* Sala 202
     *Prioridade:* Alta

     Você pode acompanhar o andamento pelo sistema.
     ```

#### Fluxo de Implementação

```python
# app/services/roteamento_service.py (adicionar método)

def _processar_confirmacao_os_nlp(terceirizado, texto):
    """
    Processa confirmação de criação de OS por voz.
    """
    # 1. Buscar estado conversacional
    estado = EstadoConversa.query.filter_by(
        telefone=terceirizado.telefone,
        contexto__contains='confirmar_os_nlp'
    ).first()

    if not estado:
        return "Não há solicitação de OS pendente."

    # 2. Verificar confirmação
    texto_lower = texto.lower().strip()
    confirmacoes = ['sim', 's', 'yes', 'confirmar', 'ok']
    cancelamentos = ['nao', 'não', 'n', 'no', 'cancelar']

    if texto_lower in cancelamentos:
        # Limpar estado
        db.session.delete(estado)
        db.session.commit()
        return "❌ Solicitação de OS cancelada."

    if texto_lower not in confirmacoes:
        return "Por favor, responda SIM para confirmar ou NÃO para cancelar."

    # 3. Extrair dados do contexto
    dados = estado.contexto['dados']

    # 4. Buscar equipamento
    equipamento = Equipamento.query.filter(
        Equipamento.nome.ilike(f"%{dados['equipamento']}%"),
        Equipamento.ativo == True
    ).first()

    if not equipamento:
        # Fallback: criar OS sem equipamento específico
        mensagem_erro = f"⚠️ Equipamento '{dados['equipamento']}' não encontrado no catálogo. "
        mensagem_erro += "A OS será criada sem equipamento vinculado. "
        mensagem_erro += "Por favor, atualize no sistema."
        WhatsAppService.enviar_mensagem(terceirizado.telefone, mensagem_erro)

    # 5. Determinar unidade
    unidade_id = None
    if dados.get('local'):
        # Tentar mapear local para unidade (pode usar dict de mapeamento)
        unidade = Unidade.query.filter(
            Unidade.nome.ilike(f"%{dados['local']}%")
        ).first()
        if unidade:
            unidade_id = unidade.id

    # Fallback: usar unidade do terceirizado
    if not unidade_id and terceirizado.unidades:
        unidade_id = terceirizado.unidades[0].id

    # 6. Criar OS
    from datetime import datetime
    numero_os = f"OS-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    os = OrdemServico(
        numero_os=numero_os,
        equipamento_id=equipamento.id if equipamento else None,
        unidade_id=unidade_id,
        titulo=f"Problema em {dados.get('equipamento', 'equipamento não identificado')}",
        descricao=dados.get('resumo', 'Criado por reconhecimento de voz'),
        prioridade=dados.get('urgencia', 'media'),
        origem_criacao='whatsapp_bot',
        status='aberta',
        created_by=terceirizado.id  # Se terceirizado é também usuário
    )

    db.session.add(os)
    db.session.delete(estado)  # Limpar estado
    db.session.commit()

    # 7. Notificar sucesso
    mensagem = f"""✅ *OS CRIADA COM SUCESSO*

*Número:* {os.numero_os}
*Equipamento:* {equipamento.nome if equipamento else 'Não especificado'}
*Local:* {dados.get('local', 'Não especificado')}
*Prioridade:* {os.prioridade.upper()}

Você pode acompanhar o andamento pelo sistema."""

    return mensagem
```

#### Integração no Roteamento

Adicionar verificação no método `processar()`:

```python
# Verificar se usuário está respondendo confirmação de OS
if estado and estado.contexto.get('fluxo') == 'confirmar_os_nlp':
    resposta = self._processar_confirmacao_os_nlp(terceirizado, texto)
    WhatsAppService.enviar_mensagem(remetente, resposta)
    return
```

#### Testes de Aceitação

- [ ] Usuário envia áudio descrevendo problema
- [ ] Sistema transcreve, extrai entidades e pede confirmação
- [ ] Usuário responde "SIM"
- [ ] OS é criada com `origem_criacao='whatsapp_bot'`
- [ ] Usuário recebe notificação de sucesso
- [ ] Usuário responde "NÃO" e fluxo é cancelado

---

### 2.2 US-002: Processamento QR Code (EQUIP:{id})

**Prioridade**: 🔴 ALTA
**Estimativa**: ~100 linhas de código
**Arquivo**: `app/services/roteamento_service.py`, `app/services/whatsapp_service.py`

#### Descrição

Quando técnico escaneia QR Code de equipamento, o WhatsApp abre com mensagem pré-preenchida `EQUIP:127`. Sistema deve contextualizar conversa no equipamento e enviar menu interativo.

#### Requisitos Funcionais

1. **Detecção do Comando**
   - Identificar mensagens que começam com `EQUIP:`
   - Extrair ID do equipamento: `EQUIP:127` → `127`

2. **Validação**
   - Verificar se equipamento existe e está ativo
   - Se não existir, retornar erro amigável

3. **Contextualização**
   - Salvar contexto em `EstadoConversa`:
     ```json
     {
       "fluxo": "contexto_equipamento",
       "equipamento_id": 127,
       "equipamento_nome": "Esteira 3"
     }
     ```

4. **Menu Interativo**
   - Enviar List Message com opções:
     - **Abrir Chamado**: Criar nova OS para o equipamento
     - **Ver Histórico**: Listar últimas 5 OSs do equipamento
     - **Dados Técnicos**: Exibir informações do equipamento
     - **Voltar ao Menu**: Limpar contexto

#### Implementação

```python
# app/services/roteamento_service.py

def _processar_comando_equip(terceirizado, texto):
    """
    Processa comando EQUIP:{id} de QR Code.

    Args:
        terceirizado: Objeto Terceirizado/Usuario
        texto: Mensagem completa (ex: "EQUIP:127")

    Returns:
        None (envia menu interativo diretamente)
    """
    # 1. Extrair ID
    try:
        equip_id = int(texto.split(':')[1].strip())
    except (IndexError, ValueError):
        WhatsAppService.enviar_mensagem(
            terceirizado.telefone,
            "❌ Formato inválido. Use: EQUIP:ID"
        )
        return

    # 2. Buscar equipamento
    equipamento = Equipamento.query.filter_by(
        id=equip_id,
        ativo=True
    ).first()

    if not equipamento:
        WhatsAppService.enviar_mensagem(
            terceirizado.telefone,
            f"❌ Equipamento #{equip_id} não encontrado ou inativo."
        )
        return

    # 3. Salvar contexto
    EstadoService.criar_ou_atualizar_estado(
        telefone=terceirizado.telefone,
        contexto={
            'fluxo': 'contexto_equipamento',
            'equipamento_id': equip_id,
            'equipamento_nome': equipamento.nome
        }
    )

    # 4. Montar menu interativo
    sections = [
        {
            "title": "Ordens de Serviço",
            "rows": [
                {
                    "id": f"abrir_os_{equip_id}",
                    "title": "🆕 Abrir Chamado",
                    "description": f"Criar OS para {equipamento.nome}"
                },
                {
                    "id": f"historico_{equip_id}",
                    "title": "📋 Ver Histórico",
                    "description": "Últimas OSs deste equipamento"
                }
            ]
        },
        {
            "title": "Informações",
            "rows": [
                {
                    "id": f"dados_tecnicos_{equip_id}",
                    "title": "⚙️ Dados Técnicos",
                    "description": "Informações do equipamento"
                },
                {
                    "id": "voltar_menu",
                    "title": "↩️ Voltar ao Menu",
                    "description": "Limpar contexto"
                }
            ]
        }
    ]

    # 5. Enviar menu
    WhatsAppService.send_list_message(
        phone=terceirizado.telefone,
        header=f"📟 {equipamento.nome}",
        body=f"""*Código:* {equipamento.codigo}
*Unidade:* {equipamento.unidade.nome}
*Status:* {'🟢 Operacional' if equipamento.status == 'operacional' else '🔴 Manutenção'}

Escolha uma opção:""",
        sections=sections
    )


# Adicionar handlers para respostas

def _abrir_os_equipamento(terceirizado, equipamento_id):
    """Inicia fluxo de abertura de OS para equipamento específico."""
    equipamento = Equipamento.query.get(equipamento_id)

    # Salvar estado
    EstadoService.criar_ou_atualizar_estado(
        telefone=terceirizado.telefone,
        contexto={
            'fluxo': 'criando_os_equipamento',
            'equipamento_id': equipamento_id
        }
    )

    mensagem = f"""📝 *Criar OS para {equipamento.nome}*

Descreva o problema encontrado:"""

    WhatsAppService.enviar_mensagem(terceirizado.telefone, mensagem)


def _exibir_historico_equipamento(terceirizado, equipamento_id):
    """Exibe últimas 5 OSs do equipamento."""
    equipamento = Equipamento.query.get(equipamento_id)

    oss = OrdemServico.query.filter_by(
        equipamento_id=equipamento_id
    ).order_by(OrdemServico.data_abertura.desc()).limit(5).all()

    if not oss:
        mensagem = f"📋 *Histórico: {equipamento.nome}*\n\nNenhuma OS registrada para este equipamento."
    else:
        mensagem = f"📋 *Histórico: {equipamento.nome}*\n\nÚltimas OSs:\n\n"
        for os in oss:
            status_emoji = {
                'aberta': '🔴',
                'em_andamento': '🟡',
                'concluida': '🟢',
                'cancelada': '⚫'
            }.get(os.status, '⚪')

            mensagem += f"{status_emoji} *{os.numero_os}*\n"
            mensagem += f"   {os.titulo}\n"
            mensagem += f"   Data: {os.data_abertura.strftime('%d/%m/%Y')}\n\n"

    WhatsAppService.enviar_mensagem(terceirizado.telefone, mensagem)


def _exibir_dados_tecnicos(terceirizado, equipamento_id):
    """Exibe informações técnicas do equipamento."""
    equipamento = Equipamento.query.get(equipamento_id)

    mensagem = f"""⚙️ *Dados Técnicos*

*Nome:* {equipamento.nome}
*Código:* {equipamento.codigo}
*Categoria:* {equipamento.categoria.nome if equipamento.categoria else 'N/A'}
*Unidade:* {equipamento.unidade.nome}
*Status:* {equipamento.status.upper()}
*Data Aquisição:* {equipamento.data_aquisicao.strftime('%d/%m/%Y') if equipamento.data_aquisicao else 'N/A'}
*Custo Aquisição:* R$ {equipamento.custo_aquisicao:.2f if equipamento.custo_aquisicao else 0:.2f}

*Descrição:*
{equipamento.descricao or 'Sem descrição cadastrada.'}"""

    WhatsAppService.enviar_mensagem(terceirizado.telefone, mensagem)
```

#### Integração no Roteamento

Adicionar verificação no método `processar()`:

```python
# Verificar comando EQUIP
if texto.upper().startswith('EQUIP:'):
    self._processar_comando_equip(terceirizado, texto)
    return
```

Adicionar handlers em `processar_resposta_interativa()`:

```python
elif resposta_id.startswith('abrir_os_'):
    equipamento_id = int(resposta_id.split('_')[2])
    return RoteamentoService._abrir_os_equipamento(terceirizado, equipamento_id)

elif resposta_id.startswith('historico_'):
    equipamento_id = int(resposta_id.split('_')[1])
    return RoteamentoService._exibir_historico_equipamento(terceirizado, equipamento_id)

elif resposta_id.startswith('dados_tecnicos_'):
    equipamento_id = int(resposta_id.split('_')[2])
    return RoteamentoService._exibir_dados_tecnicos(terceirizado, equipamento_id)
```

#### Testes de Aceitação

- [ ] Técnico escaneia QR Code com `EQUIP:127`
- [ ] Sistema envia menu interativo com 4 opções
- [ ] Técnico seleciona "Abrir Chamado" → fluxo de criação inicia
- [ ] Técnico seleciona "Ver Histórico" → lista últimas 5 OSs
- [ ] Técnico seleciona "Dados Técnicos" → exibe informações
- [ ] Técnico seleciona "Voltar ao Menu" → contexto limpo

---

### 2.3 US-003: Geração de PDF de Pedido de Compra

**Prioridade**: 🔴 ALTA
**Estimativa**: ~150 linhas de código
**Arquivos**: `app/services/pdf_generator_service.py`, `app/tasks/whatsapp_tasks.py`

#### Descrição

Após aprovação de pedido de compra, gerar PDF profissional e enviar para fornecedor via WhatsApp e Email.

#### Requisitos Funcionais

1. **Geração de PDF**
   - Template HTML + CSS renderizado com WeasyPrint
   - Conteúdo:
     - Logo da empresa (opcional)
     - Dados do pedido (número, data)
     - Dados do fornecedor (nome, CNPJ, endereço)
     - Tabela de itens (código, descrição, quantidade, preço unitário, subtotal)
     - Valor total
     - Condições de pagamento e entrega
   - Path: `/static/uploads/pedidos/PEDIDO_{numero_pedido}.pdf`

2. **Envio Automático**
   - Task Celery disparada após aprovação
   - Enviar via WhatsApp (se fornecedor tem whatsapp)
   - Enviar via Email (sempre)
   - Atualizar status do pedido para 'pedido'

#### Implementação

**Instalar Dependência**:
```bash
pip install weasyprint
```

**Adicionar ao requirements.txt**:
```
weasyprint>=60.0
```

**Implementar Serviço**:

```python
# app/services/pdf_generator_service.py

from weasyprint import HTML, CSS
from jinja2 import Template
from flask import current_app
import os
from datetime import datetime

class PDFGeneratorService:

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
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #333;
            padding-bottom: 15px;
        }
        .header h1 {
            color: #333;
            margin: 10px 0;
        }
        .info-box {
            background-color: #f5f5f5;
            padding: 15px;
            margin: 20px 0;
            border-left: 4px solid #007bff;
        }
        .info-box h3 {
            margin-top: 0;
            color: #007bff;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th {
            background-color: #333;
            color: white;
            padding: 10px;
            text-align: left;
        }
        td {
            border: 1px solid #ddd;
            padding: 8px;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .total-row {
            background-color: #e8f4f8 !important;
            font-weight: bold;
            font-size: 12pt;
        }
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 9pt;
            color: #666;
        }
        .text-right {
            text-align: right;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>PEDIDO DE COMPRA</h1>
        <p><strong>Número:</strong> {{ pedido.numero_pedido }}</p>
        <p><strong>Data de Emissão:</strong> {{ pedido.data_solicitacao.strftime('%d/%m/%Y %H:%M') }}</p>
    </div>

    <div class="info-box">
        <h3>Fornecedor</h3>
        <p><strong>{{ pedido.fornecedor.nome }}</strong></p>
        {% if pedido.fornecedor.cnpj %}
        <p>CNPJ: {{ pedido.fornecedor.cnpj }}</p>
        {% endif %}
        {% if pedido.fornecedor.endereco %}
        <p>Endereço: {{ pedido.fornecedor.endereco }}</p>
        {% endif %}
        <p>Telefone: {{ pedido.fornecedor.telefone or 'N/A' }}</p>
        <p>Email: {{ pedido.fornecedor.email or 'N/A' }}</p>
    </div>

    <div class="info-box">
        <h3>Dados do Pedido</h3>
        <p><strong>Solicitante:</strong> {{ pedido.solicitante.nome }}</p>
        <p><strong>Unidade de Destino:</strong> {{ pedido.unidade_destino.nome if pedido.unidade_destino else 'A definir' }}</p>
        {% if pedido.os %}
        <p><strong>OS Relacionada:</strong> {{ pedido.os.numero_os }}</p>
        {% endif %}
        {% if pedido.aprovador %}
        <p><strong>Aprovado por:</strong> {{ pedido.aprovador.nome }} em {{ pedido.data_aprovacao.strftime('%d/%m/%Y %H:%M') }}</p>
        {% endif %}
    </div>

    <h3>Itens do Pedido</h3>
    <table>
        <thead>
            <tr>
                <th>Código</th>
                <th>Descrição</th>
                <th>Unidade</th>
                <th class="text-right">Quantidade</th>
                <th class="text-right">Preço Unit.</th>
                <th class="text-right">Subtotal</th>
            </tr>
        </thead>
        <tbody>
            {% for item in pedido.itens %}
            <tr>
                <td>{{ item.estoque.codigo }}</td>
                <td>{{ item.estoque.nome }}</td>
                <td>{{ item.estoque.unidade_medida }}</td>
                <td class="text-right">{{ item.quantidade }}</td>
                <td class="text-right">R$ {{ "%.2f"|format(item.preco_unitario) }}</td>
                <td class="text-right">R$ {{ "%.2f"|format(item.subtotal) }}</td>
            </tr>
            {% endfor %}
            <tr class="total-row">
                <td colspan="5" class="text-right">TOTAL</td>
                <td class="text-right">R$ {{ "%.2f"|format(pedido.valor_total) }}</td>
            </tr>
        </tbody>
    </table>

    {% if pedido.observacoes %}
    <div class="info-box">
        <h3>Observações</h3>
        <p>{{ pedido.observacoes }}</p>
    </div>
    {% endif %}

    <div class="info-box">
        <h3>Condições</h3>
        <p><strong>Prazo de Entrega:</strong> Conforme acordado com fornecedor</p>
        <p><strong>Forma de Pagamento:</strong> A combinar</p>
        <p><strong>Local de Entrega:</strong> {{ pedido.unidade_destino.endereco if pedido.unidade_destino else 'A definir' }}</p>
    </div>

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
        filename = f"PEDIDO_{pedido.numero_pedido}.pdf"
        filepath = os.path.join(pasta_pedidos, filename)

        HTML(string=html_content).write_pdf(filepath)

        return filepath
```

**Criar Task Celery**:

```python
# app/tasks/whatsapp_tasks.py (adicionar)

@celery.task(bind=True, max_retries=3)
def enviar_pedido_fornecedor(self, pedido_id):
    """
    Gera PDF do pedido e envia para fornecedor via WhatsApp e Email.

    Args:
        pedido_id: ID do pedido aprovado
    """
    from app.models.estoque_models import PedidoCompra
    from app.services.pdf_generator_service import PDFGeneratorService
    from app.services.whatsapp_service import WhatsAppService
    from app.services.email_service import EmailService
    from app import db

    try:
        pedido = PedidoCompra.query.get(pedido_id)

        # 1. Gerar PDF
        pdf_path = PDFGeneratorService.gerar_pdf_pedido(pedido_id)

        # 2. Enviar via WhatsApp (se fornecedor tem whatsapp)
        if pedido.fornecedor.whatsapp:
            mensagem = f"""📦 *PEDIDO DE COMPRA*

*Número:* {pedido.numero_pedido}
*Data:* {pedido.data_solicitacao.strftime('%d/%m/%Y')}
*Valor Total:* R$ {pedido.valor_total:.2f}

Segue em anexo o pedido completo."""

            WhatsAppService.enviar_mensagem(
                telefone=pedido.fornecedor.whatsapp,
                texto=mensagem,
                prioridade=1,
                arquivo_path=pdf_path,
                tipo_midia='document',
                caption=f"Pedido {pedido.numero_pedido}"
            )

        # 3. Enviar via Email (sempre)
        if pedido.fornecedor.email:
            EmailService.enviar_email(
                destinatario=pedido.fornecedor.email,
                assunto=f"Pedido de Compra {pedido.numero_pedido}",
                corpo=f"""Prezado(a) {pedido.fornecedor.nome},

Segue em anexo o Pedido de Compra {pedido.numero_pedido}.

Valor Total: R$ {pedido.valor_total:.2f}

Por favor, confirme o recebimento e nos informe o prazo de entrega.

Atenciosamente,
Sistema GMM""",
                anexos=[pdf_path]
            )

        # 4. Atualizar status do pedido
        pedido.status = 'pedido'
        db.session.commit()

    except Exception as exc:
        # Retry com backoff
        raise self.retry(exc=exc, countdown=60 * (5 ** self.request.retries))
```

**Disparar após Aprovação**:

```python
# app/services/roteamento_service.py
# Modificar método _aprovar_pedido (linha ~290)

# Após atualizar status
pedido.status = 'aprovado'
pedido.data_aprovacao = datetime.now()
pedido.aprovador_id = aprovador_id
db.session.commit()

# Disparar geração e envio de PDF
from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
enviar_pedido_fornecedor.delay(pedido.id)
```

#### Testes de Aceitação

- [ ] Pedido aprovado dispara task `enviar_pedido_fornecedor`
- [ ] PDF é gerado em `/static/uploads/pedidos/`
- [ ] PDF contém todas informações: fornecedor, itens, total
- [ ] PDF é enviado via WhatsApp para fornecedor (se tem whatsapp)
- [ ] PDF é enviado via Email para fornecedor (sempre)
- [ ] Status do pedido muda para 'pedido'

---

### 2.4 US-004: Cálculo Automático de Tempo de Execução

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~30 linhas de código
**Arquivo**: `app/routes/os.py`

#### Descrição

Calcular automaticamente o campo `tempo_execucao_minutos` quando OS é finalizada, pausada ou retomada.

#### Requisitos Funcionais

1. **Iniciar OS**
   - Gravar `data_inicio = NOW()`
   - Atualizar `status = 'em_andamento'`

2. **Pausar OS**
   - Calcular tempo decorrido: `NOW() - data_inicio`
   - Somar ao `tempo_execucao_minutos` acumulado
   - Atualizar `status = 'pausada'`
   - Limpar `data_inicio`

3. **Retomar OS**
   - Gravar novo `data_inicio = NOW()`
   - Atualizar `status = 'em_andamento'`

4. **Finalizar OS**
   - Calcular tempo decorrido: `NOW() - data_inicio`
   - Somar ao `tempo_execucao_minutos` acumulado
   - Atualizar `status = 'concluida'`

#### Implementação

```python
# app/routes/os.py

@bp.route('/<int:id>/iniciar', methods=['POST'])
@login_required
def iniciar_os(id):
    """Inicia execução da OS."""
    os_obj = OrdemServico.query.get_or_404(id)

    # Validações
    if os_obj.status not in ['aberta', 'pausada']:
        flash('Somente OSs abertas ou pausadas podem ser iniciadas.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    # Iniciar
    os_obj.data_inicio = datetime.now()
    os_obj.status = 'em_andamento'

    db.session.commit()
    flash(f'OS {os_obj.numero_os} iniciada.', 'success')

    return redirect(url_for('os.detalhes', id=id))


@bp.route('/<int:id>/pausar', methods=['POST'])
@login_required
def pausar_os(id):
    """Pausa execução da OS."""
    os_obj = OrdemServico.query.get_or_404(id)

    # Validações
    if os_obj.status != 'em_andamento':
        flash('Somente OSs em andamento podem ser pausadas.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    if not os_obj.data_inicio:
        flash('Erro: OS sem data de início registrada.', 'danger')
        return redirect(url_for('os.detalhes', id=id))

    # Calcular tempo decorrido
    tempo_decorrido = datetime.now() - os_obj.data_inicio
    minutos_decorridos = int(tempo_decorrido.total_seconds() / 60)

    # Acumular tempo
    if os_obj.tempo_execucao_minutos:
        os_obj.tempo_execucao_minutos += minutos_decorridos
    else:
        os_obj.tempo_execucao_minutos = minutos_decorridos

    # Pausar
    os_obj.status = 'pausada'
    os_obj.data_inicio = None  # Limpar

    db.session.commit()
    flash(f'OS {os_obj.numero_os} pausada. Tempo executado: {minutos_decorridos} min.', 'info')

    return redirect(url_for('os.detalhes', id=id))


# Modificar método concluir_os existente (linha ~87)
@bp.route('/<int:id>/concluir', methods=['POST'])
@login_required
def concluir_os(id):
    os_obj = OrdemServico.query.get_or_404(id)

    # ... validações existentes ...

    # ADICIONAR: Calcular tempo final
    if os_obj.data_inicio:
        tempo_decorrido = datetime.now() - os_obj.data_inicio
        minutos_decorridos = int(tempo_decorrido.total_seconds() / 60)

        if os_obj.tempo_execucao_minutos:
            os_obj.tempo_execucao_minutos += minutos_decorridos
        else:
            os_obj.tempo_execucao_minutos = minutos_decorridos

    # ... resto do código existente ...
    os_obj.status = 'concluida'
    os_obj.data_finalizacao = datetime.now()

    # ... upload de fotos, etc ...
```

#### Testes de Aceitação

- [ ] Técnico inicia OS → `data_inicio` é gravada
- [ ] Técnico pausa OS após 30min → `tempo_execucao_minutos = 30`
- [ ] Técnico retoma OS → novo `data_inicio` gravado
- [ ] Técnico finaliza OS após mais 45min → `tempo_execucao_minutos = 75`

---

### 2.5 US-005: SLA Dinâmico

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~30 linhas de código
**Arquivos**: `app/routes/os.py`, `app/services/os_service.py`

#### Descrição

Calcular automaticamente `data_prevista` baseado na prioridade da OS e tipo de serviço (interno ou terceirizado).

#### Requisitos Funcionais

1. **Cálculo de SLA**
   - Urgente: 4 horas
   - Alta: 24 horas (1 dia)
   - Média: 72 horas (3 dias)
   - Baixa: 168 horas (7 dias)
   - Se terceirizado: +50% de tempo

2. **Aplicação**
   - Calcular ao criar OS
   - Recalcular se prioridade for alterada

#### Implementação

```python
# app/services/os_service.py (criar método)

from datetime import datetime, timedelta

class OSService:

    @staticmethod
    def calcular_sla(prioridade, eh_terceirizado=False):
        """
        Calcula SLA (data prevista) baseado na prioridade.

        Args:
            prioridade: 'urgente', 'alta', 'media', 'baixa'
            eh_terceirizado: bool - Se serviço é terceirizado

        Returns:
            datetime: Data/hora prevista de conclusão
        """
        sla_base = {
            'urgente': 4,    # 4 horas
            'alta': 24,      # 1 dia
            'media': 72,     # 3 dias
            'baixa': 168     # 7 dias
        }

        horas = sla_base.get(prioridade.lower(), 72)  # Default: média

        # Terceirizados têm 50% a mais de tempo
        if eh_terceirizado:
            horas = int(horas * 1.5)

        return datetime.now() + timedelta(hours=horas)
```

**Aplicar na Criação de OS**:

```python
# app/routes/os.py
# Modificar método nova_os (linha ~16)

@bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova_os():
    if request.method == 'POST':
        # ... código existente para capturar dados ...

        # ADICIONAR: Calcular SLA
        from app.services.os_service import OSService

        eh_terceirizado = False  # Determinar baseado no tipo de OS
        # Se for chamado externo, eh_terceirizado = True

        data_prevista = OSService.calcular_sla(
            prioridade=prioridade,
            eh_terceirizado=eh_terceirizado
        )

        os_obj = OrdemServico(
            # ... campos existentes ...
            prioridade=prioridade,
            data_prevista=data_prevista,  # NOVO
            # ... resto ...
        )
```

**Recalcular ao Editar Prioridade**:

```python
# app/routes/os.py
# Adicionar ao método editar_os

@bp.route('/<int:id>/editar-os', methods=['POST'])
@login_required
def editar_os(id):
    # ... código existente ...

    # Se prioridade mudou, recalcular SLA
    prioridade_nova = request.form.get('prioridade')
    if prioridade_nova and prioridade_nova != os_obj.prioridade:
        os_obj.prioridade = prioridade_nova

        # Recalcular SLA
        eh_terceirizado = (os_obj.chamados_externos.count() > 0)
        os_obj.data_prevista = OSService.calcular_sla(
            prioridade=prioridade_nova,
            eh_terceirizado=eh_terceirizado
        )
```

#### Testes de Aceitação

- [ ] OS criada com prioridade "urgente" → `data_prevista = NOW() + 4h`
- [ ] OS criada com prioridade "alta" → `data_prevista = NOW() + 24h`
- [ ] OS terceirizada com prioridade "alta" → `data_prevista = NOW() + 36h` (+50%)
- [ ] Prioridade alterada de "média" para "urgente" → `data_prevista` recalculada

---

### 2.6 US-006: Aprovação Automática (Valor <= R$ 500)

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~20 linhas de código
**Arquivo**: `app/services/comando_executores.py`

#### Descrição

Pedidos de compra com valor total até R$ 500 devem ser aprovados automaticamente, sem necessidade de aprovação manual do gestor.

#### Requisitos Funcionais

1. **Verificação de Valor**
   - Após comprador inserir cotações e definir `valor_total`
   - Se `valor_total <= 500.00`: aprovar automaticamente
   - Se `valor_total > 500.00`: enviar para aprovação manual (fluxo atual)

2. **Aprovação Automática**
   - Atualizar `status = 'aprovado'`
   - Gravar `data_aprovacao = NOW()`
   - Gravar `aprovador_id = None` (ou ID do sistema)
   - Disparar geração de PDF e envio

3. **Notificação**
   - Notificar solicitante via WhatsApp:
     ```
     ✅ *PEDIDO APROVADO AUTOMATICAMENTE*

     Seu pedido #123 foi aprovado automaticamente (valor <= R$ 500).

     O pedido será enviado ao fornecedor em breve.
     ```

#### Implementação

```python
# app/routes/compras.py
# Adicionar método para atualizar valor do pedido

@bp.route('/<int:id>/atualizar-valor', methods=['POST'])
@login_required
def atualizar_valor_pedido(id):
    """
    Atualiza valor total do pedido após comprador inserir cotações.
    Aprova automaticamente se valor <= R$ 500.
    """
    from app.services.whatsapp_service import WhatsAppService
    from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor

    pedido = PedidoCompra.query.get_or_404(id)

    # Validações
    if current_user.tipo not in ['admin', 'comprador']:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('compras.index'))

    # Capturar valor total
    try:
        valor_total = float(request.form.get('valor_total', 0))
    except ValueError:
        flash('Valor inválido.', 'danger')
        return redirect(url_for('compras.detalhes', id=id))

    pedido.valor_total = valor_total

    # Verificar aprovação automática
    LIMITE_APROVACAO_AUTOMATICA = 500.00

    if valor_total <= LIMITE_APROVACAO_AUTOMATICA:
        # Aprovar automaticamente
        pedido.status = 'aprovado'
        pedido.data_aprovacao = datetime.now()
        pedido.aprovador_id = current_user.id  # Comprador que inseriu cotação

        db.session.commit()

        # Notificar solicitante
        if pedido.solicitante.telefone:
            mensagem = f"""✅ *PEDIDO APROVADO AUTOMATICAMENTE*

*Pedido:* #{pedido.numero_pedido}
*Valor Total:* R$ {valor_total:.2f}

Seu pedido foi aprovado automaticamente (valor <= R$ {LIMITE_APROVACAO_AUTOMATICA:.2f}).

O pedido será enviado ao fornecedor em breve."""

            WhatsAppService.enviar_mensagem(
                pedido.solicitante.telefone,
                mensagem
            )

        # Disparar geração de PDF e envio
        enviar_pedido_fornecedor.delay(pedido.id)

        flash(f'Pedido aprovado automaticamente (valor <= R$ {LIMITE_APROVACAO_AUTOMATICA:.2f}).', 'success')
    else:
        # Enviar para aprovação manual (gestor)
        db.session.commit()

        # Buscar gestor
        gestor = Usuario.query.filter_by(tipo='admin').first()

        if gestor and gestor.telefone:
            # Enviar botões de aprovação (código existente)
            from app.services.whatsapp_service import WhatsAppService

            mensagem = f"""📦 *NOVA SOLICITAÇÃO DE COMPRA*

*Pedido:* #{pedido.numero_pedido}
*Valor Total:* R$ {valor_total:.2f}

Clique para decidir:"""

            buttons = [
                {"type": "reply", "reply": {"id": f"aprovar_{pedido.id}", "title": "✅ Aprovar"}},
                {"type": "reply", "reply": {"id": f"rejeitar_{pedido.id}", "title": "❌ Rejeitar"}}
            ]

            WhatsAppService.send_buttons_message(
                phone=gestor.telefone,
                body=mensagem,
                buttons=buttons
            )

        flash(f'Pedido enviado para aprovação do gestor (valor > R$ {LIMITE_APROVACAO_AUTOMATICA:.2f}).', 'info')

    return redirect(url_for('compras.detalhes', id=id))
```

#### Testes de Aceitação

- [ ] Comprador insere cotação totalizando R$ 300 → pedido aprovado automaticamente
- [ ] Solicitante recebe notificação WhatsApp de aprovação automática
- [ ] PDF é gerado e enviado ao fornecedor
- [ ] Comprador insere cotação totalizando R$ 700 → pedido vai para aprovação manual
- [ ] Gestor recebe botões de aprovação/rejeição

---

## 3. SPRINT 2 - ALERTAS E NOTIFICAÇÕES (1 semana)

**Objetivo**: Sistema totalmente proativo com alertas automatizados

### 3.1 US-007: Morning Briefing (Task Celery)

**Prioridade**: 🔴 ALTA
**Estimativa**: ~100 linhas de código
**Arquivos**: `app/tasks/system_tasks.py`, `config/celery_beat_schedule.py`

#### Descrição

Enviar relatório automático às 08:00 (segunda a sexta) para gerentes com status do dia: OSs atrasadas, estoque crítico, taxa de conclusão do dia anterior.

#### Requisitos Funcionais

1. **Agendamento**
   - Task Celery Beat executada às 08:00
   - Segunda a sexta-feira apenas
   - Executar para cada unidade separadamente

2. **Conteúdo do Relatório**
   - **OSs Atrasadas**: COUNT de OSs com `data_prevista < hoje` e `status IN ('aberta', 'em_andamento')`
   - **Estoque Crítico**: COUNT de itens com `EstoqueSaldo.quantidade < Estoque.quantidade_minima`
   - **Taxa de Conclusão Ontem**: (OSs concluídas ontem / OSs criadas ontem) * 100

3. **Destinatários**
   - Gerentes de cada unidade (usuários com `tipo='gerente'`)
   - Admins (opcional)

#### Implementação

```python
# app/tasks/system_tasks.py

from app.tasks import celery
from app.models import OrdemServico, Estoque, EstoqueSaldo, Usuario, Unidade
from app.services.whatsapp_service import WhatsAppService
from app import db
from datetime import datetime, date, timedelta
from sqlalchemy import func

@celery.task
def enviar_morning_briefing():
    """
    Envia relatório matinal para gerentes de cada unidade.
    Executado às 08:00 (seg-sex).
    """
    hoje = date.today()
    ontem = hoje - timedelta(days=1)

    # Buscar todas unidades ativas
    unidades = Unidade.query.filter_by(ativo=True).all()

    for unidade in unidades:
        # 1. OSs Atrasadas
        os_atrasadas = OrdemServico.query.filter(
            OrdemServico.unidade_id == unidade.id,
            OrdemServico.status.in_(['aberta', 'em_andamento']),
            OrdemServico.data_prevista < datetime.now()
        ).count()

        # 2. Estoque Crítico
        estoque_critico = db.session.query(Estoque).join(EstoqueSaldo).filter(
            EstoqueSaldo.unidade_id == unidade.id,
            EstoqueSaldo.quantidade < Estoque.quantidade_minima
        ).count()

        # 3. Taxa de Conclusão Ontem
        os_criadas_ontem = OrdemServico.query.filter(
            OrdemServico.unidade_id == unidade.id,
            func.date(OrdemServico.data_abertura) == ontem
        ).count()

        os_concluidas_ontem = OrdemServico.query.filter(
            OrdemServico.unidade_id == unidade.id,
            func.date(OrdemServico.data_finalizacao) == ontem
        ).count()

        taxa_conclusao = 0
        if os_criadas_ontem > 0:
            taxa_conclusao = (os_concluidas_ontem / os_criadas_ontem) * 100

        # 4. Montar mensagem
        mensagem = f"""☀️ *Bom dia! Status {unidade.nome}*

📊 *Resumo de Hoje ({hoje.strftime('%d/%m/%Y')})*

🔴 {os_atrasadas} OSs Atrasadas
🟡 {estoque_critico} Itens com Estoque Crítico
"""

        if os_criadas_ontem > 0:
            emoji_taxa = '🟢' if taxa_conclusao >= 80 else '🟡' if taxa_conclusao >= 50 else '🔴'
            mensagem += f"{emoji_taxa} {taxa_conclusao:.1f}% das OSs de ontem foram concluídas\n"
        else:
            mensagem += "🟢 Nenhuma OS criada ontem\n"

        # Adicionar detalhes se houver problemas
        if os_atrasadas > 0:
            mensagem += f"\n⚠️ *Atenção:* {os_atrasadas} OSs estão atrasadas. Verifique priorização."

        if estoque_critico > 0:
            mensagem += f"\n⚠️ *Atenção:* {estoque_critico} itens abaixo do estoque mínimo. Verifique compras."

        # 5. Enviar para gerentes da unidade
        gerentes = Usuario.query.filter(
            Usuario.tipo.in_(['gerente', 'admin']),
            Usuario.unidade_id == unidade.id,
            Usuario.ativo == True,
            Usuario.telefone.isnot(None)
        ).all()

        for gerente in gerentes:
            try:
                WhatsAppService.enviar_mensagem(
                    telefone=gerente.telefone,
                    texto=mensagem,
                    prioridade=1
                )
            except Exception as e:
                # Log erro mas continua para próximos gerentes
                print(f"Erro ao enviar briefing para {gerente.nome}: {e}")
```

**Configurar Agendamento**:

```python
# config/celery_beat_schedule.py

from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # ... agendamentos existentes ...

    'morning-briefing': {
        'task': 'app.tasks.system_tasks.enviar_morning_briefing',
        'schedule': crontab(
            hour=8,
            minute=0,
            day_of_week='mon,tue,wed,thu,fri'  # Seg-sex
        ),
    },
}
```

**Registrar no Celery**:

```python
# app/__init__.py (verificar se tasks estão importadas)

def create_app():
    # ... código existente ...

    # Importar tasks para registrar no Celery
    from app.tasks import whatsapp_tasks, system_tasks

    # Configurar Celery Beat schedule
    app.celery.conf.update(
        CELERYBEAT_SCHEDULE=CELERYBEAT_SCHEDULE
    )
```

#### Testes de Aceitação

- [ ] Task executada às 08:00 de segunda a sexta
- [ ] Relatório enviado para gerentes de cada unidade
- [ ] Contém OSs atrasadas, estoque crítico, taxa de conclusão ontem
- [ ] Mensagem formatada corretamente com emojis
- [ ] Não é enviada aos sábados e domingos

---

### 3.2 US-008: Alertas Preditivos de Equipamentos

**Prioridade**: 🔴 ALTA
**Estimativa**: ~80 linhas de código
**Arquivos**: `app/tasks/system_tasks.py`, `config/celery_beat_schedule.py`

#### Descrição

Detectar equipamentos com mais de 3 OSs nos últimos 30 dias e alertar gerente sugerindo revisão profunda ou substituição.

#### Requisitos Funcionais

1. **Agendamento**
   - Task executada diariamente às 03:00

2. **Detecção de Anomalias**
   - Query: Equipamentos com `COUNT(OS) > 3` nos últimos 30 dias
   - Agrupar por equipamento e unidade

3. **Notificação**
   - Enviar WhatsApp para gerente da unidade
   - Sugerir ação: "Considere revisão profunda ou substituição"

#### Implementação

```python
# app/tasks/system_tasks.py

@celery.task
def detectar_anomalias_equipamentos():
    """
    Detecta equipamentos com >3 OSs nos últimos 30 dias.
    Envia alerta para gerentes.
    Executado diariamente às 03:00.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func

    data_limite = datetime.now() - timedelta(days=30)

    # Query: Equipamentos problemáticos
    equipamentos_problematicos = db.session.query(
        OrdemServico.equipamento_id,
        Equipamento.nome,
        Equipamento.codigo,
        Equipamento.unidade_id,
        func.count(OrdemServico.id).label('total_os')
    ).join(Equipamento).filter(
        OrdemServico.data_abertura >= data_limite,
        Equipamento.ativo == True
    ).group_by(
        OrdemServico.equipamento_id,
        Equipamento.nome,
        Equipamento.codigo,
        Equipamento.unidade_id
    ).having(
        func.count(OrdemServico.id) > 3
    ).all()

    if not equipamentos_problematicos:
        return  # Nenhum problema detectado

    # Agrupar por unidade
    alertas_por_unidade = {}
    for equip in equipamentos_problematicos:
        unidade_id = equip.unidade_id
        if unidade_id not in alertas_por_unidade:
            alertas_por_unidade[unidade_id] = []

        alertas_por_unidade[unidade_id].append({
            'nome': equip.nome,
            'codigo': equip.codigo,
            'total_os': equip.total_os
        })

    # Enviar alertas
    for unidade_id, equipamentos in alertas_por_unidade.items():
        unidade = Unidade.query.get(unidade_id)

        # Montar mensagem
        mensagem = f"""⚠️ *ALERTA PREDITIVO - {unidade.nome}*

Os seguintes equipamentos tiveram *mais de 3 OSs nos últimos 30 dias*:

"""

        for equip in equipamentos:
            mensagem += f"🔴 *{equip['nome']}* ({equip['codigo']})\n"
            mensagem += f"   → {equip['total_os']} OSs em 30 dias\n\n"

        mensagem += """💡 *Recomendação:*
Considere agendar revisão profunda ou avaliar substituição destes equipamentos para evitar paradas não planejadas."""

        # Buscar gerentes da unidade
        gerentes = Usuario.query.filter(
            Usuario.tipo.in_(['gerente', 'admin']),
            Usuario.unidade_id == unidade_id,
            Usuario.ativo == True,
            Usuario.telefone.isnot(None)
        ).all()

        for gerente in gerentes:
            try:
                WhatsAppService.enviar_mensagem(
                    telefone=gerente.telefone,
                    texto=mensagem,
                    prioridade=2  # Alta prioridade
                )
            except Exception as e:
                print(f"Erro ao enviar alerta para {gerente.nome}: {e}")
```

**Agendar Task**:

```python
# config/celery_beat_schedule.py

CELERYBEAT_SCHEDULE = {
    # ... existentes ...

    'detectar-anomalias-equipamentos': {
        'task': 'app.tasks.system_tasks.detectar_anomalias_equipamentos',
        'schedule': crontab(hour=3, minute=0),  # Diário às 03:00
    },
}
```

#### Testes de Aceitação

- [ ] Task executada diariamente às 03:00
- [ ] Detecta equipamentos com >3 OSs em 30 dias
- [ ] Agrupa por unidade
- [ ] Envia WhatsApp para gerentes da unidade
- [ ] Mensagem lista equipamentos e sugere ação

---

### 3.3 US-009: Alertas de Estoque Crítico

**Prioridade**: 🔴 ALTA
**Estimativa**: ~50 linhas de código
**Arquivos**: `app/tasks/system_tasks.py`, `config/celery_beat_schedule.py`

#### Descrição

Task diária verificando itens abaixo do estoque mínimo e notificando comprador.

#### Requisitos Funcionais

1. **Agendamento**
   - Task executada diariamente às 08:00 (junto com morning briefing)

2. **Detecção**
   - Query: `EstoqueSaldo.quantidade < Estoque.quantidade_minima`
   - Agrupar por unidade

3. **Notificação**
   - Enviar WhatsApp para compradores
   - Listar itens críticos por unidade

#### Implementação

```python
# app/tasks/system_tasks.py

@celery.task
def verificar_estoque_critico():
    """
    Verifica itens com estoque abaixo do mínimo.
    Envia alerta para compradores.
    Executado diariamente às 08:00.
    """
    # Query: Itens críticos
    itens_criticos = db.session.query(
        Estoque,
        EstoqueSaldo,
        Unidade.nome.label('unidade_nome')
    ).join(EstoqueSaldo).join(Unidade).filter(
        EstoqueSaldo.quantidade < Estoque.quantidade_minima,
        Unidade.ativo == True
    ).all()

    if not itens_criticos:
        return  # Sem problemas

    # Agrupar por unidade
    alertas_por_unidade = {}
    for item in itens_criticos:
        estoque = item.Estoque
        saldo = item.EstoqueSaldo
        unidade_nome = item.unidade_nome

        if unidade_nome not in alertas_por_unidade:
            alertas_por_unidade[unidade_nome] = []

        alertas_por_unidade[unidade_nome].append({
            'nome': estoque.nome,
            'codigo': estoque.codigo,
            'quantidade': saldo.quantidade,
            'minimo': estoque.quantidade_minima,
            'unidade_medida': estoque.unidade_medida
        })

    # Montar mensagem geral
    mensagem = f"""🟡 *ALERTA DE ESTOQUE CRÍTICO*

Os seguintes itens estão abaixo do estoque mínimo:

"""

    for unidade_nome, itens in alertas_por_unidade.items():
        mensagem += f"📍 *{unidade_nome}*\n"
        for item in itens:
            mensagem += f"  • {item['nome']} ({item['codigo']})\n"
            mensagem += f"    Atual: {item['quantidade']} {item['unidade_medida']} | "
            mensagem += f"Mínimo: {item['minimo']} {item['unidade_medida']}\n"
        mensagem += "\n"

    mensagem += "💡 Verifique necessidade de compra urgente."

    # Buscar compradores
    compradores = Usuario.query.filter(
        Usuario.tipo.in_(['comprador', 'admin']),
        Usuario.ativo == True,
        Usuario.telefone.isnot(None)
    ).all()

    for comprador in compradores:
        try:
            WhatsAppService.enviar_mensagem(
                telefone=comprador.telefone,
                texto=mensagem,
                prioridade=2
            )
        except Exception as e:
            print(f"Erro ao enviar alerta para {comprador.nome}: {e}")
```

**Agendar Task**:

```python
# config/celery_beat_schedule.py

CELERYBEAT_SCHEDULE = {
    # ... existentes ...

    'verificar-estoque-critico': {
        'task': 'app.tasks.system_tasks.verificar_estoque_critico',
        'schedule': crontab(hour=8, minute=0),  # Diário às 08:00
    },
}
```

#### Testes de Aceitação

- [ ] Task executada diariamente às 08:00
- [ ] Detecta itens com `quantidade < quantidade_minima`
- [ ] Agrupa por unidade
- [ ] Envia WhatsApp para compradores
- [ ] Mensagem lista itens críticos com quantidades

---

### 3.4 US-010: Botões Check-in/Check-out via WhatsApp

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~100 linhas de código
**Arquivos**: `app/services/roteamento_service.py`, `app/services/whatsapp_service.py`

#### Descrição

Permitir que técnicos iniciem, pausem e finalizem OSs diretamente pelo WhatsApp usando botões interativos.

#### Requisitos Funcionais

1. **Comando #MINHAS_OS**
   - Listar OSs atribuídas ao técnico
   - Para cada OS, mostrar botões de ação baseados no status

2. **Botões por Status**
   - OS aberta: [▶️ Iniciar]
   - OS em andamento: [⏸️ Pausar] [✅ Finalizar]
   - OS pausada: [▶️ Continuar]

3. **Ações**
   - Iniciar: Gravar `data_inicio`, mudar status para 'em_andamento'
   - Pausar: Calcular tempo, acumular em `tempo_execucao_minutos`
   - Finalizar: Solicitar foto e descrição da solução

#### Implementação

```python
# app/services/comando_executores.py (modificar executar_status)

def executar_status(solicitante):
    """
    Lista OSs do técnico com botões de ação.
    """
    # Buscar OSs abertas e em andamento
    oss = OrdemServico.query.filter(
        OrdemServico.tecnico_id == solicitante.id,
        OrdemServico.status.in_(['aberta', 'em_andamento', 'pausada'])
    ).order_by(OrdemServico.prioridade.desc()).limit(5).all()

    if not oss:
        return "Você não tem OSs em aberto no momento."

    # Para cada OS, enviar mensagem com botões
    for os in oss:
        # Emojis por status
        status_emoji = {
            'aberta': '🔴',
            'em_andamento': '🟡',
            'pausada': '🟠'
        }.get(os.status, '⚪')

        # Montar mensagem
        mensagem = f"""{status_emoji} *{os.numero_os}*

*Equipamento:* {os.equipamento.nome if os.equipamento else 'N/A'}
*Prioridade:* {os.prioridade.upper()}
*Status:* {os.status.replace('_', ' ').title()}
"""

        if os.tempo_execucao_minutos:
            mensagem += f"*Tempo executado:* {os.tempo_execucao_minutos} min\n"

        # Botões baseados no status
        buttons = []

        if os.status == 'aberta':
            buttons.append({
                "type": "reply",
                "reply": {"id": f"iniciar_os_{os.id}", "title": "▶️ Iniciar"}
            })

        elif os.status == 'em_andamento':
            buttons.append({
                "type": "reply",
                "reply": {"id": f"pausar_os_{os.id}", "title": "⏸️ Pausar"}
            })
            buttons.append({
                "type": "reply",
                "reply": {"id": f"finalizar_os_{os.id}", "title": "✅ Finalizar"}
            })

        elif os.status == 'pausada':
            buttons.append({
                "type": "reply",
                "reply": {"id": f"continuar_os_{os.id}", "title": "▶️ Continuar"}
            })

        # Enviar mensagem com botões
        if buttons:
            WhatsAppService.send_buttons_message(
                phone=solicitante.telefone,
                body=mensagem,
                buttons=buttons
            )

    return None  # Já enviou mensagens


# app/services/roteamento_service.py (adicionar handlers)

def _iniciar_os(terceirizado, os_id):
    """Inicia execução da OS."""
    os_obj = OrdemServico.query.get(os_id)

    if not os_obj:
        return "❌ OS não encontrada."

    if os_obj.status not in ['aberta', 'pausada']:
        return f"❌ OS {os_obj.numero_os} não pode ser iniciada (status atual: {os_obj.status})."

    # Iniciar
    os_obj.data_inicio = datetime.now()
    os_obj.status = 'em_andamento'
    db.session.commit()

    return f"✅ OS {os_obj.numero_os} iniciada! Boa sorte! 💪"


def _pausar_os(terceirizado, os_id):
    """Pausa execução da OS."""
    os_obj = OrdemServico.query.get(os_id)

    if not os_obj or os_obj.status != 'em_andamento':
        return "❌ Somente OSs em andamento podem ser pausadas."

    # Calcular tempo
    if os_obj.data_inicio:
        tempo_decorrido = datetime.now() - os_obj.data_inicio
        minutos_decorridos = int(tempo_decorrido.total_seconds() / 60)

        if os_obj.tempo_execucao_minutos:
            os_obj.tempo_execucao_minutos += minutos_decorridos
        else:
            os_obj.tempo_execucao_minutos = minutos_decorridos

    # Pausar
    os_obj.status = 'pausada'
    os_obj.data_inicio = None
    db.session.commit()

    return f"⏸️ OS {os_obj.numero_os} pausada. Tempo executado: {minutos_decorridos} min."


def _finalizar_os_whatsapp(terceirizado, os_id):
    """Inicia fluxo de finalização da OS."""
    os_obj = OrdemServico.query.get(os_id)

    if not os_obj or os_obj.status != 'em_andamento':
        return "❌ Somente OSs em andamento podem ser finalizadas."

    # Salvar contexto
    EstadoService.criar_ou_atualizar_estado(
        telefone=terceirizado.telefone,
        contexto={
            'fluxo': 'finalizando_os',
            'os_id': os_id
        }
    )

    mensagem = f"""✅ *Finalizar OS {os_obj.numero_os}*

Por favor, envie uma *foto do trabalho concluído* (obrigatório)."""

    return mensagem


# Adicionar handlers em processar_resposta_interativa()

elif resposta_id.startswith('iniciar_os_'):
    os_id = int(resposta_id.split('_')[2])
    return RoteamentoService._iniciar_os(terceirizado, os_id)

elif resposta_id.startswith('pausar_os_'):
    os_id = int(resposta_id.split('_')[2])
    return RoteamentoService._pausar_os(terceirizado, os_id)

elif resposta_id.startswith('finalizar_os_'):
    os_id = int(resposta_id.split('_')[2])
    return RoteamentoService._finalizar_os_whatsapp(terceirizado, os_id)

elif resposta_id.startswith('continuar_os_'):
    os_id = int(resposta_id.split('_')[2])
    return RoteamentoService._iniciar_os(terceirizado, os_id)  # Mesmo que iniciar
```

**Processar Foto de Finalização**:

```python
# Adicionar verificação no webhook para imagens

# app/routes/webhook.py (modificar processamento de imagem)

if tipo_conteudo == 'image':
    # Verificar se está em fluxo de finalização
    estado = EstadoConversa.query.filter_by(telefone=remetente).first()

    if estado and estado.contexto.get('fluxo') == 'finalizando_os':
        # Baixar imagem
        baixar_midia_task.delay(notificacao.id, media_url, 'image')

        # Solicitar descrição
        os_id = estado.contexto['os_id']
        estado.contexto['fluxo'] = 'finalizando_os_descricao'
        estado.contexto['foto_notificacao_id'] = notificacao.id
        db.session.commit()

        WhatsAppService.enviar_mensagem(
            remetente,
            "✅ Foto recebida! Agora descreva a solução aplicada:"
        )

        return jsonify({'status': 'ok'}), 200
```

#### Testes de Aceitação

- [ ] Técnico envia `#STATUS` → recebe lista de OSs com botões
- [ ] Técnico clica [▶️ Iniciar] → OS muda para 'em_andamento'
- [ ] Técnico clica [⏸️ Pausar] → tempo é calculado e acumulado
- [ ] Técnico clica [✅ Finalizar] → sistema solicita foto
- [ ] Técnico envia foto e descrição → OS é finalizada

---

## 4. SPRINT 3 - QR CODE COMPLETO (1 semana)

**Objetivo**: Módulo QR Code 100% funcional

### 4.1 US-011: Layout Completo da Etiqueta (5x5cm)

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~80 linhas de código
**Arquivo**: `app/services/qr_service.py`

#### Descrição

Gerar etiqueta completa com QR Code + logo + informações do equipamento em layout profissional 5x5cm.

#### Requisitos Funcionais

1. **Layout**
   - Tamanho: 5x5cm (590x590px @ 300dpi)
   - Logo da empresa no topo (opcional)
   - QR Code centralizado (3x3cm)
   - Nome do equipamento
   - Código patrimonial

2. **Geração**
   - Método: `gerar_etiqueta_completa(equipamento_id)`
   - Salvar em: `/static/uploads/qrcodes/{equipamento_id}.png`

#### Implementação

```python
# app/services/qr_service.py (modificar método existente)

import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
from flask import current_app

class QRCodeService:

    @staticmethod
    def gerar_etiqueta_completa(equipamento_id, incluir_logo=False):
        """
        Gera etiqueta completa (5x5cm) com QR Code + informações.

        Args:
            equipamento_id: ID do equipamento
            incluir_logo: bool - Se deve incluir logo da empresa

        Returns:
            str: Caminho do arquivo PNG gerado
        """
        from app.models.estoque_models import Equipamento

        equipamento = Equipamento.query.get(equipamento_id)
        if not equipamento:
            raise ValueError(f"Equipamento {equipamento_id} não encontrado")

        # Configurações
        DPI = 300
        CM_TO_PX = DPI / 2.54  # 1cm = ~118px @ 300dpi
        ETIQUETA_SIZE = int(5 * CM_TO_PX)  # 5cm = ~590px
        QR_SIZE = int(3 * CM_TO_PX)  # 3cm = ~354px

        # 1. Gerar QR Code
        numero_whatsapp = current_app.config.get('WHATSAPP_NUMBER', '5511999999999')
        url = f"https://wa.me/{numero_whatsapp}?text=EQUIP:{equipamento_id}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,  # 15%
            box_size=10,
            border=2
        )
        qr.add_data(url)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)

        # 2. Criar canvas da etiqueta
        etiqueta = Image.new('RGB', (ETIQUETA_SIZE, ETIQUETA_SIZE), 'white')
        draw = ImageDraw.Draw(etiqueta)

        # 3. Carregar fonte (usar default se Arial não disponível)
        try:
            font_titulo = ImageFont.truetype("arial.ttf", 24)
            font_codigo = ImageFont.truetype("arial.ttf", 20)
        except:
            font_titulo = ImageFont.load_default()
            font_codigo = ImageFont.load_default()

        y_offset = 10

        # 4. Logo da empresa (opcional)
        if incluir_logo:
            logo_path = os.path.join(
                current_app.root_path,
                'static', 'images', 'logo.png'
            )
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                logo.thumbnail((150, 60), Image.LANCZOS)
                logo_x = (ETIQUETA_SIZE - logo.width) // 2
                etiqueta.paste(logo, (logo_x, y_offset))
                y_offset += logo.height + 10

        # 5. Colar QR Code (centralizado)
        qr_x = (ETIQUETA_SIZE - QR_SIZE) // 2
        qr_y = y_offset + 10
        etiqueta.paste(qr_img, (qr_x, qr_y))

        # 6. Adicionar nome do equipamento (abaixo do QR)
        text_y = qr_y + QR_SIZE + 15

        # Nome do equipamento (truncar se muito longo)
        nome = equipamento.nome[:30] + '...' if len(equipamento.nome) > 30 else equipamento.nome

        # Calcular largura do texto para centralizar
        bbox = draw.textbbox((0, 0), nome, font=font_titulo)
        text_width = bbox[2] - bbox[0]
        text_x = (ETIQUETA_SIZE - text_width) // 2

        draw.text((text_x, text_y), nome, fill='black', font=font_titulo)

        # 7. Adicionar código patrimonial
        codigo_y = text_y + 30
        codigo_text = f"Cód: {equipamento.codigo}"

        bbox = draw.textbbox((0, 0), codigo_text, font=font_codigo)
        codigo_width = bbox[2] - bbox[0]
        codigo_x = (ETIQUETA_SIZE - codigo_width) // 2

        draw.text((codigo_x, codigo_y), codigo_text, fill='#666', font=font_codigo)

        # 8. Borda decorativa
        draw.rectangle(
            [(0, 0), (ETIQUETA_SIZE-1, ETIQUETA_SIZE-1)],
            outline='#333',
            width=3
        )

        # 9. Salvar
        pasta_qr = os.path.join(
            current_app.root_path,
            'static', 'uploads', 'qrcodes'
        )
        os.makedirs(pasta_qr, exist_ok=True)

        filename = f"etiqueta_{equipamento_id}.png"
        filepath = os.path.join(pasta_qr, filename)

        etiqueta.save(filepath, dpi=(DPI, DPI))

        return filepath
```

#### Testes de Aceitação

- [ ] Etiqueta gerada em 590x590px (5x5cm @ 300dpi)
- [ ] QR Code centralizado e escaneável
- [ ] Nome do equipamento exibido abaixo do QR
- [ ] Código patrimonial exibido
- [ ] Borda decorativa presente
- [ ] Logo da empresa incluída (se disponível)

---

### 4.2 US-012: Impressão em Massa (PDF Grid 4x4)

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~150 linhas de código
**Arquivos**: `app/services/qr_service.py`, `app/routes/equipamentos.py`

#### Descrição

Gerar PDF A4 com grid 4x4 (16 etiquetas por página) para impressão em massa.

#### Requisitos Funcionais

1. **Layout PDF**
   - Formato: A4 (210 x 297 mm)
   - Grid: 4 colunas x 4 linhas = 16 etiquetas/página
   - Margem: 1cm em todos os lados
   - Espaçamento entre etiquetas: 0.5cm

2. **Endpoint**
   - Rota: `GET /equipamentos/gerar-etiquetas-pdf`
   - Query params: `ids` (lista de IDs) ou `unidade_id` (todos da unidade)

#### Implementação

```python
# app/services/qr_service.py

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

class QRCodeService:

    @staticmethod
    def gerar_pdf_etiquetas_massa(equipamentos_ids):
        """
        Gera PDF A4 com grid 4x4 de etiquetas.

        Args:
            equipamentos_ids: Lista de IDs de equipamentos

        Returns:
            str: Caminho do arquivo PDF gerado
        """
        from app.models.estoque_models import Equipamento

        # Configurações
        MARGEM = 1 * cm
        ESPACAMENTO = 0.5 * cm
        ETIQUETA_SIZE = 5 * cm

        # Calcular posições (4x4)
        A4_WIDTH, A4_HEIGHT = A4

        # Espaço disponível
        espaco_largura = A4_WIDTH - (2 * MARGEM)
        espaco_altura = A4_HEIGHT - (2 * MARGEM)

        # Posições X (4 colunas)
        colunas = []
        for i in range(4):
            x = MARGEM + (i * (ETIQUETA_SIZE + ESPACAMENTO))
            colunas.append(x)

        # Posições Y (4 linhas, de cima para baixo)
        linhas = []
        for i in range(4):
            y = A4_HEIGHT - MARGEM - ETIQUETA_SIZE - (i * (ETIQUETA_SIZE + ESPACAMENTO))
            linhas.append(y)

        # Criar PDF
        pasta_pdf = os.path.join(
            current_app.root_path,
            'static', 'uploads', 'qrcodes'
        )
        os.makedirs(pasta_pdf, exist_ok=True)

        filename = f"etiquetas_massa_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        filepath = os.path.join(pasta_pdf, filename)

        c = canvas.Canvas(filepath, pagesize=A4)

        # Processar equipamentos (16 por página)
        pagina = 0
        for idx, equip_id in enumerate(equipamentos_ids):
            posicao_na_pagina = idx % 16

            # Nova página a cada 16 etiquetas
            if idx > 0 and posicao_na_pagina == 0:
                c.showPage()
                pagina += 1

            # Calcular posição no grid
            linha = posicao_na_pagina // 4
            coluna = posicao_na_pagina % 4

            x = colunas[coluna]
            y = linhas[linha]

            # Gerar etiqueta individual
            try:
                etiqueta_path = QRCodeService.gerar_etiqueta_completa(equip_id)

                # Desenhar etiqueta no PDF
                c.drawImage(
                    etiqueta_path,
                    x, y,
                    width=ETIQUETA_SIZE,
                    height=ETIQUETA_SIZE,
                    preserveAspectRatio=True
                )

            except Exception as e:
                print(f"Erro ao gerar etiqueta para equipamento {equip_id}: {e}")
                # Desenhar placeholder
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                c.rect(x, y, ETIQUETA_SIZE, ETIQUETA_SIZE)
                c.setFont("Helvetica", 10)
                c.drawString(x + 1*cm, y + 2.5*cm, f"Erro: Equip #{equip_id}")

        # Finalizar PDF
        c.save()

        return filepath
```

**Criar Rota**:

```python
# app/routes/equipamentos.py (criar arquivo se não existir)

from flask import Blueprint, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.services.qr_service import QRCodeService
from app.models.estoque_models import Equipamento

bp = Blueprint('equipamentos', __name__, url_prefix='/equipamentos')

@bp.route('/gerar-etiquetas-pdf', methods=['GET', 'POST'])
@login_required
def gerar_etiquetas_pdf():
    """
    Gera PDF com etiquetas em massa.

    Query params:
    - ids: Lista de IDs (ex: ids=1,2,3,4)
    - unidade_id: Todos equipamentos da unidade
    """
    if current_user.tipo not in ['admin', 'gerente']:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('os.index'))

    # Obter IDs
    ids_param = request.args.get('ids')
    unidade_id = request.args.get('unidade_id')

    equipamentos_ids = []

    if ids_param:
        # Lista de IDs fornecida
        equipamentos_ids = [int(id.strip()) for id in ids_param.split(',')]

    elif unidade_id:
        # Todos da unidade
        equipamentos = Equipamento.query.filter_by(
            unidade_id=int(unidade_id),
            ativo=True
        ).all()
        equipamentos_ids = [e.id for e in equipamentos]

    else:
        flash('Forneça parâmetro "ids" ou "unidade_id".', 'warning')
        return redirect(url_for('os.index'))

    if not equipamentos_ids:
        flash('Nenhum equipamento encontrado.', 'warning')
        return redirect(url_for('os.index'))

    # Gerar PDF
    try:
        pdf_path = QRCodeService.gerar_pdf_etiquetas_massa(equipamentos_ids)

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=os.path.basename(pdf_path),
            mimetype='application/pdf'
        )

    except Exception as e:
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('os.index'))


@bp.route('/<int:id>/gerar-etiqueta-individual', methods=['GET'])
@login_required
def gerar_etiqueta_individual(id):
    """Gera e retorna etiqueta individual (PNG) de um equipamento."""
    try:
        etiqueta_path = QRCodeService.gerar_etiqueta_completa(id)

        return send_file(
            etiqueta_path,
            as_attachment=True,
            download_name=f"etiqueta_equip_{id}.png",
            mimetype='image/png'
        )

    except Exception as e:
        flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('os.index'))
```

**Registrar Blueprint**:

```python
# app/__init__.py

def create_app():
    # ... código existente ...

    from app.routes import equipamentos
    app.register_blueprint(equipamentos.bp)
```

#### Testes de Aceitação

- [ ] Endpoint `/equipamentos/gerar-etiquetas-pdf?ids=1,2,3,4` gera PDF
- [ ] PDF contém grid 4x4 (16 etiquetas por página)
- [ ] Margem de 1cm e espaçamento de 0.5cm entre etiquetas
- [ ] Múltiplas páginas se >16 equipamentos
- [ ] PDF pode ser baixado e impresso
- [ ] Endpoint com `unidade_id` gera etiquetas de todos equipamentos da unidade

### 4.3 US-013: Menu Automático Após Escanear QR Code

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~100 linhas de código
**Arquivos**: `app/services/roteamento_service.py`, `app/services/comando_executores.py`

#### Descrição

Implementar fluxo conversacional completo quando usuário escaneia QR Code do equipamento. O sistema deve enviar automaticamente menu interativo com opções de ações relacionadas ao equipamento.

#### Requisitos Funcionais

1. **Detecção de Scan QR**
   - Quando recebe comando `EQUIP:{id}`, armazenar contexto do equipamento no estado do usuário
   - Buscar informações do equipamento no banco
   - Se não encontrado, enviar mensagem de erro

2. **Menu Interativo**
   - Enviar List Message com opções:
     - 📋 Ver Histórico de OSs
     - ➕ Criar Nova OS
     - 📊 Ver Status Atual
     - 📍 Ver Localização
     - 🔙 Voltar ao Menu Principal

3. **Processamento das Opções**
   - **Ver Histórico**: Listar últimas 5 OSs do equipamento com status e data
   - **Criar Nova OS**: Iniciar fluxo de criação com equipamento pré-selecionado
   - **Ver Status**: Mostrar informações (categoria, fabricante, modelo, data instalação)
   - **Ver Localização**: Mostrar unidade, setor, subsistema
   - **Voltar**: Limpar contexto e retornar ao menu principal

4. **Persistência de Contexto**
   - Armazenar `equipamento_id` no estado do chat
   - Manter contexto durante todo o fluxo de criação de OS
   - Limpar contexto após conclusão ou cancelamento

#### Implementação

```python
# app/services/roteamento_service.py

def processar_comando_equip(chat_id, equipamento_id, whatsapp_service):
    """
    Processa scan de QR Code EQUIP:{id}.

    Args:
        chat_id: ID do chat WhatsApp
        equipamento_id: ID do equipamento
        whatsapp_service: Instância do WhatsAppService
    """
    from app.models.models import Equipamento, OrdemServico, Usuario
    from app import db
    from datetime import datetime, timedelta

    # Buscar equipamento
    equipamento = Equipamento.query.get(equipamento_id)

    if not equipamento:
        whatsapp_service.enviar_mensagem(
            chat_id,
            f"❌ *Equipamento não encontrado*\n\nO código {equipamento_id} não existe no sistema."
        )
        return

    # Armazenar contexto
    estado = EstadoService.get_estado(chat_id)
    estado['equipamento_atual'] = equipamento_id
    estado['contexto'] = 'menu_equipamento'
    EstadoService.set_estado(chat_id, estado)

    # Buscar últimas OSs (para mostrar resumo)
    ultimas_os = OrdemServico.query.filter_by(
        equipamento_id=equipamento_id
    ).order_by(
        OrdemServico.data_abertura.desc()
    ).limit(5).all()

    # Construir mensagem de contexto
    mensagem_contexto = f"""
🔧 *{equipamento.nome}*

📂 Categoria: {equipamento.categoria.nome if equipamento.categoria else 'N/A'}
🏢 Unidade: {equipamento.unidade.nome if equipamento.unidade else 'N/A'}
📍 Setor: {equipamento.setor or 'N/A'}

📊 *Resumo Rápido:*
OSs Abertas: {len([os for os in ultimas_os if os.status == 'aberta'])}
Última Manutenção: {ultimas_os[0].data_abertura.strftime('%d/%m/%Y') if ultimas_os else 'Nunca'}

O que você gostaria de fazer?
"""

    # Criar List Message com opções
    opcoes = [
        {
            'id': f'hist_equip_{equipamento_id}',
            'title': '📋 Ver Histórico',
            'description': 'Últimas 5 OSs deste equipamento'
        },
        {
            'id': f'nova_os_equip_{equipamento_id}',
            'title': '➕ Criar Nova OS',
            'description': 'Abrir nova ordem de serviço'
        },
        {
            'id': f'status_equip_{equipamento_id}',
            'title': '📊 Ver Detalhes',
            'description': 'Informações técnicas completas'
        },
        {
            'id': f'localizacao_equip_{equipamento_id}',
            'title': '📍 Ver Localização',
            'description': 'Onde está instalado'
        },
        {
            'id': 'voltar_menu',
            'title': '🔙 Voltar',
            'description': 'Menu principal'
        }
    ]

    whatsapp_service.enviar_list_message(
        chat_id,
        mensagem_contexto,
        "Opções",
        opcoes
    )


def processar_opcao_menu_equipamento(chat_id, opcao_id, whatsapp_service):
    """
    Processa opção selecionada no menu do equipamento.

    Args:
        chat_id: ID do chat
        opcao_id: ID da opção selecionada
        whatsapp_service: Instância do WhatsAppService
    """
    from app.models.models import Equipamento, OrdemServico
    from datetime import datetime

    estado = EstadoService.get_estado(chat_id)
    equipamento_id = estado.get('equipamento_atual')

    if not equipamento_id:
        whatsapp_service.enviar_mensagem(chat_id, "❌ Contexto perdido. Por favor, escaneie o QR Code novamente.")
        return

    equipamento = Equipamento.query.get(equipamento_id)

    # Ver Histórico
    if opcao_id.startswith('hist_equip_'):
        ultimas_os = OrdemServico.query.filter_by(
            equipamento_id=equipamento_id
        ).order_by(
            OrdemServico.data_abertura.desc()
        ).limit(5).all()

        if not ultimas_os:
            mensagem = f"📋 *Histórico de {equipamento.nome}*\n\nNenhuma OS encontrada."
        else:
            mensagem = f"📋 *Histórico de {equipamento.nome}*\n\n"
            for os in ultimas_os:
                status_emoji = {
                    'aberta': '🔴',
                    'em_andamento': '🟡',
                    'pausada': '⏸️',
                    'concluida': '✅',
                    'cancelada': '❌'
                }.get(os.status, '⚪')

                mensagem += f"{status_emoji} *{os.numero_os}*\n"
                mensagem += f"   Data: {os.data_abertura.strftime('%d/%m/%Y')}\n"
                mensagem += f"   Status: {os.status.replace('_', ' ').title()}\n"
                if os.tecnico:
                    mensagem += f"   Técnico: {os.tecnico.nome}\n"
                mensagem += "\n"

        whatsapp_service.enviar_mensagem(chat_id, mensagem)

    # Criar Nova OS
    elif opcao_id.startswith('nova_os_equip_'):
        estado['aguardando'] = 'descricao_os'
        estado['equipamento_pre_selecionado'] = equipamento_id
        EstadoService.set_estado(chat_id, estado)

        whatsapp_service.enviar_mensagem(
            chat_id,
            f"➕ *Nova OS para {equipamento.nome}*\n\n"
            f"Por favor, descreva o problema encontrado:"
        )

    # Ver Detalhes
    elif opcao_id.startswith('status_equip_'):
        mensagem = f"""
📊 *Detalhes Técnicos*

🔧 *{equipamento.nome}*

📂 Categoria: {equipamento.categoria.nome if equipamento.categoria else 'N/A'}
🏭 Fabricante: {equipamento.fabricante or 'N/A'}
📦 Modelo: {equipamento.modelo or 'N/A'}
🔢 Nº Série: {equipamento.numero_serie or 'N/A'}
📅 Instalação: {equipamento.data_instalacao.strftime('%d/%m/%Y') if equipamento.data_instalacao else 'N/A'}
"""

        if equipamento.observacoes:
            mensagem += f"\n📝 Observações:\n{equipamento.observacoes}"

        whatsapp_service.enviar_mensagem(chat_id, mensagem)

    # Ver Localização
    elif opcao_id.startswith('localizacao_equip_'):
        mensagem = f"""
📍 *Localização*

🔧 *{equipamento.nome}*

🏢 Unidade: {equipamento.unidade.nome if equipamento.unidade else 'N/A'}
🏭 Setor: {equipamento.setor or 'N/A'}
⚙️ Subsistema: {equipamento.subsistema or 'N/A'}
"""

        if equipamento.unidade and equipamento.unidade.endereco:
            mensagem += f"\n📬 Endereço:\n{equipamento.unidade.endereco}"

        whatsapp_service.enviar_mensagem(chat_id, mensagem)

    # Voltar
    elif opcao_id == 'voltar_menu':
        estado.pop('equipamento_atual', None)
        estado.pop('contexto', None)
        EstadoService.set_estado(chat_id, estado)

        whatsapp_service.enviar_menu_principal(chat_id)
```

```python
# app/services/comando_executores.py

# Adicionar ao processamento de respostas de List Message

def processar_resposta_list_message(chat_id, opcao_id, whatsapp_service):
    """
    Processa resposta de List Message.
    """
    from app.services.roteamento_service import processar_opcao_menu_equipamento

    # ... código existente para outras opções ...

    # Menu de Equipamento
    if any(opcao_id.startswith(prefix) for prefix in ['hist_equip_', 'nova_os_equip_', 'status_equip_', 'localizacao_equip_']):
        processar_opcao_menu_equipamento(chat_id, opcao_id, whatsapp_service)

    # ... resto do código ...
```

#### Integração

Atualizar `roteamento_service.py` para chamar `processar_comando_equip()` quando detecta padrão `EQUIP:{id}`:

```python
# app/services/roteamento_service.py

def rotear_mensagem(mensagem_obj, whatsapp_service):
    """
    Roteamento principal de mensagens.
    """
    texto = mensagem_obj.texto.strip()
    chat_id = mensagem_obj.chat_id

    # ... código existente ...

    # Detecção de QR Code EQUIP:{id}
    import re
    match_equip = re.match(r'^EQUIP:(\d+)$', texto, re.IGNORECASE)
    if match_equip:
        equipamento_id = int(match_equip.group(1))
        processar_comando_equip(chat_id, equipamento_id, whatsapp_service)
        return

    # ... resto do código de roteamento ...
```

#### Testes de Aceitação

- [ ] Enviar mensagem `EQUIP:1` exibe menu com 5 opções
- [ ] Opção "Ver Histórico" lista últimas 5 OSs
- [ ] Opção "Criar Nova OS" inicia fluxo com equipamento pré-selecionado
- [ ] Opção "Ver Detalhes" mostra informações técnicas completas
- [ ] Opção "Ver Localização" mostra unidade, setor e endereço
- [ ] Opção "Voltar" limpa contexto e retorna ao menu principal
- [ ] Contexto persiste durante todo o fluxo
- [ ] Código de equipamento inválido retorna erro amigável

---

## 5. SPRINT 4 - ANALYTICS AVANÇADO (1 semana)

**Objetivo**: Expandir dashboards com visualizações avançadas e exportações completas

### 5.1 US-014: Timeline Diária (Gráfico Gantt)

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~100 linhas de código
**Arquivos**: `app/routes/analytics.py`, `app/templates/analytics/performance_tecnica.html`

#### Descrição

Criar visualização em timeline (estilo Gantt) mostrando jornada de trabalho vs. execução de OSs para cada técnico.

#### Requisitos Funcionais

1. **Estrutura de Dados**
   - Eixo X: Horário (00:00 - 23:59)
   - Eixo Y: Técnicos (um por linha)
   - Barra Azul: Jornada de trabalho (check-in → check-out)
   - Blocos Verdes: OSs executadas com horário início/fim

2. **Filtros**
   - Data específica (padrão: hoje)
   - Unidade (para Admin/Comprador)
   - Técnico individual (opcional)

3. **Interatividade**
   - Hover sobre barra azul: Mostrar horas totais trabalhadas
   - Hover sobre bloco verde: Mostrar número OS, equipamento, duração

4. **Exportação**
   - Botão para download como imagem PNG

#### Implementação

```python
# app/routes/analytics.py

@bp.route('/timeline-diaria')
@login_required
@roles_required('admin', 'gerente', 'comprador')
def timeline_diaria():
    """
    Timeline Gantt de jornada vs execução.
    """
    from app.models.models import RegistroPonto, OrdemServico, Usuario
    from datetime import datetime, date

    # Filtros
    data_filtro = request.args.get('data', date.today().isoformat())
    unidade_id = request.args.get('unidade_id', type=int)
    tecnico_id = request.args.get('tecnico_id', type=int)

    data_obj = datetime.strptime(data_filtro, '%Y-%m-%d').date()

    # Query técnicos
    query_tecnicos = Usuario.query.filter(
        Usuario.tipo.in_(['tecnico', 'gerente'])
    )

    if unidade_id:
        query_tecnicos = query_tecnicos.filter_by(unidade_id=unidade_id)

    if tecnico_id:
        query_tecnicos = query_tecnicos.filter_by(id=tecnico_id)

    tecnicos = query_tecnicos.all()

    # Construir dados para gráfico
    timeline_data = []

    for tecnico in tecnicos:
        # Buscar registro de ponto
        ponto = RegistroPonto.query.filter(
            RegistroPonto.usuario_id == tecnico.id,
            RegistroPonto.data_entrada == data_obj
        ).first()

        if not ponto:
            continue

        # Barra de jornada
        entrada_minutos = ponto.data_hora_entrada.hour * 60 + ponto.data_hora_entrada.minute

        if ponto.data_hora_saida:
            saida_minutos = ponto.data_hora_saida.hour * 60 + ponto.data_hora_saida.minute
        else:
            saida_minutos = datetime.now().hour * 60 + datetime.now().minute

        jornada_duracao = saida_minutos - entrada_minutos

        # Buscar OSs do dia
        os_list = OrdemServico.query.filter(
            OrdemServico.tecnico_id == tecnico.id,
            db.func.date(OrdemServico.data_abertura) == data_obj
        ).all()

        os_blocos = []
        for os in os_list:
            if os.data_inicio_execucao:
                inicio_minutos = os.data_inicio_execucao.hour * 60 + os.data_inicio_execucao.minute

                if os.data_conclusao:
                    fim_minutos = os.data_conclusao.hour * 60 + os.data_conclusao.minute
                else:
                    fim_minutos = inicio_minutos + (os.tempo_execucao_minutos or 60)

                os_blocos.append({
                    'numero_os': os.numero_os,
                    'equipamento': os.equipamento.nome if os.equipamento else 'N/A',
                    'inicio': inicio_minutos,
                    'fim': fim_minutos,
                    'duracao': fim_minutos - inicio_minutos
                })

        timeline_data.append({
            'tecnico': tecnico.nome,
            'tecnico_id': tecnico.id,
            'jornada_inicio': entrada_minutos,
            'jornada_fim': saida_minutos,
            'jornada_duracao': jornada_duracao,
            'os_blocos': os_blocos
        })

    return jsonify({
        'data': data_filtro,
        'timeline': timeline_data
    })
```

```html
<!-- app/templates/analytics/performance_tecnica.html -->

<!-- Adicionar seção de Timeline -->

<div class="card mt-4">
    <div class="card-header">
        <h5>⏱️ Timeline Diária - Jornada vs. Execução</h5>
    </div>
    <div class="card-body">
        <div class="row mb-3">
            <div class="col-md-4">
                <label>Data:</label>
                <input type="date" id="timeline-data" class="form-control" value="{{ date.today() }}">
            </div>
            <div class="col-md-4">
                <button class="btn btn-primary" onclick="atualizarTimeline()">🔄 Atualizar</button>
                <button class="btn btn-secondary" onclick="exportarTimeline()">💾 Exportar PNG</button>
            </div>
        </div>

        <canvas id="timelineChart" height="400"></canvas>
    </div>
</div>

<script>
let timelineChart = null;

function atualizarTimeline() {
    const data = document.getElementById('timeline-data').value;
    const unidadeId = document.getElementById('filtro-unidade')?.value || '';

    fetch(`/analytics/timeline-diaria?data=${data}&unidade_id=${unidadeId}`)
        .then(response => response.json())
        .then(data => {
            renderizarTimeline(data.timeline);
        });
}

function renderizarTimeline(timelineData) {
    const ctx = document.getElementById('timelineChart').getContext('2d');

    // Destruir gráfico anterior
    if (timelineChart) {
        timelineChart.destroy();
    }

    // Preparar datasets
    const datasets = [];
    const labels = timelineData.map(t => t.tecnico);

    // Dataset de Jornada (azul)
    const jornadas = timelineData.map(t => [t.jornada_inicio, t.jornada_fim]);
    datasets.push({
        label: 'Jornada de Trabalho',
        data: jornadas,
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1
    });

    // Datasets de OSs (verde)
    timelineData.forEach((tecnico, index) => {
        tecnico.os_blocos.forEach((os, osIndex) => {
            const osData = Array(timelineData.length).fill(null);
            osData[index] = [os.inicio, os.fim];

            datasets.push({
                label: os.numero_os,
                data: osData,
                backgroundColor: 'rgba(75, 192, 192, 0.7)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            });
        });
    });

    // Criar gráfico
    timelineChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            indexAxis: 'y',
            scales: {
                x: {
                    type: 'linear',
                    min: 0,
                    max: 1440, // 24 horas em minutos
                    ticks: {
                        callback: function(value) {
                            const horas = Math.floor(value / 60);
                            const minutos = value % 60;
                            return `${horas.toString().padStart(2, '0')}:${minutos.toString().padStart(2, '0')}`;
                        }
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const inicio = context.raw[0];
                            const fim = context.raw[1];
                            const duracao = fim - inicio;

                            const horasInicio = Math.floor(inicio / 60);
                            const minutosInicio = inicio % 60;
                            const horasFim = Math.floor(fim / 60);
                            const minutosFim = fim % 60;

                            return `${context.dataset.label}: ${horasInicio}:${minutosInicio.toString().padStart(2, '0')} - ${horasFim}:${minutosFim.toString().padStart(2, '0')} (${duracao}min)`;
                        }
                    }
                }
            }
        }
    });
}

function exportarTimeline() {
    const canvas = document.getElementById('timelineChart');
    const url = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = 'timeline-diaria.png';
    link.href = url;
    link.click();
}

// Carregar ao abrir página
document.addEventListener('DOMContentLoaded', function() {
    atualizarTimeline();
});
</script>
```

#### Testes de Aceitação

- [ ] Timeline exibe jornada de todos os técnicos da unidade
- [ ] Barras azuis representam check-in até check-out
- [ ] Blocos verdes representam OSs executadas
- [ ] Hover mostra informações detalhadas
- [ ] Filtro por data atualiza gráfico
- [ ] Exportação gera imagem PNG válida
- [ ] Eixo X mostra horários de 00:00 a 23:59

---

### 5.2 US-015: Gráfico Pareto de Defeitos

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~50 linhas de código
**Arquivos**: `app/routes/analytics.py`, `app/templates/analytics/dashboard.html`

#### Descrição

Criar gráfico de Pareto mostrando Top 10 equipamentos com mais ocorrências de OSs, seguindo princípio 80/20.

#### Requisitos Funcionais

1. **Dados**
   - Agrupar OSs por equipamento
   - Ordenar por quantidade (decrescente)
   - Limitar aos Top 10
   - Calcular percentual acumulado

2. **Visualização**
   - Barras: Quantidade de OSs por equipamento
   - Linha: Percentual acumulado
   - Destacar linha de 80% (princípio de Pareto)

3. **Filtros**
   - Período (30 dias, 90 dias, 1 ano)
   - Unidade

#### Implementação

```python
# app/routes/analytics.py

@bp.route('/pareto-defeitos')
@login_required
@roles_required('admin', 'gerente', 'comprador')
def pareto_defeitos():
    """
    Gráfico de Pareto de defeitos por equipamento.
    """
    from app.models.models import OrdemServico, Equipamento
    from datetime import datetime, timedelta
    from sqlalchemy import func

    # Filtros
    periodo_dias = request.args.get('periodo', 30, type=int)
    unidade_id = request.args.get('unidade_id', type=int)

    data_inicio = datetime.now() - timedelta(days=periodo_dias)

    # Query agrupada
    query = db.session.query(
        Equipamento.nome,
        func.count(OrdemServico.id).label('total_os')
    ).join(
        OrdemServico, OrdemServico.equipamento_id == Equipamento.id
    ).filter(
        OrdemServico.data_abertura >= data_inicio
    )

    if unidade_id:
        query = query.filter(Equipamento.unidade_id == unidade_id)

    resultados = query.group_by(
        Equipamento.nome
    ).order_by(
        func.count(OrdemServico.id).desc()
    ).limit(10).all()

    # Calcular percentual acumulado
    total_geral = sum([r.total_os for r in resultados])

    dados_pareto = []
    acumulado = 0

    for equipamento, total_os in resultados:
        percentual = (total_os / total_geral * 100) if total_geral > 0 else 0
        acumulado += percentual

        dados_pareto.append({
            'equipamento': equipamento,
            'total_os': total_os,
            'percentual': round(percentual, 2),
            'acumulado': round(acumulado, 2)
        })

    return jsonify({
        'periodo_dias': periodo_dias,
        'data_inicio': data_inicio.isoformat(),
        'total_geral': total_geral,
        'dados': dados_pareto
    })
```

```html
<!-- app/templates/analytics/dashboard.html -->

<div class="card mt-4">
    <div class="card-header">
        <h5>📊 Pareto de Defeitos - Top 10 Equipamentos</h5>
    </div>
    <div class="card-body">
        <div class="row mb-3">
            <div class="col-md-3">
                <select id="pareto-periodo" class="form-control" onchange="atualizarPareto()">
                    <option value="30">Últimos 30 dias</option>
                    <option value="90">Últimos 90 dias</option>
                    <option value="365">Último ano</option>
                </select>
            </div>
        </div>

        <canvas id="paretoChart" height="100"></canvas>
    </div>
</div>

<script>
let paretoChart = null;

function atualizarPareto() {
    const periodo = document.getElementById('pareto-periodo').value;
    const unidadeId = document.getElementById('filtro-unidade')?.value || '';

    fetch(`/analytics/pareto-defeitos?periodo=${periodo}&unidade_id=${unidadeId}`)
        .then(response => response.json())
        .then(data => {
            renderizarPareto(data.dados);
        });
}

function renderizarPareto(dados) {
    const ctx = document.getElementById('paretoChart').getContext('2d');

    if (paretoChart) {
        paretoChart.destroy();
    }

    const labels = dados.map(d => d.equipamento);
    const totais = dados.map(d => d.total_os);
    const acumulados = dados.map(d => d.acumulado);

    paretoChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Quantidade de OSs',
                    data: totais,
                    backgroundColor: 'rgba(255, 99, 132, 0.5)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: '% Acumulado',
                    data: acumulados,
                    type: 'line',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Quantidade de OSs'
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: '% Acumulado'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            },
            plugins: {
                annotation: {
                    annotations: {
                        line80: {
                            type: 'line',
                            yMin: 80,
                            yMax: 80,
                            yScaleID: 'y1',
                            borderColor: 'red',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            label: {
                                content: 'Regra 80/20',
                                enabled: true
                            }
                        }
                    }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    atualizarPareto();
});
</script>
```

#### Testes de Aceitação

- [ ] Gráfico mostra Top 10 equipamentos com mais OSs
- [ ] Barras ordenadas decrescentemente
- [ ] Linha de percentual acumulado sobe até 100%
- [ ] Linha vermelha tracejada marca 80%
- [ ] Filtro por período atualiza dados
- [ ] Tooltip mostra quantidade exata e percentual

---

### 5.3 US-016: Performance de Fornecedores

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~100 linhas de código
**Arquivos**: `app/routes/analytics.py`, `app/templates/analytics/dashboard.html`

#### Descrição

Dashboard para avaliar desempenho de fornecedores comparando prazo prometido vs. prazo real de entrega.

#### Requisitos Funcionais

1. **Métricas por Fornecedor**
   - Prazo médio prometido (dias)
   - Prazo médio real (dias)
   - Taxa de atraso (%)
   - Quantidade de pedidos

2. **Visualização**
   - Gráfico de radar comparando fornecedores
   - Tabela detalhada com rankings
   - Indicador visual (verde/amarelo/vermelho)

3. **Filtros**
   - Período
   - Status do pedido (apenas concluídos ou todos)

#### Implementação

```python
# app/routes/analytics.py

@bp.route('/performance-fornecedores')
@login_required
@roles_required('admin', 'comprador')
def performance_fornecedores():
    """
    Performance de fornecedores (prazo prometido vs real).
    """
    from app.models.models import PedidoCompra, Fornecedor
    from datetime import datetime, timedelta
    from sqlalchemy import func, case

    periodo_dias = request.args.get('periodo', 90, type=int)
    apenas_concluidos = request.args.get('concluidos', 'true') == 'true'

    data_inicio = datetime.now() - timedelta(days=periodo_dias)

    # Query com cálculos de prazo
    query = db.session.query(
        Fornecedor.nome,
        func.count(PedidoCompra.id).label('total_pedidos'),
        func.avg(
            func.julianday(PedidoCompra.data_prevista) -
            func.julianday(PedidoCompra.data_solicitacao)
        ).label('prazo_medio_prometido'),
        func.avg(
            case(
                (PedidoCompra.data_chegada != None,
                 func.julianday(PedidoCompra.data_chegada) -
                 func.julianday(PedidoCompra.data_solicitacao)),
                else_=None
            )
        ).label('prazo_medio_real'),
        func.sum(
            case(
                (PedidoCompra.data_chegada > PedidoCompra.data_prevista, 1),
                else_=0
            )
        ).label('total_atrasados')
    ).join(
        PedidoCompra, PedidoCompra.fornecedor_id == Fornecedor.id
    ).filter(
        PedidoCompra.data_solicitacao >= data_inicio
    )

    if apenas_concluidos:
        query = query.filter(PedidoCompra.status == 'concluido')

    resultados = query.group_by(Fornecedor.nome).all()

    # Processar dados
    performance = []

    for fornecedor, total, prazo_prom, prazo_real, atrasados in resultados:
        taxa_atraso = (atrasados / total * 100) if total > 0 else 0

        # Classificação
        if taxa_atraso <= 10:
            status = 'excelente'
            cor = '#28a745'
        elif taxa_atraso <= 25:
            status = 'bom'
            cor = '#ffc107'
        else:
            status = 'ruim'
            cor = '#dc3545'

        performance.append({
            'fornecedor': fornecedor,
            'total_pedidos': total,
            'prazo_prometido_dias': round(prazo_prom or 0, 1),
            'prazo_real_dias': round(prazo_real or 0, 1),
            'taxa_atraso_percentual': round(taxa_atraso, 1),
            'status': status,
            'cor': cor
        })

    # Ordenar por taxa de atraso (melhor primeiro)
    performance.sort(key=lambda x: x['taxa_atraso_percentual'])

    return jsonify({
        'periodo_dias': periodo_dias,
        'performance': performance
    })
```

```html
<!-- app/templates/analytics/dashboard.html -->

<div class="card mt-4">
    <div class="card-header">
        <h5>🚚 Performance de Fornecedores</h5>
    </div>
    <div class="card-body">
        <div class="row mb-3">
            <div class="col-md-3">
                <select id="fornec-periodo" class="form-control" onchange="atualizarFornecedores()">
                    <option value="30">Últimos 30 dias</option>
                    <option value="90" selected>Últimos 90 dias</option>
                    <option value="180">Últimos 6 meses</option>
                    <option value="365">Último ano</option>
                </select>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <canvas id="fornecedoresRadarChart"></canvas>
            </div>
            <div class="col-md-6">
                <table class="table table-sm" id="fornecedoresTable">
                    <thead>
                        <tr>
                            <th>Fornecedor</th>
                            <th>Pedidos</th>
                            <th>Prazo Prom.</th>
                            <th>Prazo Real</th>
                            <th>Taxa Atraso</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
let fornecedoresRadarChart = null;

function atualizarFornecedores() {
    const periodo = document.getElementById('fornec-periodo').value;

    fetch(`/analytics/performance-fornecedores?periodo=${periodo}&concluidos=true`)
        .then(response => response.json())
        .then(data => {
            renderizarFornecedores(data.performance);
        });
}

function renderizarFornecedores(performance) {
    // Radar Chart
    const ctx = document.getElementById('fornecedoresRadarChart').getContext('2d');

    if (fornecedoresRadarChart) {
        fornecedoresRadarChart.destroy();
    }

    const labels = performance.map(f => f.fornecedor);
    const taxasAtraso = performance.map(f => 100 - f.taxa_atraso_percentual); // Inverter para melhor=maior

    fornecedoresRadarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Pontualidade (%)',
                data: taxasAtraso,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 2
            }]
        },
        options: {
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    ticks: {
                        stepSize: 20
                    }
                }
            }
        }
    });

    // Tabela
    const tbody = document.querySelector('#fornecedoresTable tbody');
    tbody.innerHTML = '';

    performance.forEach((f, index) => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${f.fornecedor}</td>
            <td>${f.total_pedidos}</td>
            <td>${f.prazo_prometido_dias} dias</td>
            <td>${f.prazo_real_dias} dias</td>
            <td>${f.taxa_atraso_percentual}%</td>
            <td><span class="badge" style="background-color: ${f.cor}">${f.status.toUpperCase()}</span></td>
        `;
    });
}

document.addEventListener('DOMContentLoaded', function() {
    atualizarFornecedores();
});
</script>
```

#### Testes de Aceitação

- [ ] Gráfico radar mostra pontualidade de todos fornecedores
- [ ] Tabela lista fornecedores ordenados por performance
- [ ] Taxa de atraso calculada corretamente
- [ ] Badge colorido indica status (verde/amarelo/vermelho)
- [ ] Filtro por período atualiza dados
- [ ] Prazo real só considera pedidos concluídos

---

### 5.4 US-017: Exportação Excel e PDF Avançada

**Prioridade**: 🟡 MÉDIA
**Estimativa**: ~150 linhas de código
**Arquivos**: `app/routes/analytics.py`

#### Descrição

Adicionar exportação de todos os relatórios em formatos Excel (.xlsx) e PDF com formatação profissional.

#### Requisitos Funcionais

1. **Exportação Excel**
   - Múltiplas abas (Overview, Técnicos, Equipamentos, Fornecedores)
   - Formatação condicional (cores para status)
   - Gráficos embutidos
   - Cabeçalhos com filtros

2. **Exportação PDF**
   - Logo da empresa
   - Cabeçalho com período e filtros aplicados
   - Tabelas formatadas
   - Gráficos como imagens
   - Rodapé com data/hora de geração

3. **Botões de Export**
   - Disponíveis em todos os dashboards
   - Download automático após geração

#### Implementação

```python
# app/routes/analytics.py

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import BarChart, Reference
from io import BytesIO
from weasyprint import HTML
import tempfile

@bp.route('/exportar-excel')
@login_required
@roles_required('admin', 'gerente', 'comprador')
def exportar_excel():
    """
    Exporta dashboard completo em Excel.
    """
    from app.models.models import OrdemServico, Usuario, RegistroPonto
    from datetime import datetime, timedelta

    periodo_dias = request.args.get('periodo', 30, type=int)
    unidade_id = request.args.get('unidade_id', type=int)

    data_inicio = datetime.now() - timedelta(days=periodo_dias)

    # Criar workbook
    wb = Workbook()

    # === ABA 1: Overview ===
    ws_overview = wb.active
    ws_overview.title = "Overview"

    # Cabeçalho
    ws_overview['A1'] = 'RELATÓRIO DE ANALYTICS - GMM'
    ws_overview['A1'].font = Font(size=16, bold=True)
    ws_overview.merge_cells('A1:E1')

    ws_overview['A2'] = f'Período: {data_inicio.strftime("%d/%m/%Y")} - {datetime.now().strftime("%d/%m/%Y")}'
    ws_overview['A2'].font = Font(size=12)

    # KPIs
    ws_overview['A4'] = 'KPI'
    ws_overview['B4'] = 'Valor'
    ws_overview['A4'].font = Font(bold=True)
    ws_overview['B4'].font = Font(bold=True)

    # Calcular KPIs
    total_os = OrdemServico.query.filter(OrdemServico.data_abertura >= data_inicio)
    if unidade_id:
        total_os = total_os.filter_by(unidade_id=unidade_id)
    total_os = total_os.count()

    os_concluidas = OrdemServico.query.filter(
        OrdemServico.data_abertura >= data_inicio,
        OrdemServico.status == 'concluida'
    )
    if unidade_id:
        os_concluidas = os_concluidas.filter_by(unidade_id=unidade_id)
    os_concluidas = os_concluidas.count()

    taxa_conclusao = (os_concluidas / total_os * 100) if total_os > 0 else 0

    kpis = [
        ('Total de OSs', total_os),
        ('OSs Concluídas', os_concluidas),
        ('Taxa de Conclusão', f'{taxa_conclusao:.1f}%'),
    ]

    for i, (kpi, valor) in enumerate(kpis, start=5):
        ws_overview[f'A{i}'] = kpi
        ws_overview[f'B{i}'] = valor

    # === ABA 2: Performance Técnica ===
    ws_tecnicos = wb.create_sheet("Performance Técnica")

    ws_tecnicos['A1'] = 'Técnico'
    ws_tecnicos['B1'] = 'OSs Concluídas'
    ws_tecnicos['C1'] = 'Horas Trabalhadas'
    ws_tecnicos['D1'] = 'Ociosidade (%)'

    # Cabeçalho em negrito
    for cell in ws_tecnicos[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='DDDDDD', end_color='DDDDDD', fill_type='solid')

    # Dados dos técnicos
    tecnicos = Usuario.query.filter_by(tipo='tecnico')
    if unidade_id:
        tecnicos = tecnicos.filter_by(unidade_id=unidade_id)
    tecnicos = tecnicos.all()

    for i, tecnico in enumerate(tecnicos, start=2):
        os_tecnico = OrdemServico.query.filter(
            OrdemServico.tecnico_id == tecnico.id,
            OrdemServico.data_abertura >= data_inicio,
            OrdemServico.status == 'concluida'
        ).count()

        pontos = RegistroPonto.query.filter(
            RegistroPonto.usuario_id == tecnico.id,
            RegistroPonto.data_entrada >= data_inicio.date()
        ).all()

        horas_totais = sum([
            (p.data_hora_saida - p.data_hora_entrada).total_seconds() / 3600
            for p in pontos if p.data_hora_saida
        ])

        ws_tecnicos[f'A{i}'] = tecnico.nome
        ws_tecnicos[f'B{i}'] = os_tecnico
        ws_tecnicos[f'C{i}'] = round(horas_totais, 1)
        ws_tecnicos[f'D{i}'] = '15%'  # Placeholder

    # Adicionar gráfico
    chart = BarChart()
    chart.title = "OSs Concluídas por Técnico"
    chart.x_axis.title = "Técnico"
    chart.y_axis.title = "Quantidade"

    data = Reference(ws_tecnicos, min_col=2, min_row=1, max_row=len(tecnicos)+1)
    cats = Reference(ws_tecnicos, min_col=1, min_row=2, max_row=len(tecnicos)+1)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)

    ws_tecnicos.add_chart(chart, "F2")

    # === ABA 3: Equipamentos ===
    ws_equipamentos = wb.create_sheet("Top Equipamentos")

    ws_equipamentos['A1'] = 'Equipamento'
    ws_equipamentos['B1'] = 'Quantidade de OSs'

    for cell in ws_equipamentos[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='DDDDDD', end_color='DDDDDD', fill_type='solid')

    # Top 10 equipamentos
    from app.models.models import Equipamento
    from sqlalchemy import func

    top_equipamentos = db.session.query(
        Equipamento.nome,
        func.count(OrdemServico.id).label('total')
    ).join(
        OrdemServico
    ).filter(
        OrdemServico.data_abertura >= data_inicio
    ).group_by(
        Equipamento.nome
    ).order_by(
        func.count(OrdemServico.id).desc()
    ).limit(10).all()

    for i, (nome, total) in enumerate(top_equipamentos, start=2):
        ws_equipamentos[f'A{i}'] = nome
        ws_equipamentos[f'B{i}'] = total

    # Salvar em memória
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'analytics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )


@bp.route('/exportar-pdf')
@login_required
@roles_required('admin', 'gerente', 'comprador')
def exportar_pdf():
    """
    Exporta dashboard em PDF.
    """
    from datetime import datetime, timedelta

    periodo_dias = request.args.get('periodo', 30, type=int)
    unidade_id = request.args.get('unidade_id', type=int)

    data_inicio = datetime.now() - timedelta(days=periodo_dias)

    # Buscar dados (reutilizar lógica do Excel)
    total_os = OrdemServico.query.filter(OrdemServico.data_abertura >= data_inicio)
    if unidade_id:
        total_os = total_os.filter_by(unidade_id=unidade_id)
    total_os = total_os.count()

    # Renderizar template HTML
    html_content = render_template(
        'analytics/export_pdf.html',
        data_inicio=data_inicio,
        data_fim=datetime.now(),
        total_os=total_os,
        # ... outros dados
    )

    # Converter para PDF
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)
    pdf_file.seek(0)

    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'analytics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )
```

```html
<!-- app/templates/analytics/export_pdf.html -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #333;
            margin: 0;
        }
        .header p {
            color: #666;
            font-size: 14px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            font-size: 12px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Relatório de Analytics - GMM</h1>
        <p>Período: {{ data_inicio.strftime('%d/%m/%Y') }} - {{ data_fim.strftime('%d/%m/%Y') }}</p>
        <p>Gerado em: {{ data_fim.strftime('%d/%m/%Y %H:%M:%S') }}</p>
    </div>

    <h2>KPIs Principais</h2>
    <table>
        <tr>
            <th>Indicador</th>
            <th>Valor</th>
        </tr>
        <tr>
            <td>Total de OSs</td>
            <td>{{ total_os }}</td>
        </tr>
        <!-- Adicionar mais KPIs -->
    </table>

    <div class="footer">
        <p>Sistema GMM - Gestão de Manutenção e Manutenção</p>
    </div>
</body>
</html>
```

#### Dependências

Adicionar ao `requirements.txt`:

```
openpyxl==3.1.2
weasyprint==60.1
```

#### Testes de Aceitação

- [ ] Botão "Exportar Excel" gera arquivo .xlsx válido
- [ ] Excel contém 3 abas (Overview, Técnicos, Equipamentos)
- [ ] Cabeçalhos formatados em negrito com fundo cinza
- [ ] Gráfico de barras embutido na aba "Performance Técnica"
- [ ] Botão "Exportar PDF" gera arquivo .pdf válido
- [ ] PDF contém logo, cabeçalho, tabelas e rodapé
- [ ] Download automático após geração

---

### 5.5 US-018: Paginação Infinita na Central de Mensagens

**Prioridade**: 🟢 BAIXA
**Estimativa**: ~50 linhas de código
**Arquivos**: `app/templates/admin/chat_central.html`, `app/routes/admin_whatsapp.py`

#### Descrição

Implementar scroll infinito na central de mensagens para melhorar performance quando há muitas mensagens.

#### Requisitos Funcionais

1. **Carregamento Inicial**
   - Carregar últimas 50 mensagens

2. **Scroll Infinito**
   - Quando usuário rola para o topo, carregar mais 50 mensagens antigas
   - Mostrar indicador de loading

3. **Performance**
   - Lazy loading de imagens
   - Virtualização de mensagens antigas

#### Implementação

```javascript
// app/templates/admin/chat_central.html

<script>
let currentOffset = 0;
const LIMIT = 50;
let isLoading = false;
let hasMore = true;

function carregarMensagensAntigas() {
    if (isLoading || !hasMore) return;

    isLoading = true;
    const chatId = chatSelecionado;

    fetch(`/admin-whatsapp/mensagens/${chatId}?offset=${currentOffset}&limit=${LIMIT}`)
        .then(response => response.json())
        .then(data => {
            if (data.mensagens.length < LIMIT) {
                hasMore = false;
            }

            // Adicionar mensagens no topo
            const container = document.getElementById('mensagens-container');
            const scrollHeight = container.scrollHeight;

            data.mensagens.reverse().forEach(msg => {
                const div = criarDivMensagem(msg);
                container.insertBefore(div, container.firstChild);
            });

            // Manter posição do scroll
            container.scrollTop = container.scrollHeight - scrollHeight;

            currentOffset += data.mensagens.length;
            isLoading = false;
        });
}

// Detectar scroll no topo
document.getElementById('mensagens-container').addEventListener('scroll', function(e) {
    if (e.target.scrollTop < 100) {
        carregarMensagensAntigas();
    }
});
</script>
```

```python
# app/routes/admin_whatsapp.py

@bp.route('/mensagens/<chat_id>')
@login_required
@roles_required('admin')
def listar_mensagens(chat_id):
    """
    Lista mensagens com paginação.
    """
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    mensagens = MensagemWhatsApp.query.filter_by(
        chat_id=chat_id
    ).order_by(
        MensagemWhatsApp.data_hora.desc()
    ).offset(offset).limit(limit).all()

    return jsonify({
        'mensagens': [m.to_dict() for m in mensagens],
        'offset': offset,
        'limit': limit,
        'total': MensagemWhatsApp.query.filter_by(chat_id=chat_id).count()
    })
```

#### Testes de Aceitação

- [ ] Carregamento inicial mostra últimas 50 mensagens
- [ ] Scroll para o topo carrega mais 50 mensagens
- [ ] Indicador de loading aparece durante carregamento
- [ ] Posição do scroll mantém-se após carregar
- [ ] Não carrega mais quando todas mensagens já exibidas

---

## 6. INFRAESTRUTURA E CONFIGURAÇÃO

### 6.1 Requisitos de Infraestrutura

#### Produção

1. **Servidor de Aplicação**
   - **OS**: Ubuntu 22.04 LTS ou CentOS 8
   - **CPU**: 4 cores (mínimo 2 cores)
   - **RAM**: 8 GB (mínimo 4 GB)
   - **Disco**: 100 GB SSD

2. **Banco de Dados**
   - **PostgreSQL 14+**
   - **Configurações**:
     ```ini
     max_connections = 100
     shared_buffers = 2GB
     effective_cache_size = 6GB
     work_mem = 20MB
     ```

3. **Redis**
   - **Versão**: 6.2+
   - **Memória**: 1 GB dedicado
   - **Configurações**:
     ```ini
     maxmemory 1gb
     maxmemory-policy allkeys-lru
     ```

4. **Serviços**
   - **Gunicorn**: 4 workers (2 * cores + 1)
   - **Celery Worker**: 4 workers
   - **Celery Beat**: 1 instância
   - **Nginx**: Proxy reverso

#### Desenvolvimento

- SQLite (já configurado)
- Redis local
- Flask development server

### 6.2 Configurações de Segurança

#### 6.2.1 Timeout de Sessão (4 horas)

```python
# config.py

class Config:
    # ... existente ...

    # Sessão expira após 4 horas de inatividade
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True  # Apenas HTTPS em produção
    SESSION_COOKIE_SAMESITE = 'Lax'
```

```python
# app/routes/auth.py

@bp.route('/login', methods=['POST'])
def login():
    # ... código existente ...

    if usuario and check_password_hash(usuario.senha, senha):
        login_user(usuario, remember=True)
        session.permanent = True  # Ativa timeout de 4h

        # ... resto do código ...
```

#### 6.2.2 IP Whitelist para Webhook

```python
# app/routes/webhook.py

from functools import wraps
from flask import request, abort

# IPs permitidos da MegaAPI
WEBHOOK_ALLOWED_IPS = [
    '187.17.192.0/24',  # Range MegaAPI
    '200.204.0.0/16',   # Range MegaAPI secundário
    '127.0.0.1',        # Localhost (desenvolvimento)
]

def ip_whitelist_required(f):
    """
    Decorator para validar IP do webhook.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        # Extrair primeiro IP se houver múltiplos proxies
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        # Verificar whitelist
        from ipaddress import ip_address, ip_network

        allowed = False
        for allowed_range in WEBHOOK_ALLOWED_IPS:
            if '/' in allowed_range:
                if ip_address(client_ip) in ip_network(allowed_range):
                    allowed = True
                    break
            else:
                if client_ip == allowed_range:
                    allowed = True
                    break

        if not allowed:
            current_app.logger.warning(f"Webhook bloqueado de IP não autorizado: {client_ip}")
            abort(403)

        return f(*args, **kwargs)
    return decorated_function

@bp.route('/webhook', methods=['POST'])
@ip_whitelist_required  # Aplicar whitelist
def webhook():
    # ... código existente ...
```

#### 6.2.3 Rotação de API Keys (90 dias)

```python
# app/tasks/system_tasks.py

from celery import shared_task
from datetime import datetime, timedelta
from app import db
from app.models.whatsapp_models import ConfiguracaoWhatsApp

@shared_task
def verificar_expiracao_api_keys():
    """
    Task Celery para alertar sobre API Keys próximas da expiração.

    Executa diariamente às 09:00.
    """
    configs = ConfiguracaoWhatsApp.query.filter_by(ativo=True).all()

    for config in configs:
        if not config.data_criacao_chave:
            continue

        dias_desde_criacao = (datetime.now() - config.data_criacao_chave).days

        # Alertar se > 80 dias (10 dias antes dos 90)
        if dias_desde_criacao >= 80:
            dias_restantes = 90 - dias_desde_criacao

            # Enviar email para admin
            from app.services.email_service import enviar_email

            enviar_email(
                destinatario='admin@empresa.com',
                assunto=f'⚠️ API Key WhatsApp próxima da expiração ({dias_restantes} dias)',
                corpo=f"""
                A API Key da instância {config.nome_instancia} está próxima da expiração.

                Data de criação: {config.data_criacao_chave.strftime('%d/%m/%Y')}
                Dias desde criação: {dias_desde_criacao}
                Dias restantes: {dias_restantes}

                Por favor, gere uma nova chave antes do vencimento para evitar interrupções.
                """
            )

            current_app.logger.warning(
                f"API Key {config.nome_instancia} expira em {dias_restantes} dias"
            )
```

```python
# config/celery_beat_schedule.py

# Adicionar task de verificação de API Keys

CELERY_BEAT_SCHEDULE = {
    # ... existente ...

    'verificar-expiracao-api-keys': {
        'task': 'app.tasks.system_tasks.verificar_expiracao_api_keys',
        'schedule': crontab(hour=9, minute=0),  # Diariamente às 09:00
    },
}
```

```python
# app/models/whatsapp_models.py

# Adicionar campo ao modelo

class ConfiguracaoWhatsApp(db.Model):
    # ... campos existentes ...

    data_criacao_chave = db.Column(db.DateTime, nullable=True)

    # ... resto do modelo ...
```

Migração:

```bash
flask db migrate -m "add data_criacao_chave to ConfiguracaoWhatsApp"
flask db upgrade
```

### 6.3 Backup Automatizado

#### 6.3.1 Script de Backup

Criar arquivo `scripts/backup.sh`:

```bash
#!/bin/bash

# Configurações
BACKUP_DIR="/var/backups/gmm"
DB_NAME="gmm_db"
DB_USER="gmm_user"
RETENTION_DAYS=30
RETENTION_WEEKS=12

# Criar diretório de backup
mkdir -p "$BACKUP_DIR/daily"
mkdir -p "$BACKUP_DIR/weekly"

# Timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DAY_OF_WEEK=$(date +"%u")  # 1=Monday, 7=Sunday

# Backup diário do banco de dados
echo "[$(date)] Iniciando backup diário..."
pg_dump -U $DB_USER -Fc $DB_NAME > "$BACKUP_DIR/daily/backup_$TIMESTAMP.dump"

# Backup semanal (aos domingos)
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    echo "[$(date)] Criando backup semanal..."
    cp "$BACKUP_DIR/daily/backup_$TIMESTAMP.dump" "$BACKUP_DIR/weekly/backup_$TIMESTAMP.dump"
fi

# Backup de arquivos de mídia
tar -czf "$BACKUP_DIR/daily/media_$TIMESTAMP.tar.gz" \
    /var/www/gmm/app/static/uploads

# Limpeza de backups antigos
echo "[$(date)] Limpando backups antigos..."

# Remover backups diários > 30 dias
find "$BACKUP_DIR/daily" -name "*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR/daily" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Remover backups semanais > 12 semanas (84 dias)
find "$BACKUP_DIR/weekly" -name "*.dump" -mtime +$((RETENTION_WEEKS * 7)) -delete

echo "[$(date)] Backup concluído com sucesso!"

# Verificar integridade do último backup
LAST_BACKUP=$(ls -t "$BACKUP_DIR/daily"/*.dump | head -1)
pg_restore --list "$LAST_BACKUP" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] Verificação de integridade: OK"
else
    echo "[$(date)] ERRO: Backup corrompido!"
    # Enviar alerta (implementar notificação)
fi
```

Dar permissão de execução:

```bash
chmod +x scripts/backup.sh
```

#### 6.3.2 Cron Job para Backup

```bash
# Editar crontab
crontab -e

# Adicionar linha (backup diário às 02:00)
0 2 * * * /var/www/gmm/scripts/backup.sh >> /var/log/gmm/backup.log 2>&1
```

### 6.4 Política de Retenção de Mídias

```python
# app/tasks/system_tasks.py

@shared_task
def limpar_midias_antigas():
    """
    Remove arquivos de mídia com mais de 90 dias.

    Executa mensalmente no dia 1 às 03:00.
    """
    from pathlib import Path
    import os
    from datetime import datetime, timedelta

    RETENTION_DAYS = 90
    MEDIA_DIRS = [
        'app/static/uploads/audios',
        'app/static/uploads/chamados',
        'app/static/uploads/os'
    ]

    data_limite = datetime.now() - timedelta(days=RETENTION_DAYS)
    total_removidos = 0
    espaco_liberado = 0

    for media_dir in MEDIA_DIRS:
        for arquivo in Path(media_dir).rglob('*'):
            if arquivo.is_file():
                # Verificar data de modificação
                mtime = datetime.fromtimestamp(arquivo.stat().st_mtime)

                if mtime < data_limite:
                    tamanho = arquivo.stat().st_size
                    arquivo.unlink()

                    total_removidos += 1
                    espaco_liberado += tamanho

    # Log
    espaco_mb = espaco_liberado / (1024 * 1024)
    current_app.logger.info(
        f"Limpeza de mídias: {total_removidos} arquivos removidos, "
        f"{espaco_mb:.2f} MB liberados"
    )

    return {
        'arquivos_removidos': total_removidos,
        'espaco_liberado_mb': round(espaco_mb, 2)
    }
```

```python
# config/celery_beat_schedule.py

CELERY_BEAT_SCHEDULE = {
    # ... existente ...

    'limpar-midias-antigas': {
        'task': 'app.tasks.system_tasks.limpar_midias_antigas',
        'schedule': crontab(day_of_month=1, hour=3, minute=0),  # Dia 1 de cada mês às 03:00
    },
}
```

### 6.5 Monitoramento de Uptime

#### 6.5.1 Endpoint de Health Check

```python
# app/routes/admin.py

@bp.route('/health')
def health_check():
    """
    Endpoint para monitoramento de saúde da aplicação.

    Verifica:
    - Conexão com banco de dados
    - Conexão com Redis
    - Status do Celery
    - Espaço em disco
    """
    from sqlalchemy import text
    from redis import Redis
    import psutil

    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }

    # 1. Verificar banco de dados
    try:
        db.session.execute(text('SELECT 1'))
        health_status['checks']['database'] = 'OK'
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['database'] = f'ERRO: {str(e)}'

    # 2. Verificar Redis
    try:
        redis_client = Redis.from_url(current_app.config['CELERY_BROKER_URL'])
        redis_client.ping()
        health_status['checks']['redis'] = 'OK'
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['redis'] = f'ERRO: {str(e)}'

    # 3. Verificar Celery
    try:
        from app import celery
        stats = celery.control.inspect().stats()

        if stats:
            health_status['checks']['celery'] = f'OK ({len(stats)} workers)'
        else:
            health_status['status'] = 'degraded'
            health_status['checks']['celery'] = 'AVISO: Nenhum worker ativo'
    except Exception as e:
        health_status['status'] = 'degraded'
        health_status['checks']['celery'] = f'ERRO: {str(e)}'

    # 4. Verificar espaço em disco
    try:
        disk = psutil.disk_usage('/')
        percent_used = disk.percent

        if percent_used > 90:
            health_status['status'] = 'degraded'
            health_status['checks']['disk'] = f'AVISO: {percent_used}% usado'
        elif percent_used > 95:
            health_status['status'] = 'unhealthy'
            health_status['checks']['disk'] = f'CRÍTICO: {percent_used}% usado'
        else:
            health_status['checks']['disk'] = f'OK ({percent_used}% usado)'
    except Exception as e:
        health_status['checks']['disk'] = f'ERRO: {str(e)}'

    # Código de status HTTP baseado na saúde
    status_code = 200
    if health_status['status'] == 'degraded':
        status_code = 200  # Ainda operacional
    elif health_status['status'] == 'unhealthy':
        status_code = 503  # Serviço indisponível

    return jsonify(health_status), status_code
```

#### 6.5.2 Integração com Prometheus (Opcional)

Adicionar ao `requirements.txt`:

```
prometheus-client==0.19.0
```

```python
# app/__init__.py

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Métricas
http_requests_total = Counter(
    'http_requests_total',
    'Total de requisições HTTP',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'Duração das requisições HTTP',
    ['method', 'endpoint']
)

@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.endpoint or 'unknown'
        ).observe(duration)

        http_requests_total.labels(
            method=request.method,
            endpoint=request.endpoint or 'unknown',
            status=response.status_code
        ).inc()

    return response

@app.route('/metrics')
def metrics():
    """
    Endpoint para Prometheus scraping.
    """
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
```

---

## 7. CRITÉRIOS DE ACEITAÇÃO

### 7.1 Critérios Globais

Todos os user stories devem atender:

- [ ] Código segue padrão PEP 8 (Python)
- [ ] Funções documentadas com docstrings
- [ ] Tratamento de erros com try/except apropriado
- [ ] Logs informativos em pontos críticos
- [ ] Sem queries N+1 (usar joinedload onde necessário)
- [ ] Validação de entrada de dados
- [ ] Testes manuais realizados em desenvolvimento
- [ ] Integração testada com módulos existentes

### 7.2 Critérios de Performance

- [ ] Endpoints API respondem em < 500ms (média)
- [ ] Dashboards carregam em < 2 segundos
- [ ] Exportações (Excel/PDF) geram em < 5 segundos
- [ ] Queries de banco otimizadas (sem SCAN completo de tabelas grandes)
- [ ] Redis usado para cache quando apropriado

### 7.3 Critérios de Segurança

- [ ] Nenhuma credencial ou API Key em código-fonte
- [ ] Validação de permissões em todas as rotas
- [ ] Sanitização de inputs do usuário
- [ ] Proteção contra SQL Injection (usar ORM)
- [ ] Proteção contra XSS (usar Jinja2 autoescape)
- [ ] CSRF tokens em formulários

### 7.4 Critérios de Usabilidade

- [ ] Mensagens de erro claras e em português
- [ ] Feedback visual para ações do usuário
- [ ] Loaders durante operações assíncronas
- [ ] Layout responsivo (mobile-friendly)
- [ ] Acessibilidade básica (alt text em imagens, labels em inputs)

---

## 8. RISCOS E MITIGAÇÕES

### 8.1 Riscos Técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **API OpenAI indisponível** | Média | Alto | Implementar fallback sem NLP + cache de resultados + retry com backoff exponencial |
| **Webhook MegaAPI instável** | Baixa | Alto | Circuit Breaker já implementado + logs detalhados + fila de retry |
| **Estouro de memória Redis** | Baixa | Médio | Política LRU configurada + monitoramento de uso + limpeza de chaves expiradas |
| **Queries lentas em produção** | Média | Médio | Índices em colunas críticas + EXPLAIN ANALYZE antes deploy + caching |
| **Conflitos de migração** | Alta | Baixo | Testes em ambiente de staging + backup antes migrate + rollback script |

### 8.2 Riscos de Negócio

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Usuários não adotam QR Code** | Média | Médio | Treinamento + gamificação + incentivos para uso |
| **Alertas considerados spam** | Alta | Médio | Permitir configuração de preferências + opt-out parcial |
| **Custo de API OpenAI alto** | Média | Médio | Monitorar uso + limitar transcrições por usuário/dia + otimizar prompts |

### 8.3 Riscos de Prazo

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Complexidade subestimada** | Média | Alto | Buffer de 20% no prazo + revisão semanal + priorizar MVPs |
| **Dependências de terceiros** | Baixa | Alto | Testar integrações no Sprint 1 + ter alternativas |
| **Falta de recursos** | Baixa | Alto | Documentação detalhada + pair programming quando possível |

---

## 9. CRONOGRAMA RESUMIDO

### Semana 1 - Sprint 1 (Crítico)
**Dias 1-2**: US-001, US-002 (voz + QR Code)
**Dias 3-4**: US-003, US-004 (PDF + tempo execução)
**Dia 5**: US-005, US-006 (SLA + aprovação automática) + testes

### Semana 2 - Sprint 2 (Alertas)
**Dias 1-2**: US-007 (Morning Briefing) + US-008 (Preditivo)
**Dias 3-4**: US-009 (Estoque crítico) + US-010 (Check-in/out)
**Dia 5**: Testes integrados + ajustes

### Semana 3 - Sprint 3 (QR Code)
**Dias 1-2**: US-011 (Layout etiqueta)
**Dias 3-4**: US-012 (Impressão massa) + US-013 (Menu QR)
**Dia 5**: Testes end-to-end de QR Code

### Semana 4 - Sprint 4 (Analytics)
**Dias 1-2**: US-014 (Timeline) + US-015 (Pareto)
**Dias 3-4**: US-016 (Fornecedores) + US-017 (Exportação)
**Dia 5**: US-018 (Paginação) + testes finais

---

## 10. DEFINIÇÃO DE PRONTO (DEFINITION OF DONE)

Um user story é considerado **PRONTO** quando:

- [ ] ✅ Código implementado conforme especificação
- [ ] ✅ Testes de aceitação passando (100%)
- [ ] ✅ Code review realizado (se equipe > 1 pessoa)
- [ ] ✅ Documentação atualizada (docstrings + README se aplicável)
- [ ] ✅ Testado em ambiente de desenvolvimento
- [ ] ✅ Migração de banco criada (se houver mudanças no schema)
- [ ] ✅ Logs adicionados em operações críticas
- [ ] ✅ Tratamento de erros implementado
- [ ] ✅ Integração com módulos existentes validada
- [ ] ✅ Performance verificada (sem queries N+1)
- [ ] ✅ Segurança revisada (validação de inputs, permissões)
- [ ] ✅ Deploy em staging OK (antes de produção)

---

## 11. PRÓXIMOS PASSOS APÓS IMPLEMENTAÇÃO

### 11.1 Fase de Testes (1 semana)
- Testes de integração completos
- Testes de carga (simular 100 usuários simultâneos)
- Testes de regressão (garantir que funcionalidades antigas ainda funcionam)

### 11.2 Documentação Final (1 semana)
- [ ] API Documentation (Swagger/OpenAPI)
- [ ] Guia de Deployment em Produção
- [ ] Runbook de Operações (troubleshooting)
- [ ] Manual do Usuário Final

### 11.3 Deploy em Produção
- [ ] Migração de banco de dados (com rollback planejado)
- [ ] Configuração de monitoramento (Prometheus/Grafana)
- [ ] Backup inicial
- [ ] Go-live

---

**FIM DO PRD**

**Documento Vivo**: Este PRD deve ser atualizado conforme surgem descobertas durante a implementação.

**Versão**: 1.0
**Data**: Janeiro 2026
**Responsável**: Equipe GMM
**Aprovação**: Pendente