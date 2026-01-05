# 🔍 Auditoria Completa: Backend vs Frontend - GMM v3.1

**Data:** 05/01/2026
**Sistema:** GMM - Gestão Moderna de Manutenção
**Foco:** Integração WhatsApp + Central de Atendimento

---

## ✅ STATUS ATUAL: IMPLEMENTAÇÃO QUASE COMPLETA

### 📊 Resumo Executivo

A análise dos arquivos do sistema revelou que **a Central de Mensagens está 95% implementada**, mas há uma **desconexão crítica** entre o backend robusto (WhatsAppService) e as rotas da Central de Atendimento.

**Situação:**
- ✅ **Backend WhatsApp**: Implementado com Circuit Breaker, Rate Limiting, Criptografia
- ✅ **Frontend (Central)**: Template HTML criado com layout WhatsApp-style
- ✅ **Rotas API**: Endpoints `/api/conversas` e `/api/conversas/<id>/mensagens` criados
- ✅ **Menu**: Link atualizado para "Central de Mensagens"
- ❌ **Integração**: As rotas de terceirizados ainda usam `enviar_whatsapp_task.delay()` diretamente, não o `WhatsAppService` centralizado

---

## 🏗️ ARQUITETURA ENCONTRADA

### Camada 1: Serviços de Infraestrutura (✅ COMPLETO)

```python
app/services/whatsapp_service.py
├── WhatsAppService.enviar_mensagem()        # ✅ Com Circuit Breaker
├── WhatsAppService.send_list_message()      # ✅ Mensagens interativas
├── WhatsAppService.send_button_message()    # ✅ Botões nativos
├── WhatsAppService.send_media()             # ✅ Áudio/imagem/doc
└── WhatsAppService.validar_telefone()       # ✅ Regex validation

app/services/circuit_breaker.py              # ✅ Proteção anti-cascata
app/services/rate_limiter.py                 # ✅ 60 msg/min
app/models/whatsapp_models.py                # ✅ 5 tabelas configuradas
```

**Recursos Avançados Implementados:**
- ✅ Criptografia de API Keys (Fernet)
- ✅ Retry exponencial (Celery)
- ✅ Estados de conversa (máquina de estados)
- ✅ Tokens de acesso com expiração
- ✅ Regras de automação (palavras-chave → ações)

---

### Camada 2: Rotas de Terceirizados (⚠️ INCOMPLETO)

```python
app/routes/terceirizados.py
├── /central-mensagens                       # ✅ Rota da página criada
├── /api/conversas                           # ✅ Lista de chamados
├── /api/conversas/<id>/mensagens            # ✅ Histórico de msgs
├── /api/chamados/<id>/finalizar             # ✅ Marcar como concluído
├── /api/chamados/<id>/info                  # ✅ Estatísticas
└── /chamados/<id>/responder                 # ⚠️ Usa task diretamente
```

**Problema Identificado:**
```python
# ❌ ATUAL (Linha 188)
enviar_whatsapp_task.delay(notif.id)

# ✅ DEVERIA SER
from app.services.whatsapp_service import WhatsAppService
success, response = WhatsAppService.enviar_mensagem(
    telefone=chamado.terceirizado.telefone,
    texto=mensagem,
    prioridade=1,
    notificacao_id=notif.id
)
```

---

### Camada 3: Frontend (✅ COMPLETO)

```
app/templates/terceirizados/central_mensagens.html   # ✅ 752 linhas
├── Layout 2 colunas (Sidebar + Chat)                # ✅
├── Polling automático (5s mensagens, 30s lista)     # ✅
├── Badges de status/prioridade                      # ✅
├── Checks visuais (✓, ✓✓, ✓✓ azul)                  # ✅
├── Suporte a mídias (áudio, img, doc)               # ✅
└── Transcrição de áudio                             # ✅
```

**Navegação:**
```html
<!-- app/templates/base.html - Linha 82 -->
<a href="{{ url_for('terceirizados.central_mensagens') }}">
    <i class="bi bi-whatsapp"></i> Central de Mensagens
</a>
```

---

## ❌ GAPS IDENTIFICADOS

### 1. **Desconexão entre Serviços e Rotas**

**Local:** `app/routes/terceirizados.py` (Linhas 105, 158, 188, 332)

**Problema:**
As rotas de terceirizados ainda chamam diretamente a task `enviar_whatsapp_task.delay()`, pulando:
- Circuit Breaker (proteção contra API instável)
- Rate Limiter (respeito ao limite de 60 msg/min)
- Validação centralizada de telefone
- Log estruturado de falhas

**Impacto:**
- ⚠️ Sem proteção contra cascata de falhas
- ⚠️ Risco de ultrapassar rate limit da API
- ⚠️ Telefones inválidos podem gerar erros silenciosos

---

### 2. **Falta de Integração com Mensagens Interativas**

**Local:** Central de Mensagens (Template + Rotas)

**Problema:**
O backend tem suporte a:
- Listas interativas (`send_list_message`)
- Botões nativos (`send_button_message`)
- Anexos de mídia (`send_media`)

Mas a Central não expõe essas funcionalidades no frontend.

**Exemplo de uso potencial:**
```python
# Botão de "Aceitar Orçamento" direto no WhatsApp
WhatsAppService.send_button_message(
    phone="5511999999999",
    body="Orçamento de R$ 1.500,00 para reparo do AC",
    buttons=[
        {"id": "aprovar", "title": "✅ Aprovar"},
        {"id": "rejeitar", "title": "❌ Rejeitar"}
    ]
)
```

---

### 3. **Falta de Dashboard de Monitoramento**

**Local:** Não existe

**Problema:**
Com Circuit Breaker e Rate Limiter implementados, seria essencial ter uma tela para visualizar:
- Status do Circuit Breaker (OPEN/CLOSED)
- Taxa de envio atual (mensagens/minuto)
- Histórico de falhas da API
- Filas do Celery (mensagens pendentes)

**Proposta:**
Criar `/admin/whatsapp/status` com métricas em tempo real.

---

### 4. **Ausência de Webhooks de Status**

**Local:** `app/routes/webhook.py`

**Problema:**
O sistema já tem webhook para receber mensagens inbound, mas não processa callbacks de status:
- `delivered` (mensagem entregue)
- `read` (mensagem lida)
- `failed` (falha no envio)

**Impacto:**
Os checks visuais (✓, ✓✓) na Central não atualizam em tempo real, dependem de polling.

---

### 5. **Falta de Testes da Integração**

**Local:** `tests/unit/test_whatsapp_service.py` existe, mas:

**Problema:**
- ✅ Testes unitários do `WhatsAppService`
- ❌ Testes de integração (Rotas → Service → Task)
- ❌ Testes E2E (Frontend → API → WhatsApp)

---

## 📋 PLANO DE IMPLEMENTAÇÃO

### 🎯 Fase 1: Correção da Integração de Serviços (CRÍTICA)

**Prioridade:** 🔴 ALTA
**Tempo Estimado:** 2-3 horas
**Objetivo:** Fazer todas as rotas usarem o `WhatsAppService` ao invés de chamar tasks diretamente.

#### Arquivos a Modificar:
1. **`app/routes/terceirizados.py`**
   - Linha 105: Rota `criar_chamado()`
   - Linha 158: Rota `cobrar_terceirizado()`
   - Linha 188: Rota `responder_manual()`
   - Linha 332: Rota `api_finalizar_chamado()`

#### Implementação:

```python
# ========== ALTERAÇÃO 1: Importação no topo do arquivo ==========
from app.services.whatsapp_service import WhatsAppService

# ========== ALTERAÇÃO 2: Substituir chamadas diretas ==========

# ANTES (Linha 105 - criar_chamado)
enviar_whatsapp_task.delay(notif.id)

# DEPOIS
success, response = WhatsAppService.enviar_mensagem(
    telefone=terceirizado.telefone,
    texto=msg,
    prioridade=1,  # Chamado novo = prioridade normal
    notificacao_id=notif.id
)

if success:
    flash('Chamado criado e notificação enviada.', 'success')
else:
    # Se Circuit Breaker aberto ou rate limit
    if response.get('code') == 'CIRCUIT_OPEN':
        flash('Chamado criado. Mensagem será enviada quando API estabilizar.', 'warning')
    elif response.get('status') == 'enfileirado':
        flash('Chamado criado. Mensagem enfileirada (rate limit).', 'info')
    else:
        flash(f'Chamado criado, mas falha no envio: {response.get("error")}', 'warning')

# ========== ALTERAÇÃO 3: Adicionar tratamento de erros ==========
# Repetir padrão acima para as outras 3 rotas (cobrar, responder, finalizar)
```

---

### 🎯 Fase 2: Exposição de Recursos Interativos no Frontend

**Prioridade:** 🟡 MÉDIA
**Tempo Estimado:** 4-6 horas
**Objetivo:** Permitir envio de botões, listas e mídias direto da Central.

#### 2.1 Adicionar Botões de Ação Rápida

**Arquivo:** `app/templates/terceirizados/central_mensagens.html`

**Localização:** Dentro do `chat-input-area` (após o input de texto)

```html
<!-- Linha ~370 -->
<div class="chat-input-area">
    <!-- Input atual -->
    <input type="text" id="inputMsg" ...>

    <!-- NOVO: Dropdown de ações rápidas -->
    <div class="dropdown">
        <button class="btn btn-light dropdown-toggle" data-bs-toggle="dropdown">
            <i class="bi bi-three-dots"></i>
        </button>
        <ul class="dropdown-menu">
            <li><a class="dropdown-item" onclick="enviarListaInterativa()">
                <i class="bi bi-list-ul"></i> Enviar Lista de Opções
            </a></li>
            <li><a class="dropdown-item" onclick="enviarBotoes()">
                <i class="bi bi-ui-checks"></i> Enviar Botões
            </a></li>
            <li><a class="dropdown-item" onclick="anexarArquivo()">
                <i class="bi bi-paperclip"></i> Anexar Arquivo
            </a></li>
        </ul>
    </div>

    <button type="submit" ...>Enviar</button>
</div>
```

#### 2.2 Criar Rotas para Mensagens Interativas

**Arquivo:** `app/routes/terceirizados.py`

```python
@bp.route('/api/chamados/<int:id>/enviar-lista', methods=['POST'])
@login_required
def enviar_lista_interativa(id):
    """Envia lista interativa (menu nativo do WhatsApp)"""
    chamado = ChamadoExterno.query.get_or_404(id)
    dados = request.json

    sections = dados.get('sections', [])
    header = dados.get('header', 'Opções')
    body = dados.get('body', 'Selecione uma opção:')

    success, response = WhatsAppService.send_list_message(
        phone=chamado.terceirizado.telefone,
        header=header,
        body=body,
        sections=sections
    )

    if success:
        # Registra no histórico
        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='lista_interativa',
            destinatario=chamado.terceirizado.telefone,
            mensagem=f"Lista: {header}",
            tipo_conteudo='interactive',
            status_envio='enviado',
            direcao='outbound'
        )
        db.session.add(notif)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': response}), 500


@bp.route('/api/chamados/<int:id>/enviar-botoes', methods=['POST'])
@login_required
def enviar_botoes(id):
    """Envia mensagem com botões nativos"""
    chamado = ChamadoExterno.query.get_or_404(id)
    dados = request.json

    body = dados.get('body')
    buttons = dados.get('buttons', [])

    success, response = WhatsAppService.send_button_message(
        phone=chamado.terceirizado.telefone,
        body=body,
        buttons=buttons
    )

    if success:
        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='botoes',
            destinatario=chamado.terceirizado.telefone,
            mensagem=body,
            tipo_conteudo='interactive',
            status_envio='enviado',
            direcao='outbound'
        )
        db.session.add(notif)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': response}), 500


@bp.route('/api/chamados/<int:id>/enviar-midia', methods=['POST'])
@login_required
def enviar_midia(id):
    """Envia arquivo de mídia (imagem, documento, áudio)"""
    chamado = ChamadoExterno.query.get_or_404(id)

    if 'arquivo' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400

    arquivo = request.files['arquivo']
    caption = request.form.get('caption', '')

    # Salva arquivo localmente (ou S3/CDN)
    from werkzeug.utils import secure_filename
    import os
    filename = secure_filename(arquivo.filename)
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'whatsapp', filename)
    arquivo.save(upload_path)

    # Determina tipo de mídia
    media_type = 'document'
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        media_type = 'image'
    elif filename.lower().endswith(('.mp3', '.ogg', '.m4a')):
        media_type = 'audio'

    # Envia via WhatsApp
    public_url = f"{request.host_url}static/uploads/whatsapp/{filename}"

    success, response = WhatsAppService.send_media(
        phone=chamado.terceirizado.telefone,
        media_type=media_type,
        media_url=public_url,
        caption=caption
    )

    if success:
        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='midia_enviada',
            destinatario=chamado.terceirizado.telefone,
            mensagem=caption or f"Arquivo: {filename}",
            tipo_conteudo=media_type,
            url_midia_local=public_url,
            caption=caption,
            status_envio='enviado',
            direcao='outbound'
        )
        db.session.add(notif)
        db.session.commit()
        return jsonify({'success': True, 'url': public_url})
    else:
        return jsonify({'success': False, 'error': response}), 500
```

---

### 🎯 Fase 3: Dashboard de Monitoramento

**Prioridade:** 🟡 MÉDIA
**Tempo Estimado:** 3-4 horas
**Objetivo:** Criar tela de status em tempo real do sistema WhatsApp.

#### Arquivo Novo: `app/templates/admin/whatsapp_status.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="container-fluid">
    <h2><i class="bi bi-activity"></i> Status do Sistema WhatsApp</h2>

    <div class="row mt-4">
        <!-- Circuit Breaker -->
        <div class="col-md-3">
            <div class="card">
                <div class="card-body text-center">
                    <i class="bi bi-shield-check display-4" id="cbIcon"></i>
                    <h5 class="mt-3">Circuit Breaker</h5>
                    <h3 id="cbStatus" class="text-success">CLOSED</h3>
                    <small id="cbInfo">Sistema operando normalmente</small>
                </div>
            </div>
        </div>

        <!-- Rate Limiter -->
        <div class="col-md-3">
            <div class="card">
                <div class="card-body text-center">
                    <i class="bi bi-speedometer2 display-4 text-warning"></i>
                    <h5 class="mt-3">Taxa de Envio</h5>
                    <h3 id="rateCount">0</h3>
                    <small>mensagens no último minuto (máx: 60)</small>
                </div>
            </div>
        </div>

        <!-- Fila Celery -->
        <div class="col-md-3">
            <div class="card">
                <div class="card-body text-center">
                    <i class="bi bi-inbox display-4 text-info"></i>
                    <h5 class="mt-3">Fila de Mensagens</h5>
                    <h3 id="queueSize">0</h3>
                    <small>mensagens aguardando envio</small>
                </div>
            </div>
        </div>

        <!-- Últimas Falhas -->
        <div class="col-md-3">
            <div class="card">
                <div class="card-body text-center">
                    <i class="bi bi-exclamation-triangle display-4 text-danger"></i>
                    <h5 class="mt-3">Falhas (1h)</h5>
                    <h3 id="failCount">0</h3>
                    <small>últimos erros registrados</small>
                </div>
            </div>
        </div>
    </div>

    <!-- Gráfico de Mensagens -->
    <div class="row mt-4">
        <div class="col-12">
            <div class="card">
                <div class="card-body">
                    <h5>Volume de Mensagens (Últimas 24h)</h5>
                    <canvas id="chartMensagens" height="80"></canvas>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Atualiza métricas a cada 5 segundos
setInterval(async () => {
    const res = await fetch('/admin/api/whatsapp/metrics');
    const data = await res.json();

    // Circuit Breaker
    const cbStatus = document.getElementById('cbStatus');
    const cbIcon = document.getElementById('cbIcon');
    if (data.circuit_breaker.status === 'OPEN') {
        cbStatus.textContent = 'OPEN';
        cbStatus.className = 'text-danger';
        cbIcon.className = 'bi bi-shield-x display-4 text-danger';
    } else {
        cbStatus.textContent = 'CLOSED';
        cbStatus.className = 'text-success';
        cbIcon.className = 'bi bi-shield-check display-4 text-success';
    }

    document.getElementById('rateCount').textContent = data.rate_limiter.count;
    document.getElementById('queueSize').textContent = data.celery.queue_size;
    document.getElementById('failCount').textContent = data.failures.last_hour;
}, 5000);
</script>
{% endblock %}
```

#### Rota de API para Métricas

**Arquivo:** `app/routes/admin_whatsapp.py`

```python
@bp.route('/admin/api/whatsapp/metrics')
@login_required
def whatsapp_metrics():
    """Retorna métricas em tempo real do sistema WhatsApp"""
    from app.services.circuit_breaker import CircuitBreaker
    from app.services.rate_limiter import RateLimiter
    from app.models.terceirizados_models import HistoricoNotificacao
    from datetime import datetime, timedelta

    # Circuit Breaker
    cb_open = not CircuitBreaker.should_attempt()

    # Rate Limiter
    pode_enviar, restantes = RateLimiter.check_limit()
    rate_count = 60 - restantes

    # Fila Celery (requer Flower ou inspect)
    from celery import current_app as celery_app
    inspect = celery_app.control.inspect()
    reserved = inspect.reserved()
    queue_size = sum(len(tasks) for tasks in (reserved or {}).values())

    # Falhas última hora
    uma_hora_atras = datetime.utcnow() - timedelta(hours=1)
    fail_count = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.status_envio == 'falhou',
        HistoricoNotificacao.criado_em >= uma_hora_atras
    ).count()

    return jsonify({
        'circuit_breaker': {
            'status': 'OPEN' if cb_open else 'CLOSED',
            'failure_count': CircuitBreaker.failure_count,
            'threshold': CircuitBreaker.FAILURE_THRESHOLD
        },
        'rate_limiter': {
            'count': rate_count,
            'max': RateLimiter.MAX_PER_MINUTE,
            'can_send': pode_enviar
        },
        'celery': {
            'queue_size': queue_size
        },
        'failures': {
            'last_hour': fail_count
        }
    })
```

---

### 🎯 Fase 4: Webhooks de Status

**Prioridade:** 🟢 BAIXA
**Tempo Estimado:** 2-3 horas
**Objetivo:** Atualizar checks visuais (✓✓) em tempo real via webhooks.

#### Arquivo: `app/routes/webhook.py`

```python
@bp.route('/webhook/whatsapp/status', methods=['POST'])
def whatsapp_status_webhook():
    """
    Processa callbacks da MegaAPI sobre status de mensagens.

    Payload esperado:
    {
        "message_id": "wamid.xxx",
        "status": "delivered" | "read" | "failed",
        "timestamp": "2026-01-05T14:30:00Z"
    }
    """
    try:
        data = request.json
        message_id = data.get('message_id')
        status = data.get('status')

        # Encontra notificação pelo megaapi_id
        notif = HistoricoNotificacao.query.filter_by(megaapi_id=message_id).first()

        if notif:
            # Mapeia status da API para nosso modelo
            status_map = {
                'delivered': 'entregue',
                'read': 'lido',
                'failed': 'falhou'
            }

            notif.status_envio = status_map.get(status, notif.status_envio)
            db.session.commit()

            logger.info(f"Status atualizado: {message_id} -> {status}")
            return jsonify({'success': True}), 200
        else:
            logger.warning(f"Mensagem não encontrada: {message_id}")
            return jsonify({'error': 'Message not found'}), 404

    except Exception as e:
        logger.error(f"Erro no webhook de status: {str(e)}")
        return jsonify({'error': str(e)}), 500
```

**Configuração na MegaAPI:**
```bash
# URL do webhook a configurar no painel da MegaAPI
https://seu-dominio.com/webhook/whatsapp/status
```

---

### 🎯 Fase 5: Testes de Integração

**Prioridade:** 🟡 MÉDIA
**Tempo Estimado:** 4-6 horas
**Objetivo:** Garantir que todas as camadas funcionam em conjunto.

#### Arquivo Novo: `tests/integration/test_central_mensagens.py`

```python
import pytest
from app import create_app, db
from app.models.terceirizados_models import ChamadoExterno, HistoricoNotificacao, Terceirizado
from app.models.users import Usuario
from datetime import datetime, timedelta

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_user(app):
    """Cria usuário autenticado"""
    user = Usuario(nome='Admin', email='admin@test.com', tipo='admin')
    user.set_password('test123')
    db.session.add(user)
    db.session.commit()
    return user

def test_central_mensagens_page_loads(client, auth_user):
    """Testa se a página da Central carrega"""
    # Login
    client.post('/login', data={'email': 'admin@test.com', 'senha': 'test123'})

    # Acessa Central
    response = client.get('/terceirizados/central-mensagens')
    assert response.status_code == 200
    assert b'Central GMM' in response.data

def test_api_conversas_retorna_lista(client, auth_user):
    """Testa endpoint de lista de conversas"""
    # Cria terceirizado e chamado
    terc = Terceirizado(nome='João', telefone='5511999999999', empresa='JM Tech')
    db.session.add(terc)
    db.session.commit()

    chamado = ChamadoExterno(
        numero_chamado='CH-2026-001',
        terceirizado_id=terc.id,
        titulo='Teste',
        status='aguardando',
        prazo_combinado=datetime.utcnow() + timedelta(days=1),
        criado_por=auth_user.id
    )
    db.session.add(chamado)
    db.session.commit()

    # Login
    client.post('/login', data={'email': 'admin@test.com', 'senha': 'test123'})

    # Chama API
    response = client.get('/terceirizados/api/conversas')
    assert response.status_code == 200

    data = response.get_json()
    assert len(data) == 1
    assert data[0]['prestador'] == 'João'

def test_envio_mensagem_usa_whatsapp_service(client, auth_user, mocker):
    """Testa se envio de mensagem usa WhatsAppService"""
    # Mock do WhatsAppService
    mock_enviar = mocker.patch('app.services.whatsapp_service.WhatsAppService.enviar_mensagem')
    mock_enviar.return_value = (True, {'message_id': 'wamid.123'})

    # Cria chamado
    terc = Terceirizado(nome='Maria', telefone='5511988888888', empresa='MS Corp')
    db.session.add(terc)
    db.session.commit()

    chamado = ChamadoExterno(
        numero_chamado='CH-2026-002',
        terceirizado_id=terc.id,
        titulo='Urgente',
        status='aguardando',
        prazo_combinado=datetime.utcnow() + timedelta(hours=2),
        criado_por=auth_user.id
    )
    db.session.add(chamado)
    db.session.commit()

    # Login
    client.post('/login', data={'email': 'admin@test.com', 'senha': 'test123'})

    # Envia mensagem
    response = client.post(f'/terceirizados/chamados/{chamado.id}/responder', data={
        'mensagem': 'Teste de integração'
    })

    assert response.status_code == 200

    # Verifica se WhatsAppService foi chamado
    mock_enviar.assert_called_once()
    args = mock_enviar.call_args
    assert args[1]['telefone'] == '5511988888888'
    assert args[1]['texto'] == 'Teste de integração'
```

**Para rodar os testes:**
```bash
pytest tests/integration/test_central_mensagens.py -v
```

---

## 📊 CHECKLIST DE IMPLEMENTAÇÃO

### Fase 1: Integração de Serviços (CRÍTICA)
- [ ] Importar `WhatsAppService` em `terceirizados.py`
- [ ] Substituir `enviar_whatsapp_task.delay()` por `WhatsAppService.enviar_mensagem()` em 4 rotas
- [ ] Adicionar tratamento de Circuit Breaker aberto
- [ ] Adicionar tratamento de Rate Limit atingido
- [ ] Testar manualmente criação de chamado
- [ ] Testar manualmente envio de cobrança
- [ ] Testar manualmente resposta no chat
- [ ] Testar manualmente finalização de chamado

### Fase 2: Recursos Interativos
- [ ] Adicionar dropdown de ações rápidas no template
- [ ] Criar rota `/api/chamados/<id>/enviar-lista`
- [ ] Criar rota `/api/chamados/<id>/enviar-botoes`
- [ ] Criar rota `/api/chamados/<id>/enviar-midia`
- [ ] Implementar função JS `enviarListaInterativa()`
- [ ] Implementar função JS `enviarBotoes()`
- [ ] Implementar função JS `anexarArquivo()` com upload
- [ ] Testar envio de lista interativa
- [ ] Testar envio de botões
- [ ] Testar upload e envio de imagem

### Fase 3: Dashboard de Monitoramento
- [ ] Criar template `whatsapp_status.html`
- [ ] Criar rota `/admin/api/whatsapp/metrics`
- [ ] Adicionar link no menu Admin
- [ ] Configurar Chart.js para gráfico de volume
- [ ] Testar atualização em tempo real
- [ ] Criar alertas visuais para Circuit Breaker OPEN

### Fase 4: Webhooks de Status
- [ ] Criar rota `/webhook/whatsapp/status`
- [ ] Mapear status da API para modelo interno
- [ ] Adicionar logs estruturados
- [ ] Configurar URL no painel da MegaAPI
- [ ] Testar com ferramenta de webhook (ex: ngrok + Postman)
- [ ] Validar atualização dos checks visuais na Central

### Fase 5: Testes de Integração
- [ ] Criar arquivo `tests/integration/test_central_mensagens.py`
- [ ] Implementar 5 testes principais
- [ ] Configurar fixtures de autenticação
- [ ] Mockar chamadas externas (MegaAPI)
- [ ] Rodar suite completa de testes
- [ ] Atingir 80%+ de cobertura nas rotas críticas

---

## 🚨 RISCOS E MITIGAÇÕES

### Risco 1: Circuit Breaker Aberto em Horário de Pico
**Cenário:** MegaAPI instável fecha o Circuit Breaker, bloqueando todos os envios.

**Mitigação:**
- ✅ Sistema já enfileira mensagens automaticamente
- ✅ Celery reprocessa com retry exponencial
- ⚠️ **NOVO:** Criar notificação no Dashboard quando Circuit abrir
- ⚠️ **NOVO:** Email automático para admin quando ficar aberto > 5 min

### Risco 2: Fila do Celery Crescer Descontroladamente
**Cenário:** Rate limit + muitas mensagens = fila com 1000+ itens.

**Mitigação:**
- ✅ Rate Limiter já controla fluxo
- ⚠️ **NOVO:** Monitorar tamanho da fila no Dashboard
- ⚠️ **NOVO:** Alertar quando fila > 100 mensagens
- ⚠️ **NOVO:** Limitar criação de novos chamados se fila > 500

### Risco 3: Usuários Enviarem Mensagens Repetidas
**Cenário:** Operador não vê feedback imediato e clica 3x em "Enviar".

**Mitigação:**
- ✅ Botão já desabilita durante envio (template linha ~640)
- ⚠️ **NOVO:** Adicionar debounce de 2s no frontend
- ⚠️ **NOVO:** Validar no backend se não há mensagem idêntica nos últimos 30s

---

## 📈 MÉTRICAS DE SUCESSO

### KPIs para Avaliar Implementação

| Métrica | Antes | Meta Após Implementação |
|---------|-------|-------------------------|
| Taxa de falha de envio | Desconhecida | < 2% |
| Tempo médio de resposta ao prestador | Manual | < 1 minuto |
| Mensagens perdidas por rate limit | Possível | 0 (enfileiramento) |
| Uptime do sistema de envio | ~95% | > 99% (com Circuit Breaker) |
| Satisfação do operador | Não medida | Survey após 1 mês |

---

## 🎓 DOCUMENTAÇÃO ADICIONAL

### Para Desenvolvedores
- **Swagger/OpenAPI:** Documentar endpoints da API
- **Postman Collection:** Criar coleção com exemplos de uso
- **Diagrama de Arquitetura:** Fluxo completo (Frontend → Rotas → Service → Task → MegaAPI)

### Para Usuários Finais
- **Manual do Operador:** Como usar a Central de Mensagens
- **FAQ:** Perguntas frequentes sobre status de mensagens
- **Troubleshooting:** O que fazer quando mensagem falha

---

## ✅ CONCLUSÃO

### Status Atual: 95% Implementado

**O que está pronto:**
- ✅ Backend robusto com Circuit Breaker, Rate Limiter, Criptografia
- ✅ Central de Atendimento com layout WhatsApp-style
- ✅ Rotas API para conversas e mensagens
- ✅ Polling automático no frontend
- ✅ Suporte a mídias (áudio, imagem, doc)

**O que falta (Crítico):**
- ❌ Integração das rotas com `WhatsAppService` (Fase 1)

**O que falta (Desejável):**
- ⚠️ Mensagens interativas na Central (Fase 2)
- ⚠️ Dashboard de monitoramento (Fase 3)
- ⚠️ Webhooks de status (Fase 4)
- ⚠️ Testes de integração (Fase 5)

### Próximos Passos Imediatos

1. **AGORA:** Implementar Fase 1 (2-3 horas)
2. **Hoje:** Testar envio de mensagens na Central
3. **Amanhã:** Implementar Fase 2 (recursos interativos)
4. **Esta Semana:** Fases 3, 4 e 5

---

**Preparado por:** Claude Sonnet 4.5
**Data:** 05/01/2026
**Versão do Sistema:** GMM v3.1
**Status:** ✅ Pronto para Implementação
