# Especificação Completa - Plataforma GMM v3.1
**Documento Único de Desenvolvimento**
**Data:** Janeiro 2026
**Versão:** 3.1 Definitiva

---

## 📋 ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura & Stack](#2-arquitetura--stack)
3. [Modelo de Dados Completo](#3-modelo-de-dados-completo)
4. [Requisitos Funcionais por Módulo](#4-requisitos-funcionais-por-módulo)
5. [Requisitos Não-Funcionais](#5-requisitos-não-funcionais)
6. [Roadmap de Implementação](#6-roadmap-de-implementação)
7. [Especificações Técnicas de Integração](#7-especificações-técnicas-de-integração)
8. [Custos e Recursos](#8-custos-e-recursos)

---

## 1. VISÃO GERAL

### 1.1 Objetivo do Sistema
Transformar o GMM de um gestor de OS tradicional em um **Ecossistema de Operações Inteligente**, onde o WhatsApp (via MegaAPI) atua como interface primária para técnicos e gestores, eliminando fricção operacional e centralizando dados.

### 1.2 Princípios Fundamentais
- **Zero-Loss**: Nenhuma mensagem ou mídia pode ser perdida (princípio de backup total)
- **Mobile-First**: WhatsApp como canal primário de comunicação
- **Automação Inteligente**: NLP e chatbots reduzem trabalho manual
- **Auditoria Completa**: Todo evento registrado com timestamp e autor

### 1.3 Usuários do Sistema
| Tipo | Funcionalidades Principais |
|------|---------------------------|
| **Técnico** | Receber/executar OS via WhatsApp, solicitar peças, enviar fotos |
| **Comprador** | Gerenciar pedidos, cotações, recebimentos |
| **Gerente** | Aprovar compras, visualizar KPIs, receber alertas |
| **Admin** | Configurar sistema, usuários, unidades |

---

## 2. ARQUITETURA & STACK

### 2.1 Stack Tecnológico
```
┌─────────────────────────────────────┐
│   Frontend: Jinja2 Templates       │
│   + Bootstrap + Chart.js            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Backend: Flask 3.0+               │
│   + SQLAlchemy ORM                  │
│   + Flask-Login (auth)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Async: Celery + Redis             │
│   (Tasks, Beat Schedule)            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Database: SQLite (Dev)            │
│             PostgreSQL (Prod)       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   Integrações Externas:             │
│   - MegaAPI (WhatsApp)              │
│   - OpenAI Whisper (Transcrição)    │
│   - Twilio/AWS SNS (SMS Fallback)   │
│   - SendGrid (Email)                │
└─────────────────────────────────────┘
```

### 2.2 Armazenamento
- **Mídias**: `/static/uploads/whatsapp/{ano}/{mes}/{filename}`
- **Pedidos PDF**: `/static/uploads/pedidos/PEDIDO_{id}.pdf`
- **QR Codes**: `/static/uploads/qr/{equipamento_id}.png`
- **Limite por arquivo**: 10MB
- **Política de Retenção**:
  - 0-3 meses: Disco local (SSD)
  - 3-6 meses: Compressão WebP (-70% tamanho)
  - 6+ meses: Cold Storage (S3 Glacier)

### 2.3 Segurança
- **Autenticação**: Flask-Login com bcrypt
- **Webhook**: HMAC SHA256 signature validation
- **API Keys**: Armazenamento criptografado (Fernet)
- **Backup**: Incremental diário + completo semanal (90 dias retenção)

---

## 3. MODELO DE DADOS COMPLETO

### 3.1 Tabelas Existentes (Já Implementadas)

#### usuarios
```sql
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tipo VARCHAR(20) NOT NULL, -- 'admin', 'tecnico', 'comum'
    email VARCHAR(100),
    telefone VARCHAR(20),
    unidade_id INTEGER REFERENCES unidades(id),
    ativo BOOLEAN DEFAULT TRUE,
    foto_perfil VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### unidades
```sql
CREATE TABLE unidades (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    endereco TEXT,
    telefone VARCHAR(20),
    ip_permitido VARCHAR(50), -- IP whitelisting
    ssid_wifi VARCHAR(100),
    ativo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### equipamentos
```sql
CREATE TABLE equipamentos (
    id INTEGER PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nome VARCHAR(200) NOT NULL,
    categoria_id INTEGER REFERENCES categorias_equipamento(id),
    unidade_id INTEGER REFERENCES unidades(id),
    descricao TEXT,
    status VARCHAR(20) DEFAULT 'operacional', -- 'operacional', 'manutencao', 'inativo'
    custo_aquisicao DECIMAL(10,2),
    data_aquisicao DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### ordens_servico (ATUALIZAR - Campos novos destacados com ⭐)
```sql
CREATE TABLE ordens_servico (
    id INTEGER PRIMARY KEY,
    numero_os VARCHAR(20) UNIQUE NOT NULL,
    equipamento_id INTEGER REFERENCES equipamentos(id),
    unidade_id INTEGER REFERENCES unidades(id),
    tecnico_id INTEGER REFERENCES usuarios(id),
    titulo VARCHAR(200) NOT NULL,
    descricao TEXT,
    prioridade VARCHAR(20) DEFAULT 'media', -- 'baixa', 'media', 'alta', 'urgente'
    status VARCHAR(20) DEFAULT 'aberta', -- 'aberta', 'em_andamento', 'pausada', 'concluida', 'cancelada'
    data_abertura DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_prevista DATE,
    data_inicio DATETIME,
    data_finalizacao DATETIME,
    solucao TEXT,
    ⭐ tempo_execucao_minutos INTEGER, -- Calculado via check-in/out
    ⭐ origem_criacao VARCHAR(20) DEFAULT 'web', -- 'web', 'whatsapp_bot', 'qr_code'
    ⭐ avaliacao INTEGER CHECK(avaliacao BETWEEN 1 AND 5), -- Rating 1-5
    created_by INTEGER REFERENCES usuarios(id),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### estoque
```sql
CREATE TABLE estoque (
    id INTEGER PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    categoria_id INTEGER REFERENCES categorias_estoque(id),
    unidade_medida VARCHAR(20) DEFAULT 'UN', -- 'UN', 'KG', 'M', 'L'
    quantidade_minima INTEGER DEFAULT 0,
    quantidade_global INTEGER DEFAULT 0, -- Total em todas unidades
    preco_medio DECIMAL(10,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### estoque_saldo (Multi-Unidade)
```sql
CREATE TABLE estoque_saldo (
    id INTEGER PRIMARY KEY,
    estoque_id INTEGER REFERENCES estoque(id),
    unidade_id INTEGER REFERENCES unidades(id),
    quantidade INTEGER DEFAULT 0,
    UNIQUE(estoque_id, unidade_id)
);
```

#### movimentacoes_estoque (ATUALIZAR - Campo novo ⭐)
```sql
CREATE TABLE movimentacoes_estoque (
    id INTEGER PRIMARY KEY,
    estoque_id INTEGER REFERENCES estoque(id),
    ⭐ unidade_id INTEGER REFERENCES unidades(id) NOT NULL,
    tipo VARCHAR(20) NOT NULL, -- 'entrada', 'saida', 'transferencia', 'ajuste'
    quantidade INTEGER NOT NULL,
    ⭐ custo_momento DECIMAL(10,2), -- Snapshot do custo unitário
    motivo TEXT,
    os_id INTEGER REFERENCES ordens_servico(id),
    usuario_id INTEGER REFERENCES usuarios(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### terceirizados
```sql
CREATE TABLE terceirizados (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    empresa VARCHAR(100),
    telefone VARCHAR(20) UNIQUE NOT NULL, -- Usado para identificar no WhatsApp
    email VARCHAR(100),
    servico VARCHAR(100), -- Tipo de serviço prestado
    unidades TEXT, -- JSON array de unidade_ids atendidas
    ativo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### chamados_externos
```sql
CREATE TABLE chamados_externos (
    id INTEGER PRIMARY KEY,
    os_id INTEGER REFERENCES ordens_servico(id),
    terceirizado_id INTEGER REFERENCES terceirizados(id),
    descricao TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'aberto', -- 'aberto', 'em_atendimento', 'concluido'
    valor_orcado DECIMAL(10,2),
    valor_final DECIMAL(10,2),
    data_abertura DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_conclusao DATETIME,
    avaliacao INTEGER CHECK(avaliacao BETWEEN 1 AND 5),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### historico_notificacoes (ATUALIZAR - Campos novos ⭐)
```sql
CREATE TABLE historico_notificacoes (
    id INTEGER PRIMARY KEY,
    ⭐ megaapi_id VARCHAR(100) UNIQUE, -- ID da MegaAPI (deduplicação)
    remetente VARCHAR(20) NOT NULL, -- Número telefone
    destinatario VARCHAR(20) NOT NULL,
    mensagem TEXT,
    ⭐ tipo_conteudo VARCHAR(20) DEFAULT 'text', -- 'text', 'image', 'audio', 'document', 'location', 'interactive'
    ⭐ url_midia_local VARCHAR(255), -- Caminho local do arquivo baixado
    ⭐ mimetype VARCHAR(50), -- ex: audio/ogg, image/jpeg
    ⭐ caption TEXT, -- Legenda da mídia
    ⭐ mensagem_transcrita TEXT, -- Transcrição de áudio via Whisper
    status_envio VARCHAR(20) DEFAULT 'pendente', -- 'pendente', 'enviado', 'falha'
    ⭐ status_leitura VARCHAR(20), -- 'enviado', 'entregue', 'lido'
    tentativas INTEGER DEFAULT 0,
    direcao VARCHAR(10) NOT NULL, -- 'inbound', 'outbound'
    prioridade INTEGER DEFAULT 0,
    mensagem_hash VARCHAR(64), -- SHA256 para deduplicação
    os_id INTEGER REFERENCES ordens_servico(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_megaapi_id ON historico_notificacoes(megaapi_id);
CREATE INDEX idx_remetente ON historico_notificacoes(remetente);
```

#### regras_automacao
```sql
CREATE TABLE regras_automacao (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    condicao_tipo VARCHAR(20) NOT NULL, -- 'exata', 'contem', 'regex'
    condicao_valor TEXT NOT NULL,
    acao_tipo VARCHAR(50) NOT NULL, -- 'criar_os', 'enviar_mensagem', 'atribuir_tecnico'
    acao_parametros TEXT, -- JSON
    ativo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### estado_conversa
```sql
CREATE TABLE estado_conversa (
    id INTEGER PRIMARY KEY,
    telefone VARCHAR(20) UNIQUE NOT NULL,
    contexto TEXT, -- JSON com dados do fluxo
    ultimo_comando VARCHAR(50),
    expira_em DATETIME, -- 24h de inatividade
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### token_acesso
```sql
CREATE TABLE token_acesso (
    id INTEGER PRIMARY KEY,
    token VARCHAR(64) UNIQUE NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- 'aprovar_pedido', 'confirmar_os'
    recurso_id INTEGER NOT NULL, -- ID do pedido/OS
    expira_em DATETIME NOT NULL, -- 24-48h validade
    usado BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### metricas_whatsapp
```sql
CREATE TABLE metricas_whatsapp (
    id INTEGER PRIMARY KEY,
    periodo VARCHAR(20) NOT NULL, -- 'hora', 'dia'
    timestamp DATETIME NOT NULL,
    mensagens_enviadas INTEGER DEFAULT 0,
    mensagens_falhadas INTEGER DEFAULT 0,
    mensagens_recebidas INTEGER DEFAULT 0,
    tempo_resposta_medio_seg INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(periodo, timestamp)
);
```

### 3.2 Tabelas para Compras

#### fornecedores
```sql
CREATE TABLE fornecedores (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    cnpj VARCHAR(18) UNIQUE,
    email VARCHAR(100),
    telefone VARCHAR(20),
    whatsapp VARCHAR(20),
    endereco TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### catalogo_fornecedor
```sql
CREATE TABLE catalogo_fornecedor (
    id INTEGER PRIMARY KEY,
    fornecedor_id INTEGER REFERENCES fornecedores(id),
    estoque_id INTEGER REFERENCES estoque(id),
    preco DECIMAL(10,2) NOT NULL,
    prazo_entrega_dias INTEGER,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fornecedor_id, estoque_id)
);
```

#### pedidos_compra
```sql
CREATE TABLE pedidos_compra (
    id INTEGER PRIMARY KEY,
    numero_pedido VARCHAR(20) UNIQUE NOT NULL,
    fornecedor_id INTEGER REFERENCES fornecedores(id),
    os_id INTEGER REFERENCES ordens_servico(id),
    solicitante_id INTEGER REFERENCES usuarios(id),
    status VARCHAR(20) DEFAULT 'solicitado', -- 'solicitado', 'aprovado', 'rejeitado', 'pedido', 'entregue'
    valor_total DECIMAL(10,2),
    data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_aprovacao DATETIME,
    aprovador_id INTEGER REFERENCES usuarios(id),
    data_entrega DATETIME,
    unidade_destino_id INTEGER REFERENCES unidades(id), -- Onde será alocado
    observacoes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### itens_pedido
```sql
CREATE TABLE itens_pedido (
    id INTEGER PRIMARY KEY,
    pedido_id INTEGER REFERENCES pedidos_compra(id) ON DELETE CASCADE,
    estoque_id INTEGER REFERENCES estoque(id),
    quantidade INTEGER NOT NULL,
    preco_unitario DECIMAL(10,2),
    subtotal DECIMAL(10,2)
);
```

---

## 4. REQUISITOS FUNCIONAIS POR MÓDULO

### 4.1 MÓDULO COMUNICAÇÃO

#### 4.1.1 Webhook WhatsApp (MegaAPI)
**Endpoint**: `POST /webhook/whatsapp`

**Requisitos**:
- ✅ Validação HMAC SHA256 da assinatura
- ✅ Validação de timestamp (max 5 minutos)
- ✅ Deduplicação via `megaapi_id`
- ✅ Retornar 200 OK em < 500ms
- ✅ Processar assincronamente via Celery

**Fluxo**:
```python
1. Recebe POST da MegaAPI
2. Valida signature HMAC
3. Cria registro em historico_notificacoes (inbound)
4. Se tipo_conteudo in ['image', 'audio', 'document']:
   → Dispara baixar_midia_task.delay(notificacao_id, url_midia)
5. Dispara processar_mensagem_inbound.delay(notificacao_id)
6. Retorna 200 OK
```

**Campos recebidos** (JSON):
```json
{
  "id": "megaapi_msg_123",
  "from": "5511999999999",
  "timestamp": 1234567890,
  "type": "text|image|audio|document",
  "text": {"body": "mensagem"},
  "image": {"url": "https://...", "caption": "..."},
  "audio": {"url": "https://...", "mimetype": "audio/ogg"},
  "document": {"url": "https://...", "filename": "..."}
}
```

#### 4.1.2 Download de Mídias
**Task Celery**: `baixar_midia_task(notificacao_id, url_midia_megaapi, tipo_conteudo)`

**Requisitos**:
- Timeout: 30 segundos
- Retry: 3 tentativas (backoff exponencial: 1min, 5min, 25min)
- Max tamanho: 10MB
- Formatos suportados: .jpg, .png, .pdf, .ogg, .mp3, .wav
- Path de salvamento: `/static/uploads/whatsapp/{ano}/{mes}/{uuid}_{filename}`

**Fluxo**:
```python
1. GET na url_midia_megaapi (Bearer token)
2. Valida tamanho (< 10MB)
3. Salva no disco
4. Atualiza historico_notificacoes.url_midia_local
5. Se tipo_conteudo == 'audio':
   → Dispara transcrever_audio_task.delay(notificacao_id)
```

#### 4.1.3 Transcrição de Áudio (NLP)
**Task Celery**: `transcrever_audio_task(notificacao_id)`

**Requisitos**:
- API: OpenAI Whisper (`whisper-1`)
- Idioma: `pt-BR`
- Timeout: 60 segundos
- Retry: 3 tentativas
- Confiança mínima: 70% (senão marca "requer_revisao")

**Fluxo**:
```python
1. Carrega áudio de url_midia_local
2. Envia para Whisper API (openai.Audio.transcribe)
3. Recebe transcrição + confidence
4. Se confidence >= 70%:
   → Salva em mensagem_transcrita
   → Chama processar_nlp_keywords(notificacao_id)
5. Senão:
   → Marca flag requer_revisao_manual
```

**Custos**: ~$0.006/min (~R$0.03/min)

#### 4.1.4 Roteamento de Mensagens
**Service**: `RoteamentoService.processar_mensagem(notificacao_id)`

**Lógica**:
```python
1. Identifica remetente (Terceirizado ou Usuario)
2. Busca estado_conversa ativo (< 24h)
3. Se tem estado:
   → Continua fluxo (ex: aguardando foto da OS)
4. Se mensagem começa com '#':
   → ComandoParser.extrair_comando(mensagem)
   → ComandoExecutor.executar(comando, params)
5. Se mensagem começa com 'EQUIP:':
   → Contextualiza no equipamento
   → Envia menu interativo
6. Senão:
   → Busca em RegrasAutomacao (match por regex)
   → Se nenhuma regra: Encaminha para gerente
```

#### 4.1.5 Comandos Suportados
| Comando | Exemplo | Ação |
|---------|---------|------|
| `#COMPRA` | `#COMPRA ROL001 5` | Solicita pedido de compra (código + qtd) |
| `#STATUS` | `#STATUS` | Lista OSs do técnico (aberta, em_andamento) |
| `#AJUDA` | `#AJUDA` | Envia menu interativo |
| `EQUIP:{id}` | `EQUIP:127` | Contextualiza no equipamento (via QR Code) |

#### 4.1.6 Menus Interativos (List Messages)
**Service**: `WhatsAppService.send_list_message(phone, header, body, sections)`

**Payload MegaAPI**:
```json
{
  "to": "5511999999999",
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {"type": "text", "text": "Menu Principal"},
    "body": {"text": "Escolha uma opção:"},
    "action": {
      "button": "Ver Opções",
      "sections": [
        {
          "title": "Ordens de Serviço",
          "rows": [
            {"id": "minhas_os", "title": "Minhas OSs"},
            {"id": "abrir_os", "title": "Abrir Chamado"}
          ]
        },
        {
          "title": "Estoque",
          "rows": [
            {"id": "solicitar_peca", "title": "Solicitar Peça"},
            {"id": "consultar_estoque", "title": "Consultar Estoque"}
          ]
        }
      ]
    }
  }
}
```

**Processamento da Resposta**:
- Webhook recebe `message.type == 'interactive'`
- Extrai `message.interactive.list_reply.id`
- Roteia para handler específico (ex: `minhas_os` → listar OSs do técnico)

#### 4.1.7 Botões Interativos (Approvals)
**Service**: `WhatsAppService.send_buttons_message(phone, body, buttons)`

**Payload MegaAPI**:
```json
{
  "to": "5511999999999",
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {"text": "Aprovar compra de Motor WEG (R$ 1.200)?"},
    "action": {
      "buttons": [
        {"type": "reply", "reply": {"id": "aprovar_123", "title": "✅ Aprovar"}},
        {"type": "reply", "reply": {"id": "rejeitar_123", "title": "❌ Rejeitar"}}
      ]
    }
  }
}
```

**Casos de Uso**:
1. Aprovação de pedido de compra (> R$ 500)
2. Aceitar/rejeitar OS atribuída
3. Confirmar recebimento de material

#### 4.1.8 Central de Mensagens (Chat UI)
**Rota**: `GET /admin/chat`

**Requisitos**:
- Carregamento inicial: < 2 segundos (últimas 50 mensagens)
- Paginação: 50 msgs/página (scroll infinito)
- Filtros: Por remetente, período, tipo_conteudo
- Indicadores de status: ⏱️ Pendente, ✓ Enviado, ✓✓ Lido

**Funcionalidades**:
- Enviar mensagem (texto + anexo)
- Gravar áudio no navegador (MediaRecorder API)
- Player HTML5 para áudios
- Lightbox para imagens
- Download de PDFs

**Template**: `admin/chat_central.html`

---

### 4.2 MÓDULO MANUTENÇÃO (OS)

#### 4.2.1 Criação de OS
**Origens**:
1. **Web** (`origem_criacao='web'`): Formulário padrão
2. **WhatsApp Bot** (`origem_criacao='whatsapp_bot'`): Via NLP ou menu interativo
3. **QR Code** (`origem_criacao='qr_code'`): Escaneia etiqueta do equipamento

**Campos Obrigatórios**:
- `equipamento_id`
- `unidade_id`
- `titulo`
- `prioridade`

**Validações**:
- Equipamento deve estar ativo
- Se via WhatsApp: Remetente deve ser técnico ou terceirizado

#### 4.2.2 Check-in/Check-out
**Fluxo**:
```
1. Técnico inicia OS (via WhatsApp ou web)
   → Atualiza status='em_andamento', data_inicio=NOW()
2. Técnico pausa OS
   → Calcula tempo_execucao_minutos += (NOW() - data_inicio)
   → Atualiza status='pausada'
3. Técnico finaliza OS
   → Calcula tempo_execucao_minutos final
   → Exige foto (AnexosOS.tipo='photo_depois')
   → Atualiza status='concluida', data_finalizacao=NOW()
```

**Via WhatsApp**:
- Envia botões: `[▶️ Iniciar] [⏸️ Pausar] [✅ Finalizar]`
- Resposta interativa atualiza OS

#### 4.2.3 Consumo de Peças
**Fluxo**:
```
1. Técnico seleciona peça do estoque
2. Sistema verifica saldo na unidade da OS
3. Se saldo >= quantidade:
   → Cria MovimentacaoEstoque (tipo='saida', unidade_id=OS.unidade_id)
   → Atualiza EstoqueSaldo.quantidade
   → Grava custo_momento (preço atual da peça)
4. Senão:
   → Sugere transferência de outra unidade OU
   → Cria PedidoCompra automaticamente
```

#### 4.2.4 Anexos de OS
**Tabela**: `anexos_os`
```sql
CREATE TABLE anexos_os (
    id INTEGER PRIMARY KEY,
    os_id INTEGER REFERENCES ordens_servico(id) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL, -- 'photo_antes', 'photo_depois', 'documento'
    caminho VARCHAR(255) NOT NULL,
    descricao TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Requisitos**:
- Photo antes: Opcional
- Photo depois: Obrigatória (finalização de OS)
- Tamanho max: 10MB
- Formatos: .jpg, .png, .pdf

#### 4.2.5 SLA Dinâmico
**Cálculo**:
```python
def calcular_sla(prioridade, tipo_servico):
    sla_base = {
        'urgente': 4,    # 4 horas
        'alta': 24,      # 1 dia
        'media': 72,     # 3 dias
        'baixa': 168     # 7 dias
    }

    horas = sla_base.get(prioridade, 72)

    # Terceirizados têm 50% a mais de tempo
    if tipo_servico == 'terceirizado':
        horas *= 1.5

    return datetime.now() + timedelta(hours=horas)
```

#### 4.2.6 Alertas Preditivos
**Task Celery**: `detectar_anomalias_equipamentos()` (diário, 03:00)

**Lógica**:
```python
SELECT equipamento_id, COUNT(*) as total_os
FROM ordens_servico
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY equipamento_id
HAVING total_os > 3
```

**Ação**:
- Envia WhatsApp para gerente:
  > "⚠️ Atenção: Equipamento **Esteira 3** teve **5 OSs** nos últimos 30 dias. Considere revisão profunda ou substituição."

---

### 4.3 MÓDULO ESTOQUE

#### 4.3.1 Controle Multi-Unidade
**Conceito**: Cada peça tem um saldo **global** (tabela `estoque`) e saldos **locais** por unidade (tabela `estoque_saldo`).

**Regras**:
- `estoque.quantidade_global` = SUM(`estoque_saldo.quantidade`)
- Toda movimentação DEVE especificar `unidade_id`
- Consumo tenta unidade local primeiro

#### 4.3.2 Transferências Entre Unidades
**Fluxo**:
```
1. Técnico solicita transferência (via web ou WhatsApp)
   → Cria SolicitacaoTransferencia (status='solicitado')
2. Gerente da unidade origem aprova
   → MovimentacaoEstoque (tipo='saida', unidade_origem)
   → MovimentacaoEstoque (tipo='entrada', unidade_destino)
   → Atualiza EstoqueSaldo de ambas
   → Notifica solicitante via WhatsApp
```

#### 4.3.3 Alertas de Estoque Crítico
**Task Celery**: `verificar_estoque_critico()` (diário, 08:00)

**Lógica**:
```python
SELECT e.id, e.descricao, es.unidade_id, es.quantidade, e.quantidade_minima
FROM estoque e
JOIN estoque_saldo es ON e.id = es.estoque_id
WHERE es.quantidade < e.quantidade_minima
```

**Ação**:
- Envia WhatsApp para comprador:
  > "🟡 Estoque crítico: **Rolamento 608ZZ** na unidade **Centro**: 2 unidades (mínimo: 5)"

---

### 4.4 MÓDULO COMPRAS

#### 4.4.1 Fluxo "One-Tap Approval"
```
┌─────────────────────────────────────────┐
│ 1. Técnico solicita peça via WhatsApp  │
│    "#COMPRA ROL001 5"                   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│ 2. Sistema cria PedidoCompra            │
│    status='solicitado'                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│ 3. Comprador recebe notificação         │
│    "Nova solicitação: 5x Rolamento..."  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│ 4. Comprador insere cotações (web)      │
│    Atualiza valor_total                 │
└──────────────┬──────────────────────────┘
               │
               ├─── Valor <= R$ 500 ───────┐
               │   → Aprova automaticamente│
               │   → status='aprovado'      │
               │                            │
               └─── Valor > R$ 500 ────────┤
                   ┌──────────────▼─────────▼──┐
                   │ 5. Gerente recebe botões  │
                   │    [✅ Aprovar] [❌ Rejeitar] │
                   └──────────────┬──────────────┘
                                  │
                   ┌──────────────▼──────────────┐
                   │ 6. Ação reflete no sistema  │
                   │    status='aprovado'        │
                   └──────────────┬──────────────┘
                                  │
                   ┌──────────────▼──────────────┐
                   │ 7. PDF gerado e enviado     │
                   │    para fornecedor          │
                   └─────────────────────────────┘
```

#### 4.4.2 Geração de PDF
**Service**: `PDFGeneratorService.gerar_pdf_pedido(pedido_id)`

**Requisitos**:
- Template: HTML + CSS (renderizado com WeasyPrint)
- Conteúdo: Logo, dados fornecedor, itens, valor total, condições
- Path: `/static/uploads/pedidos/PEDIDO_{numero_pedido}.pdf`

**Task**: `enviar_pedido_fornecedor.delay(pedido_id)` (após aprovação)

#### 4.4.3 Recebimento com Alocação
**Rota**: `POST /compras/pedido/<id>/marcar-entregue`

**Campos obrigatórios**:
- `unidade_destino_id` (select dropdown)
- `data_entrega`

**Fluxo**:
```python
1. Valida unidade_destino_id
2. Para cada item do pedido:
   → Cria MovimentacaoEstoque (tipo='entrada', unidade_id=destino)
   → Atualiza EstoqueSaldo.quantidade
   → Grava custo_momento = item.preco_unitario
3. Atualiza PedidoCompra.status='entregue'
4. Notifica solicitante via WhatsApp
```

---

### 4.5 MÓDULO ANALYTICS

#### 4.5.1 KPIs Principais
| Métrica | Fórmula | Visualização |
|---------|---------|--------------|
| **MTTR** | AVG(data_finalizacao - data_abertura) | Gráfico linha (mensal) |
| **Taxa Conclusão** | COUNT(concluídas) / COUNT(total) * 100 | Gauge (%) |
| **TCO** | custo_aquisicao + SUM(peças_consumidas) | Tabela por equipamento |
| **OSs por Status** | GROUP BY status | Gráfico pizza |
| **Custo Manutenção** | SUM(custo_momento * quantidade) | Gráfico barra (por mês) |

#### 4.5.2 Endpoints JSON (para Chart.js)
```python
GET /analytics/api/mttr
→ [{"mes": "2026-01", "mttr_horas": 12.5}, ...]

GET /analytics/api/os-por-status
→ {"aberta": 15, "em_andamento": 8, "concluida": 142}

GET /analytics/api/custo-equipamento/<id>
→ {"aquisicao": 5000.00, "manutencao": 1234.56, "tco": 6234.56}
```

#### 4.5.3 Morning Briefing
**Task Celery**: `enviar_morning_briefing()` (08:00, segunda a sexta)

**Conteúdo**:
```python
# OSs atrasadas (data_prevista < hoje)
os_atrasadas = OrdemServico.query.filter(
    OrdemServico.status.in_(['aberta', 'em_andamento']),
    OrdemServico.data_prevista < date.today()
).count()

# Estoque crítico
estoque_critico = db.session.query(
    Estoque, EstoqueSaldo
).join(EstoqueSaldo).filter(
    EstoqueSaldo.quantidade < Estoque.quantidade_minima
).count()

# Taxa de conclusão ontem
os_ontem = OrdemServico.query.filter(
    func.date(OrdemServico.created_at) == date.today() - timedelta(days=1)
).count()
os_concluidas_ontem = OrdemServico.query.filter(
    func.date(OrdemServico.data_finalizacao) == date.today() - timedelta(days=1)
).count()
taxa = (os_concluidas_ontem / os_ontem * 100) if os_ontem > 0 else 0

mensagem = f"""
Bom dia! 🌤️ *Status Hoje:*

🔴 {os_atrasadas} OSs Atrasadas
🟡 {estoque_critico} Peças com Estoque Crítico
🟢 {taxa:.1f}% das OSs ontem foram concluídas
"""

WhatsAppService.enviar_mensagem(gerente.telefone, mensagem)
```

---

### 4.6 MÓDULO QR CODE

#### 4.6.1 Geração de Etiquetas
**Service**: `QRCodeService.gerar_etiqueta(equipamento_id)`

**Especificações**:
- **URL**: `https://wa.me/5511999999999?text=EQUIP:{equipamento_id}`
- **Tamanho QR**: 300x300px
- **Error Correction**: Level M (15%)
- **Biblioteca**: `qrcode` + `PIL`

**Layout da Etiqueta** (5x5cm):
```
┌─────────────────────────┐
│   [LOGO DA EMPRESA]     │
│                         │
│   ███████████████       │
│   ████ QR ███████       │ ← QR Code (3x3cm)
│   ███████████████       │
│                         │
│ Nome: Esteira 3         │
│ Código: EQ-127          │
└─────────────────────────┘
```

**Código**:
```python
import qrcode
from PIL import Image, ImageDraw, ImageFont

def gerar_etiqueta(equipamento_id):
    equipamento = Equipamento.query.get(equipamento_id)
    url = f"https://wa.me/5511999999999?text=EQUIP:{equipamento_id}"

    # Gerar QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Criar etiqueta completa (5x5cm = ~590x590px @ 300dpi)
    etiqueta = Image.new('RGB', (590, 590), 'white')

    # Colar QR Code (centralizado)
    qr_img = qr_img.resize((350, 350))
    etiqueta.paste(qr_img, (120, 80))

    # Adicionar textos
    draw = ImageDraw.Draw(etiqueta)
    font = ImageFont.truetype("arial.ttf", 24)
    draw.text((50, 450), f"Nome: {equipamento.nome}", fill='black', font=font)
    draw.text((50, 490), f"Código: {equipamento.codigo}", fill='black', font=font)

    # Salvar
    path = f"/static/uploads/qr/{equipamento_id}.png"
    etiqueta.save(path)
    return path
```

#### 4.6.2 Impressão em Massa
**Rota**: `GET /equipamentos/gerar-etiquetas-pdf`

**Requisitos**:
- Grid 4x4 (16 etiquetas por página A4)
- Formato PDF
- Margem: 1cm
- Espaçamento: 0.5cm entre etiquetas

**Biblioteca**: `reportlab` ou `WeasyPrint`

---

## 5. REQUISITOS NÃO-FUNCIONAIS

### 5.1 SLAs Técnicos

#### Performance
| Operação | SLA | Métrica |
|----------|-----|---------|
| Webhook response | < 500ms | 95th percentile |
| Download de mídia | < 30s | Timeout absoluto |
| Central de Mensagens | < 2s | Carregamento inicial |
| API JSON | < 1s | Queries simples |

#### Confiabilidade
- **Taxa de sucesso de envio**: > 95% (medida semanal)
- **Uptime**: 99.5% (permitido ~3.6h downtime/mês)
- **Taxa de perda de mensagens**: 0% (princípio Zero-Loss)

#### Escalabilidade
- **Mensagens/dia**: 1.000 (30k/mês)
- **Usuários simultâneos**: 100 na Central de Mensagens
- **Registros em historico_notificacoes**: > 500k sem degradação

### 5.2 Segurança

#### Autenticação
- **Senha**: Bcrypt (cost=12)
- **Sessão**: Flask-Login com cookie HTTPOnly + Secure
- **Timeout**: 4 horas de inatividade

#### Webhook
- **HMAC SHA256**: Validação obrigatória
- **Timestamp**: Max 5 minutos de diferença
- **IP Whitelist**: Somente IPs da MegaAPI

#### API Keys
- **Armazenamento**: Fernet encryption (symmetric)
- **Rotação**: A cada 90 dias (aviso com 15 dias de antecedência)

### 5.3 Resiliência & Fallback

#### Circuit Breaker (MegaAPI)
```python
Estado: CLOSED | OPEN | HALF_OPEN
Threshold: 5 falhas consecutivas → OPEN
Recovery: 10 minutos → tenta HALF_OPEN
Durante OPEN: Mensagens enfileiradas para retry
```

#### Protocolo de Fallback
1. **WhatsApp (MegaAPI)** - Canal primário
2. **Email (SMTP)** - Após 3 falhas consecutivas
3. **SMS (Twilio/AWS SNS)** - Apenas alertas críticos
4. **Push Notification** - Se disponível

**Critérios de Ativação**:
- WhatsApp indisponível > 15 minutos
- Taxa de falha > 50% em 1 hora
- Circuit Breaker OPEN > 30 minutos

### 5.4 Backup & Disaster Recovery

#### Backup Incremental (Diário)
```bash
# Cron: 02:00 todos os dias
rsync -av --link-dest=../backup-anterior \
  /static/uploads/ \
  /backup/gmm-uploads-$(date +%Y%m%d)/
```

#### Backup Completo (Semanal)
```bash
# Cron: 03:00 domingo
pg_dump -Fc gmm_db > /backup/gmm-db-$(date +%Y%m%d).dump
tar -czf /backup/gmm-uploads-$(date +%Y%m%d).tar.gz /static/uploads/
```

**Retenção**: 90 dias (depois move para S3 Glacier)

#### Recovery Time Objective (RTO)
- **Falha de servidor**: < 4 horas
- **Perda de banco de dados**: < 2 horas (restore do backup)

---

## 6. ROADMAP DE IMPLEMENTAÇÃO

### 🚀 FASE 1: Fundação & Schema (Semana 1)

#### 1.1 Migration Database
**Arquivo**: `migrations/versions/xxxx_add_campos_v3_1.py`

```python
def upgrade():
    # historico_notificacoes
    op.add_column('historico_notificacoes', sa.Column('megaapi_id', sa.String(100), unique=True))
    op.add_column('historico_notificacoes', sa.Column('tipo_conteudo', sa.String(20), default='text'))
    op.add_column('historico_notificacoes', sa.Column('url_midia_local', sa.String(255)))
    op.add_column('historico_notificacoes', sa.Column('mimetype', sa.String(50)))
    op.add_column('historico_notificacoes', sa.Column('caption', sa.Text))
    op.add_column('historico_notificacoes', sa.Column('mensagem_transcrita', sa.Text))
    op.add_column('historico_notificacoes', sa.Column('status_leitura', sa.String(20)))
    op.create_index('idx_megaapi_id', 'historico_notificacoes', ['megaapi_id'])

    # ordens_servico
    op.add_column('ordens_servico', sa.Column('tempo_execucao_minutos', sa.Integer))
    op.add_column('ordens_servico', sa.Column('origem_criacao', sa.String(20), default='web'))
    op.add_column('ordens_servico', sa.Column('avaliacao', sa.Integer))

    # movimentacoes_estoque
    op.add_column('movimentacoes_estoque', sa.Column('custo_momento', sa.Numeric(10, 2)))
```

**Comando**:
```bash
flask db migrate -m "Add v3.1 fields"
flask db upgrade
```

#### 1.2 Media Downloader Service
**Arquivo**: `app/services/media_downloader_service.py`

```python
import requests
import os
from datetime import datetime
from uuid import uuid4

class MediaDownloaderService:
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    TIMEOUT = 30

    @staticmethod
    def download(url_megaapi, tipo_conteudo, bearer_token):
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
                raise ValueError(f"Arquivo muito grande: {content_length} bytes")

            # Define caminho
            now = datetime.now()
            ano = now.strftime('%Y')
            mes = now.strftime('%m')
            ext = MediaDownloaderService._get_extension(tipo_conteudo, response.headers.get('Content-Type'))
            filename = f"{uuid4()}{ext}"

            directory = f"/static/uploads/whatsapp/{ano}/{mes}"
            os.makedirs(directory, exist_ok=True)

            filepath = f"{directory}/{filename}"

            # Salva arquivo
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return filepath

        except Exception as e:
            raise Exception(f"Erro ao baixar mídia: {str(e)}")

    @staticmethod
    def _get_extension(tipo_conteudo, mimetype):
        extensions = {
            'image': '.jpg',
            'audio': '.ogg',
            'document': '.pdf'
        }
        return extensions.get(tipo_conteudo, '.bin')
```

#### 1.3 Task Celery: Baixar Mídia
**Arquivo**: `app/tasks/whatsapp_tasks.py`

```python
from app.tasks import celery
from app.services.media_downloader_service import MediaDownloaderService
from app.models import HistoricoNotificacao, db

@celery.task(bind=True, max_retries=3)
def baixar_midia_task(self, notificacao_id, url_megaapi, tipo_conteudo):
    try:
        # Busca configuração
        config = ConfiguracaoWhatsApp.query.first()
        bearer_token = config.api_key_decrypted

        # Download
        filepath = MediaDownloaderService.download(url_megaapi, tipo_conteudo, bearer_token)

        # Atualiza banco
        notificacao = HistoricoNotificacao.query.get(notificacao_id)
        notificacao.url_midia_local = filepath
        db.session.commit()

        # Se for áudio, dispara transcrição
        if tipo_conteudo == 'audio':
            transcrever_audio_task.delay(notificacao_id)

    except Exception as exc:
        # Retry com backoff: 1min, 5min, 25min
        raise self.retry(exc=exc, countdown=60 * (5 ** self.request.retries))
```

#### 1.4 Atualização do Webhook
**Arquivo**: `app/routes/webhook.py`

```python
@webhook_bp.route('/whatsapp', methods=['POST'])
def webhook_whatsapp():
    # ... validação HMAC ...

    data = request.json

    # Cria notificação
    notificacao = HistoricoNotificacao(
        megaapi_id=data.get('id'),
        remetente=data['from'],
        destinatario=current_app.config['WHATSAPP_NUMBER'],
        tipo_conteudo=data.get('type', 'text'),
        mensagem=data.get('text', {}).get('body'),
        direcao='inbound',
        status_envio='enviado'
    )

    # Se tem mídia, extrai dados
    if data['type'] in ['image', 'audio', 'document']:
        media_data = data[data['type']]
        notificacao.caption = media_data.get('caption')
        notificacao.mimetype = media_data.get('mimetype')

        # Dispara download assíncrono
        baixar_midia_task.delay(
            notificacao.id,
            media_data['url'],
            data['type']
        )

    db.session.add(notificacao)
    db.session.commit()

    # Processa mensagem
    processar_mensagem_inbound.delay(notificacao.id)

    return jsonify({'status': 'ok'}), 200
```

**Checklist Fase 1**:
- [ ] Migration executada sem erros
- [ ] MediaDownloaderService testado (mock da MegaAPI)
- [ ] Task baixar_midia_task testada com retry
- [ ] Webhook atualizado e validado
- [ ] 100% das mensagens inbound salvas no banco

---

### 🤖 FASE 2: Automação Básica (Semana 2)

#### 2.1 List Messages (Menus Interativos)
**Arquivo**: `app/services/whatsapp_service.py`

```python
class WhatsAppService:
    # ... código existente ...

    @staticmethod
    def send_list_message(phone, header, body, sections):
        payload = {
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "button": "Ver Opções",
                    "sections": sections
                }
            }
        }

        return WhatsAppService._send_request(payload)

    @staticmethod
    def send_buttons_message(phone, body, buttons):
        # Max 3 botões
        if len(buttons) > 3:
            raise ValueError("Máximo de 3 botões permitido")

        payload = {
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": buttons}
            }
        }

        return WhatsAppService._send_request(payload)
```

#### 2.2 Processamento de Respostas Interativas
**Arquivo**: `app/services/roteamento_service.py`

```python
class RoteamentoService:
    # ... código existente ...

    @staticmethod
    def processar_resposta_interativa(notificacao):
        # Extrai ID da resposta
        # Exemplo: "minhas_os", "solicitar_peca_123"
        resposta_id = notificacao.mensagem  # Vem do webhook

        if resposta_id == 'minhas_os':
            return RoteamentoService._listar_minhas_os(notificacao.remetente)

        elif resposta_id == 'solicitar_peca':
            return RoteamentoService._iniciar_fluxo_solicitacao_peca(notificacao.remetente)

        elif resposta_id.startswith('aprovar_'):
            pedido_id = int(resposta_id.split('_')[1])
            return RoteamentoService._aprovar_pedido(pedido_id, notificacao.remetente)

        # ... outros handlers ...

    @staticmethod
    def _listar_minhas_os(telefone):
        tecnico = Terceirizado.query.filter_by(telefone=telefone).first()
        oss = OrdemServico.query.filter_by(
            tecnico_id=tecnico.id,
            status__in=['aberta', 'em_andamento']
        ).all()

        mensagem = f"Você tem {len(oss)} OSs abertas:\n\n"
        for os in oss:
            mensagem += f"#{os.numero_os} - {os.titulo} ({os.prioridade})\n"

        WhatsAppService.enviar_mensagem(telefone, mensagem)
```

#### 2.3 Central de Mensagens (UI)
**Arquivo**: `app/templates/admin/chat_central.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <!-- Sidebar: Lista de conversas -->
        <div class="col-md-3 border-right">
            <h5>Conversas</h5>
            <div id="lista-conversas">
                {% for conversa in conversas %}
                <div class="conversa-item" data-telefone="{{ conversa.telefone }}">
                    <strong>{{ conversa.nome }}</strong>
                    <small>{{ conversa.ultima_mensagem_tempo }}</small>
                    <p class="text-muted">{{ conversa.ultima_mensagem[:50] }}</p>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Área de chat -->
        <div class="col-md-9">
            <div id="chat-header">
                <h4 id="chat-nome">Selecione uma conversa</h4>
            </div>

            <div id="chat-mensagens" style="height: 500px; overflow-y: scroll;">
                <!-- Mensagens carregadas via AJAX -->
            </div>

            <div id="chat-input">
                <form id="form-enviar-mensagem">
                    <div class="input-group">
                        <input type="text" class="form-control" id="input-mensagem" placeholder="Digite uma mensagem...">
                        <button type="button" id="btn-anexo" class="btn btn-secondary">📎</button>
                        <button type="button" id="btn-audio" class="btn btn-secondary">🎤</button>
                        <button type="submit" class="btn btn-primary">Enviar</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

<script>
// Carregar mensagens via AJAX
function carregarMensagens(telefone) {
    fetch(`/admin/chat/mensagens/${telefone}`)
        .then(res => res.json())
        .then(mensagens => {
            const container = document.getElementById('chat-mensagens');
            container.innerHTML = '';

            mensagens.forEach(msg => {
                const div = document.createElement('div');
                div.className = msg.direcao === 'outbound' ? 'mensagem-enviada' : 'mensagem-recebida';

                // Renderiza texto
                if (msg.tipo_conteudo === 'text') {
                    div.innerHTML = `<p>${msg.mensagem}</p>`;
                }

                // Renderiza áudio
                else if (msg.tipo_conteudo === 'audio') {
                    div.innerHTML = `
                        <audio controls>
                            <source src="${msg.url_midia_local}" type="${msg.mimetype}">
                        </audio>
                        ${msg.mensagem_transcrita ? `<p><em>${msg.mensagem_transcrita}</em></p>` : ''}
                    `;
                }

                // Renderiza imagem
                else if (msg.tipo_conteudo === 'image') {
                    div.innerHTML = `
                        <img src="${msg.url_midia_local}" class="img-fluid" style="max-width: 300px;">
                        ${msg.caption ? `<p>${msg.caption}</p>` : ''}
                    `;
                }

                // Indicador de status
                const status = msg.status_leitura === 'lido' ? '✓✓' : (msg.status_leitura === 'entregue' ? '✓' : '⏱️');
                div.innerHTML += `<small class="text-muted">${msg.created_at} ${status}</small>`;

                container.appendChild(div);
            });

            // Scroll para última mensagem
            container.scrollTop = container.scrollHeight;
        });
}

// Event listeners
document.querySelectorAll('.conversa-item').forEach(item => {
    item.addEventListener('click', () => {
        const telefone = item.dataset.telefone;
        carregarMensagens(telefone);
    });
});
</script>
{% endblock %}
```

**Checklist Fase 2**:
- [ ] List messages enviadas com sucesso
- [ ] Respostas interativas processadas corretamente
- [ ] Central de mensagens carrega em < 2s
- [ ] Player de áudio funcional
- [ ] Lightbox de imagens implementado

---

### 📦 FASE 3: Compras & Fluxos Complexos (Semana 3)

#### 3.1 Comando #COMPRA
**Arquivo**: `app/services/comando_executores.py`

```python
class ComandoExecutores:
    # ... código existente ...

    @staticmethod
    def executar_compra(params, remetente):
        # Formato: #COMPRA ROL001 5
        try:
            codigo_peca, quantidade = params.split()
            quantidade = int(quantidade)
        except:
            return "❌ Formato inválido. Use: #COMPRA <CODIGO> <QTD>"

        # Busca peça
        peca = Estoque.query.filter_by(codigo=codigo_peca).first()
        if not peca:
            return f"❌ Peça {codigo_peca} não encontrada"

        # Identifica solicitante
        tecnico = Terceirizado.query.filter_by(telefone=remetente).first()
        if not tecnico:
            return "❌ Usuário não autorizado"

        # Cria pedido
        pedido = PedidoCompra(
            numero_pedido=f"PC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            solicitante_id=tecnico.id,
            status='solicitado'
        )
        db.session.add(pedido)
        db.session.flush()

        # Cria item
        item = ItemPedido(
            pedido_id=pedido.id,
            estoque_id=peca.id,
            quantidade=quantidade,
            preco_unitario=peca.preco_medio
        )
        pedido.valor_total = item.preco_unitario * quantidade
        db.session.add(item)
        db.session.commit()

        # Notifica comprador
        comprador = Usuario.query.filter_by(tipo='comprador').first()
        WhatsAppService.enviar_mensagem(
            comprador.telefone,
            f"🛒 Nova solicitação: {quantidade}x {peca.descricao}\nPedido: {pedido.numero_pedido}"
        )

        return f"✅ Pedido {pedido.numero_pedido} criado com sucesso!"
```

#### 3.2 Aprovação One-Tap
**Arquivo**: `app/routes/whatsapp.py`

```python
@whatsapp_bp.route('/aprovar/<token>', methods=['GET'])
def aprovar_pedido(token):
    # Valida token
    token_obj = TokenAcesso.query.filter_by(token=token, usado=False).first()

    if not token_obj or token_obj.expira_em < datetime.now():
        return render_template('whatsapp/erro.html', mensagem="Token inválido ou expirado")

    # Busca pedido
    pedido = PedidoCompra.query.get(token_obj.recurso_id)

    # Atualiza status
    pedido.status = 'aprovado'
    pedido.data_aprovacao = datetime.now()
    pedido.aprovador_id = token_obj.criado_por_id

    token_obj.usado = True
    db.session.commit()

    # Notifica solicitante
    WhatsAppService.enviar_mensagem(
        pedido.solicitante.telefone,
        f"✅ Seu pedido {pedido.numero_pedido} foi aprovado!"
    )

    # Dispara envio de PDF para fornecedor
    enviar_pedido_fornecedor.delay(pedido.id)

    return render_template('whatsapp/confirmacao.html', pedido=pedido)
```

**Geração de Token** (ao criar pedido > R$ 500):
```python
import secrets

def criar_token_aprovacao(pedido_id, gerente_id):
    token = secrets.token_urlsafe(32)

    token_obj = TokenAcesso(
        token=token,
        tipo='aprovar_pedido',
        recurso_id=pedido_id,
        criado_por_id=gerente_id,
        expira_em=datetime.now() + timedelta(hours=24)
    )
    db.session.add(token_obj)
    db.session.commit()

    # Envia botões para gerente
    url_aprovar = f"https://gmm.com/whatsapp/aprovar/{token}"
    url_rejeitar = f"https://gmm.com/whatsapp/rejeitar/{token}"

    WhatsAppService.send_buttons_message(
        gerente.telefone,
        f"Aprovar compra de {pedido.descricao} (R$ {pedido.valor_total})?",
        [
            {"type": "reply", "reply": {"id": f"aprovar_{pedido.id}", "title": "✅ Aprovar"}},
            {"type": "reply", "reply": {"id": f"rejeitar_{pedido.id}", "title": "❌ Rejeitar"}}
        ]
    )
```

#### 3.3 Geração de PDF
**Arquivo**: `app/services/pdf_generator_service.py`

```python
from weasyprint import HTML
from jinja2 import Template

class PDFGeneratorService:
    @staticmethod
    def gerar_pdf_pedido(pedido_id):
        pedido = PedidoCompra.query.get(pedido_id)

        # Template HTML
        template_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial; }
                .header { text-align: center; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; }
                th, td { border: 1px solid #ddd; padding: 8px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>PEDIDO DE COMPRA</h1>
                <p>Número: {{ pedido.numero_pedido }}</p>
            </div>

            <h3>Fornecedor</h3>
            <p>{{ pedido.fornecedor.nome }}<br>
               {{ pedido.fornecedor.endereco }}</p>

            <h3>Itens</h3>
            <table>
                <tr>
                    <th>Código</th>
                    <th>Descrição</th>
                    <th>Quantidade</th>
                    <th>Preço Unit.</th>
                    <th>Subtotal</th>
                </tr>
                {% for item in pedido.itens %}
                <tr>
                    <td>{{ item.estoque.codigo }}</td>
                    <td>{{ item.estoque.descricao }}</td>
                    <td>{{ item.quantidade }}</td>
                    <td>R$ {{ "%.2f"|format(item.preco_unitario) }}</td>
                    <td>R$ {{ "%.2f"|format(item.subtotal) }}</td>
                </tr>
                {% endfor %}
                <tr>
                    <td colspan="4" style="text-align: right;"><strong>TOTAL</strong></td>
                    <td><strong>R$ {{ "%.2f"|format(pedido.valor_total) }}</strong></td>
                </tr>
            </table>
        </body>
        </html>
        """

        template = Template(template_html)
        html_content = template.render(pedido=pedido)

        # Gera PDF
        filename = f"PEDIDO_{pedido.numero_pedido}.pdf"
        filepath = f"/static/uploads/pedidos/{filename}"
        HTML(string=html_content).write_pdf(filepath)

        return filepath
```

**Task**: `enviar_pedido_fornecedor.delay(pedido_id)`
```python
@celery.task
def enviar_pedido_fornecedor(pedido_id):
    pedido = PedidoCompra.query.get(pedido_id)

    # Gera PDF
    pdf_path = PDFGeneratorService.gerar_pdf_pedido(pedido_id)

    # Envia via WhatsApp (se fornecedor tem whatsapp)
    if pedido.fornecedor.whatsapp:
        WhatsAppService.enviar_documento(
            pedido.fornecedor.whatsapp,
            pdf_path,
            f"Pedido de Compra {pedido.numero_pedido}"
        )

    # Envia via Email (sempre)
    send_email(
        to=pedido.fornecedor.email,
        subject=f"Pedido de Compra {pedido.numero_pedido}",
        body="Segue em anexo o pedido de compra.",
        attachments=[pdf_path]
    )
```

**Checklist Fase 3**:
- [ ] Comando #COMPRA funcional
- [ ] Tokens de aprovação gerados corretamente
- [ ] Aprovação one-tap atualiza status
- [ ] PDF gerado com layout correto
- [ ] Envio para fornecedor (WhatsApp + Email)

---

### 🧠 FASE 4: Inteligência & Analytics (Semana 4)

#### 4.1 Transcrição de Áudio (Whisper)
**Arquivo**: `app/tasks/whatsapp_tasks.py`

```python
import openai

@celery.task(bind=True, max_retries=3)
def transcrever_audio_task(self, notificacao_id):
    try:
        notificacao = HistoricoNotificacao.query.get(notificacao_id)

        # Abre arquivo de áudio
        audio_file = open(notificacao.url_midia_local, 'rb')

        # Chama Whisper API
        transcript = openai.Audio.transcribe(
            model="whisper-1",
            file=audio_file,
            language="pt"
        )

        # Salva transcrição
        notificacao.mensagem_transcrita = transcript['text']
        db.session.commit()

        # Processa NLP (keywords)
        processar_nlp_keywords.delay(notificacao_id)

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (5 ** self.request.retries))
```

**Configuração OpenAI** (`config.py`):
```python
import openai
openai.api_key = os.getenv('OPENAI_API_KEY')
```

#### 4.2 NLP - Extração de Keywords
**Arquivo**: `app/services/nlp_service.py`

```python
import re

class NLPService:
    KEYWORDS_EQUIPAMENTO = ['esteira', 'motor', 'balança', 'elevador', 'bomba']
    KEYWORDS_URGENCIA = ['parou', 'queimado', 'vazamento', 'fogo', 'urgente']
    KEYWORDS_LOCAL = {
        'centro': 1,  # unidade_id
        'filial 2': 2,
        'depósito': 3
    }

    @staticmethod
    def extrair_dados_os(texto):
        texto_lower = texto.lower()

        # Extrai equipamento
        equipamento_nome = None
        for keyword in NLPService.KEYWORDS_EQUIPAMENTO:
            if keyword in texto_lower:
                equipamento_nome = keyword
                break

        # Extrai urgência
        prioridade = 'media'
        for keyword in NLPService.KEYWORDS_URGENCIA:
            if keyword in texto_lower:
                prioridade = 'alta'
                break

        # Extrai local
        unidade_id = None
        for local, uid in NLPService.KEYWORDS_LOCAL.items():
            if local in texto_lower:
                unidade_id = uid
                break

        return {
            'equipamento_nome': equipamento_nome,
            'prioridade': prioridade,
            'unidade_id': unidade_id,
            'descricao': texto
        }

    @staticmethod
    def criar_os_automatica(dados, solicitante_telefone):
        # Busca equipamento no catálogo
        equipamento = Equipamento.query.filter(
            Equipamento.nome.ilike(f"%{dados['equipamento_nome']}%")
        ).first()

        if not equipamento or not dados['unidade_id']:
            # Dados insuficientes, pede confirmação
            return None

        # Cria OS
        os = OrdemServico(
            numero_os=f"OS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            equipamento_id=equipamento.id,
            unidade_id=dados['unidade_id'],
            titulo=f"Problema em {equipamento.nome}",
            descricao=dados['descricao'],
            prioridade=dados['prioridade'],
            origem_criacao='whatsapp_bot',
            status='aberta'
        )
        db.session.add(os)
        db.session.commit()

        return os
```

**Task**: `processar_nlp_keywords.delay(notificacao_id)`
```python
@celery.task
def processar_nlp_keywords(notificacao_id):
    notificacao = HistoricoNotificacao.query.get(notificacao_id)

    # Extrai dados
    dados = NLPService.extrair_dados_os(notificacao.mensagem_transcrita)

    # Tenta criar OS
    os = NLPService.criar_os_automatica(dados, notificacao.remetente)

    if os:
        WhatsAppService.enviar_mensagem(
            notificacao.remetente,
            f"✅ OS #{os.numero_os} criada automaticamente!\n{os.titulo}"
        )
    else:
        # Pede confirmação via botões
        WhatsAppService.send_buttons_message(
            notificacao.remetente,
            f"Identifiquei: {dados['equipamento_nome']} - {dados['prioridade']}\nDeseja criar OS?",
            [
                {"type": "reply", "reply": {"id": "confirmar_os", "title": "✅ Sim"}},
                {"type": "reply", "reply": {"id": "cancelar_os", "title": "❌ Não"}}
            ]
        )
```

#### 4.3 Dashboards (Chart.js)
**Arquivo**: `app/templates/analytics/dashboard.html`

```html
{% extends "base.html" %}

{% block content %}
<h2>Analytics</h2>

<div class="row">
    <div class="col-md-6">
        <canvas id="chart-mttr"></canvas>
    </div>
    <div class="col-md-6">
        <canvas id="chart-os-status"></canvas>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
// MTTR Mensal
fetch('/analytics/api/mttr')
    .then(res => res.json())
    .then(data => {
        new Chart(document.getElementById('chart-mttr'), {
            type: 'line',
            data: {
                labels: data.map(d => d.mes),
                datasets: [{
                    label: 'MTTR (horas)',
                    data: data.map(d => d.mttr_horas),
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    });

// OSs por Status
fetch('/analytics/api/os-por-status')
    .then(res => res.json())
    .then(data => {
        new Chart(document.getElementById('chart-os-status'), {
            type: 'pie',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    data: Object.values(data),
                    backgroundColor: ['#f00', '#ff0', '#0f0', '#00f']
                }]
            }
        });
    });
</script>
{% endblock %}
```

**Endpoints JSON** (`app/routes/analytics.py`):
```python
@analytics_bp.route('/api/mttr')
def api_mttr():
    # Query para MTTR mensal
    result = db.session.query(
        func.date_format(OrdemServico.created_at, '%Y-%m').label('mes'),
        func.avg(
            func.timestampdiff(
                text('HOUR'),
                OrdemServico.data_abertura,
                OrdemServico.data_finalizacao
            )
        ).label('mttr_horas')
    ).filter(
        OrdemServico.status == 'concluida',
        OrdemServico.created_at >= datetime.now() - timedelta(days=365)
    ).group_by('mes').all()

    return jsonify([{'mes': r.mes, 'mttr_horas': float(r.mttr_horas)} for r in result])

@analytics_bp.route('/api/os-por-status')
def api_os_por_status():
    result = db.session.query(
        OrdemServico.status,
        func.count(OrdemServico.id)
    ).group_by(OrdemServico.status).all()

    return jsonify({r[0]: r[1] for r in result})
```

#### 4.4 QR Code Generator
**Arquivo**: `app/routes/equipamentos.py`

```python
from app.services.qr_service import QRCodeService

@equipamentos_bp.route('/<int:id>/gerar-etiqueta')
def gerar_etiqueta(id):
    equipamento = Equipamento.query.get_or_404(id)

    # Gera PNG
    qr_path = QRCodeService.gerar_etiqueta(id)

    # Retorna PDF pronto para impressão
    pdf_path = QRCodeService.gerar_pdf_etiqueta(id)

    return send_file(pdf_path, as_attachment=True, download_name=f"etiqueta_{equipamento.codigo}.pdf")

@equipamentos_bp.route('/gerar-etiquetas-massa')
def gerar_etiquetas_massa():
    equipamentos = Equipamento.query.filter_by(ativo=True).all()

    # Gera PDF com grid 4x4
    pdf_path = QRCodeService.gerar_pdf_massa(equipamentos)

    return send_file(pdf_path, as_attachment=True, download_name="etiquetas_todas.pdf")
```

**Checklist Fase 4**:
- [ ] Transcrição Whisper funcional (PT-BR)
- [ ] NLP extrai equipamento + urgência + local
- [ ] OS criada automaticamente com dados completos
- [ ] Dashboard Chart.js renderiza gráficos
- [ ] QR Codes gerados em massa (PDF)
- [ ] Morning Briefing enviado às 08:00

---

## 7. ESPECIFICAÇÕES TÉCNICAS DE INTEGRAÇÃO

### 7.1 MegaAPI (WhatsApp)

#### Autenticação
```python
headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}
```

#### Enviar Mensagem de Texto
```python
POST https://api.megaapi.com/v1/messages

{
  "to": "5511999999999",
  "type": "text",
  "text": {
    "body": "Olá, mundo!"
  }
}
```

#### Enviar Documento
```python
POST https://api.megaapi.com/v1/messages

{
  "to": "5511999999999",
  "type": "document",
  "document": {
    "link": "https://gmm.com/static/uploads/pedidos/PEDIDO_123.pdf",
    "filename": "PEDIDO_123.pdf",
    "caption": "Pedido de Compra"
  }
}
```

#### Rate Limit
- **60 mensagens/minuto**
- Header de resposta: `X-RateLimit-Remaining`
- Se excedido: HTTP 429 (retry após 60s)

### 7.2 OpenAI Whisper

#### Transcrição
```python
import openai

audio_file = open("audio.ogg", "rb")
transcript = openai.Audio.transcribe(
    model="whisper-1",
    file=audio_file,
    language="pt"
)

# Response:
# {
#   "text": "A esteira 3 parou com cheiro de queimado."
# }
```

**Limites**:
- Max file size: 25MB
- Formatos: .mp3, .mp4, .mpeg, .mpga, .m4a, .wav, .webm, .ogg
- Timeout: 60s

### 7.3 Twilio SMS (Fallback)

#### Enviar SMS
```python
from twilio.rest import Client

client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

message = client.messages.create(
    to="+5511999999999",
    from_="+1234567890",
    body="[GMM] OS #123 criada: Manutenção urgente na Esteira 3."
)
```

**Custo**: ~R$ 0.30/SMS (Brasil)

### 7.4 SendGrid (Email)

#### Enviar Email com Anexo
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment
import base64

message = Mail(
    from_email='sistema@gmm.com',
    to_emails='fornecedor@example.com',
    subject='Pedido de Compra PC-20260115',
    html_content='<p>Segue em anexo o pedido de compra.</p>'
)

with open('PEDIDO_123.pdf', 'rb') as f:
    data = f.read()
    encoded = base64.b64encode(data).decode()

attachment = Attachment(
    file_content=encoded,
    file_name='PEDIDO_123.pdf',
    file_type='application/pdf'
)
message.attachment = attachment

sg = SendGridAPIClient(SENDGRID_API_KEY)
response = sg.send(message)
```

---

## 8. CUSTOS E RECURSOS

### 8.1 Estimativa de Custos Mensais

| Serviço | Volume | Custo Unitário | Total Mensal |
|---------|--------|----------------|--------------|
| **MegaAPI** | 30.000 msgs | R$ 0.015/msg | R$ 450 |
| **OpenAI Whisper** | 400 min áudio | $0.006/min | R$ 12 |
| **Twilio SMS** | 20 SMS (emergência) | R$ 0.30/SMS | R$ 6 |
| **SendGrid** | 100 emails/dia | Free | R$ 0 |
| **AWS S3** | 10GB | $0.023/GB | R$ 1 |
| **Servidor** | VPS 4GB RAM | - | R$ 100 |
| **PostgreSQL** | Managed (opcional) | - | R$ 50 |
| **Redis** | Managed (opcional) | - | R$ 30 |
| **TOTAL** | | | **R$ 649/mês** |

### 8.2 Infraestrutura Recomendada

#### Ambiente de Desenvolvimento
```
- CPU: 2 cores
- RAM: 4GB
- Disco: 20GB SSD
- OS: Ubuntu 22.04 LTS
- Database: SQLite
- Redis: Local (docker)
```

#### Ambiente de Produção (até 50 usuários)
```
- Servidor: VPS (DigitalOcean, AWS EC2 t3.medium)
- CPU: 2 cores
- RAM: 4GB
- Disco: 50GB SSD
- OS: Ubuntu 22.04 LTS
- Database: PostgreSQL 14
- Redis: Local ou ElastiCache
- Backup: S3 (50GB)
```

#### Escalabilidade (50-200 usuários)
```
- Load Balancer: Nginx
- App Servers: 2x (4GB RAM cada)
- Database: RDS PostgreSQL (Multi-AZ)
- Redis: ElastiCache (cluster mode)
- Storage: S3 (100GB)
- CDN: CloudFront (opcional)
```

### 8.3 Recursos Humanos

| Fase | Duração | Desenvolvedor | Horas |
|------|---------|---------------|-------|
| Fase 1 | 1 semana | Backend | 40h |
| Fase 2 | 1 semana | Fullstack | 40h |
| Fase 3 | 1 semana | Fullstack | 40h |
| Fase 4 | 1 semana | Fullstack + Data | 40h |
| **TOTAL** | **4 semanas** | | **160h** |

**Estimativa de custo (freelancer BR)**: R$ 80-150/hora = R$ 12.800 - R$ 24.000

### 8.4 Monitoramento de Custos

#### Dashboard de Métricas
- Taxa de uso da MegaAPI (% do limite mensal)
- Custo acumulado Whisper (minutos transcritos)
- SMS enviados (fallback)
- Storage S3 (GB utilizados)

#### Alertas Automáticos
- Se MegaAPI > 80% do limite → Aviso ao admin
- Se Whisper > R$ 50/mês → Considerar limitar transcrições
- Se SMS > 50/mês → Investigar problemas no WhatsApp

---

## 9. GLOSSÁRIO TÉCNICO

| Termo | Definição |
|-------|-----------|
| **Circuit Breaker** | Padrão que previne chamadas a serviços com falha recorrente |
| **MTTR** | Mean Time To Repair - Tempo médio de reparo de uma OS |
| **TCO** | Total Cost of Ownership - Custo total de propriedade de um equipamento |
| **NLP** | Natural Language Processing - Processamento de linguagem natural |
| **One-Tap Approval** | Aprovação com um único clique/toque via botão interativo |
| **Zero-Loss** | Princípio de não perder nenhuma mensagem ou dado |
| **Cold Storage** | Armazenamento de longo prazo para dados raramente acessados |
| **Webhook** | Endpoint HTTP que recebe notificações push de serviços externos |
| **HMAC** | Hash-based Message Authentication Code - Validação de integridade de mensagens |

---

## 10. CRITÉRIOS DE ACEITAÇÃO

### Fase 1
- [ ] 100% das mensagens inbound salvas em historico_notificacoes
- [ ] Mídias baixadas em < 30s (95th percentile)
- [ ] Deduplicação funciona (teste com mensagem duplicada)
- [ ] Webhook responde em < 500ms

### Fase 2
- [ ] Menu interativo exibido corretamente no WhatsApp
- [ ] Botões de aprovação funcionais
- [ ] Central de mensagens carrega em < 2s
- [ ] Player de áudio reproduz arquivos .ogg

### Fase 3
- [ ] Comando #COMPRA cria pedido corretamente
- [ ] Token de aprovação válido por 24h
- [ ] PDF gerado com layout legível
- [ ] Email enviado para fornecedor

### Fase 4
- [ ] Transcrição Whisper com 85%+ precisão (teste com 10 áudios)
- [ ] NLP identifica equipamento em 80%+ dos casos
- [ ] Dashboard Chart.js renderiza sem erros
- [ ] QR Code escaneável e abre WhatsApp

---

**FIM DO DOCUMENTO**

*Este documento consolida todos os requisitos da Plataforma GMM v3.1. Para dúvidas técnicas, consulte os arquivos de código-fonte em `gmm/app/` ou a documentação adicional em `gmm/Doc/CLAUDE.md`.*
