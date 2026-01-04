# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GMM (Gestão Moderna de Manutenção) is a Flask-based business management system for maintenance operations with WhatsApp integration for automated notifications and external service provider coordination.

**Tech Stack**: Flask 3.0+, SQLAlchemy 2.0+, Celery, Redis, MegaAPI (WhatsApp)

## Essential Commands

### Development

```bash
# Start the application (development server on port 5000)
python run.py

# Start Celery worker (required for WhatsApp and background tasks)
celery -A app.celery worker --loglevel=info

# Start Celery Beat scheduler (required for periodic tasks)
celery -A app.celery beat --loglevel=info

# Database migrations
flask db migrate -m "Description of changes"
flask db upgrade

# Initialize database with seed data
python seed_db.py

# Initialize inventory balances (after seed)
python init_saldos_estoque.py
```

### Testing

```bash
# Run unit tests
$env:PYTHONPATH="."  # Windows PowerShell
python tests/unit/test_whatsapp_service.py
python tests/unit/test_alerta_service.py

# Run integration tests
python tests/integration/test_webhook.py
python tests/integration/test_outbound.py
```

## Architecture Overview

### Application Structure

This is a **modular Flask monolith** organized in layers:

```
Routes (HTTP endpoints)
  → Services (business logic)
    → Models (database entities)
      → Database (SQLAlchemy ORM)

Background: Celery Tasks (async processing)
```

### Core Modules

**12 Flask Blueprints** in `app/routes/`:
- `auth`: Login, logout, user registration
- `ponto`: Time clock (entrada/saída)
- `os`: Work orders (ordens de serviço) - largest module
- `admin`: Admin panel, user/unit management
- `terceirizados`: External service provider management
- `equipamentos`: Equipment catalog
- `analytics`: Reports and metrics
- `whatsapp`: WhatsApp outbound messaging UI
- `webhook`: MegaAPI webhook receiver (inbound messages)
- `admin_whatsapp`: WhatsApp configuration dashboard
- `search`: Global search
- `notifications`: Notification management

**Services** in `app/services/`:
- `whatsapp_service.py`: MegaAPI integration with Circuit Breaker
- `roteamento_service.py`: Inbound message routing and command dispatch
- `estoque_service.py`: Inventory business logic
- `os_service.py`: Work order utilities
- `analytics_service.py`: Report generation
- `circuit_breaker.py`: Resilience pattern (Redis-backed)
- `rate_limiter.py`: Fixed-window rate limiting (Redis-backed)
- `alerta_service.py`: Health monitoring and Slack alerts
- `comando_parser.py`: WhatsApp command parsing (#COMPRA, #STATUS, etc.)
- `comando_executores.py`: Command execution handlers
- `estado_service.py`: Conversation state machine
- `template_service.py`: Message template rendering

**Background Tasks** in `app/tasks/`:
- `whatsapp_tasks.py`: Message sending, inbound processing, metrics aggregation, cleanup
- `system_tasks.py`: Automated reminders

### Database Architecture

Multi-tenant database organized by `Unidade` (business units). Key entities:

- **Core**: `Usuario`, `Unidade`, `RegistroPonto`
- **Inventory**: `Estoque`, `EstoqueSaldo` (per-unit balances), `MovimentacaoEstoque` (audit log), `CategoriaEstoque`
- **Equipment**: `Equipamento`, `CategoriaEquipamento`
- **Work Orders**: `OrdemServico`, `AnexosOS`, `TipoManutencao`
- **External Services**: `Terceirizado`, `ChamadoExterno`, `terceirizados_unidades` (M2M)
- **Notifications**: `HistoricoNotificacao` (complete audit trail)
- **WhatsApp**: `RegrasAutomacao`, `TokenAcesso`, `EstadoConversa`, `ConfiguracaoWhatsApp`, `MetricasWhatsApp`

**Important**: Database auto-detects PostgreSQL from `DATABASE_URL` env var, falls back to SQLite (`instance/gmm.db`).

### WhatsApp Integration Flow

**Inbound (Webhook)**:
```
MegaAPI → POST /webhook/whatsapp
  └─ Validate HMAC signature
  └─ Create HistoricoNotificacao record
  └─ Enqueue: processar_mensagem_inbound.delay()
      └─ RoteamentoService.processar()
          ├─ Match sender (Terceirizado by phone)
          ├─ Check active conversation state
          ├─ Parse commands (#COMPRA, #STATUS, #AJUDA)
          ├─ Match automation rules (RegrasAutomacao)
          └─ Execute action (respond, create OS, forward to staff)
```

**Outbound (API)**:
```
Business logic creates HistoricoNotificacao
  └─ Enqueue: enviar_whatsapp_task.delay(notif_id)
      ├─ Check Circuit Breaker (OPEN → skip)
      ├─ Check Rate Limiter (60/min, bypass for priority >= 2)
      ├─ POST to MegaAPI with Bearer token
      ├─ Update status (enviado/falhou)
      └─ Retry logic: 3 attempts with exponential backoff
```

**Resilience Patterns**:
- **Circuit Breaker**: Opens after 5 consecutive failures, auto-recovers after 10 minutes
- **Rate Limiter**: 60 messages/minute (configurable), uses Redis fixed-window counter
- **Message Deduplication**: SHA256 hash prevents duplicate processing
- **Retry Strategy**: Exponential backoff (1min → 5min → 25min)

### Configuration

**Environment Variables** (`.env` or system env):
- `DATABASE_URL`: PostgreSQL connection string (optional, defaults to SQLite)
- `SECRET_KEY`: Flask session secret
- `MEGA_API_KEY`: WhatsApp API token
- `FERNET_KEY`: 32-byte encryption key (generate with `Fernet.generate_key()`)
- `CELERY_BROKER_URL`: Redis URL (default: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND`: Redis URL
- `SLACK_WEBHOOK_URL`: Alert notifications (optional)

**See `config.py`** for defaults and auto-detection logic.

## Development Patterns

### Service Layer Pattern

Business logic lives in services, not routes. Routes should be thin controllers:

```python
# ✅ Good: Route delegates to service
@bp.route('/os/<int:os_id>/consumir', methods=['POST'])
def consumir_peca(os_id):
    estoque_id = request.form.get('estoque_id')
    quantidade = int(request.form.get('quantidade'))

    success = EstoqueService.consumir_item(
        estoque_id=estoque_id,
        quantidade=quantidade,
        os_id=os_id,
        usuario_id=current_user.id
    )

    return jsonify({'success': success})

# ❌ Bad: Route contains business logic
@bp.route('/os/<int:os_id>/consumir', methods=['POST'])
def consumir_peca(os_id):
    # Don't put SQL queries, calculations, or business rules here
    estoque = Estoque.query.get(estoque_id)
    estoque.quantidade_atual -= quantidade
    movimento = MovimentacaoEstoque(...)
    db.session.add(movimento)
    db.session.commit()
```

### Celery Task Pattern

Tasks must use Flask app context for database access:

```python
@celery.task(bind=True, max_retries=3)
def my_task(self, param):
    try:
        # Database and Flask features available due to ContextTask
        user = Usuario.query.get(param)
        # ... do work ...
        return {'status': 'success'}
    except Exception as e:
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
```

### Authentication & Authorization

- Use `@login_required` decorator on protected routes
- Access current user via `flask_login.current_user`
- User types: `admin`, `tecnico`, `comum` (stored in `Usuario.tipo`)
- Admin-only routes should check: `if current_user.tipo != 'admin': abort(403)`

### Database Migrations

After modifying models:

```bash
flask db migrate -m "Add field X to table Y"
flask db upgrade
```

**Important**: Review generated migration files before applying. Auto-detection isn't perfect.

### WhatsApp Message Sending

Always use the service layer with proper error handling:

```python
from app.services.whatsapp_service import WhatsAppService

success, response = WhatsAppService.enviar_mensagem(
    telefone="5511999999999",  # Must be 13 digits with country code
    mensagem="Your message here",
    prioridade=1  # 0-2, where 2 bypasses rate limiting
)

if not success:
    # Handle failure - message may be queued or circuit breaker may be open
    flash('Mensagem será enviada quando possível', 'warning')
```

### WhatsApp Automation Rules

Rules in `RegrasAutomacao` are processed in priority order (higher first):

- **Match types**: `exata` (exact), `contem` (contains), `regex`
- **Actions**: `responder` (auto-reply), `criar_os` (create work order), `transbordar` (forward), `executar_funcao` (run custom handler)
- Rules with `ativa=False` are skipped

### Inventory Management

Inventory uses per-unit balances (`EstoqueSaldo`). Always use `EstoqueService`:

```python
from app.services.estoque_service import EstoqueService

# Consume items (creates MovimentacaoEstoque automatically)
EstoqueService.consumir_item(
    estoque_id=1,
    quantidade=5,
    unidade_id=current_user.unidade_padrao_id,
    os_id=os_id,
    usuario_id=current_user.id
)

# Transfer between units
EstoqueService.transferir_entre_unidades(
    estoque_id=1,
    unidade_origem_id=1,
    unidade_destino_id=2,
    quantidade=10,
    usuario_id=current_user.id
)
```

## Important Implementation Notes

### Phone Number Format

WhatsApp phone numbers **must be 13 digits**: country code + area code + number
- Example: `5511999999999` (Brazil: 55 + 11 + 999999999)
- Validation regex: `^55\d{11}$`

### Message Hashing

Messages are deduplicated using SHA256 hash (stored in `HistoricoNotificacao.mensagem_hash`). Same message to same recipient within deduplication window is rejected.

### Conversation State Expiration

`EstadoConversa` records expire after 24 hours of inactivity. Cleanup runs hourly via `limpar_estados_expirados` task.

### Work Order Status Flow

```
aberta → em_andamento → aguardando_pecas → concluida/cancelada
```

Status transitions are not enforced at database level - handle in application logic.

### File Upload Handling

Work order attachments (`AnexosOS`) are stored in `app/static/uploads/os/`:
- Subdirectories by OS ID
- Filenames are sanitized
- File size tracked in KB
- Types: `foto_antes`, `foto_depois`

### Circuit Breaker Redis Keys

- `whatsapp:cb:state` → `"CLOSED"`, `"OPEN"`, or `"HALF_OPEN"`
- `whatsapp:cb:failures` → integer counter
- `whatsapp:cb:opened_at` → timestamp

Don't manipulate these keys directly - use `CircuitBreaker` class methods.

### Rate Limiter Redis Keys

- `whatsapp:ratelimit:minute:{minute_timestamp}` → request counter
- TTL: 60 seconds
- Priority 2+ messages bypass rate limiting

## Testing Strategy

### Unit Tests

Test services in isolation with mocked dependencies:

```python
# tests/unit/test_whatsapp_service.py
# Tests WhatsAppService with mocked HTTP requests
# Tests Circuit Breaker state transitions
# Tests phone validation
```

### Integration Tests

Test full request/response flows with test database:

```python
# tests/integration/test_webhook.py
# Tests webhook signature validation
# Tests inbound message processing
# Tests automation rule matching
```

**Run tests with**: `$env:PYTHONPATH="."` (Windows) or `export PYTHONPATH=.` (Linux/Mac)

## Common Troubleshooting

### "ModuleNotFoundError: No module named 'cryptography'"

Install dependencies: `pip install -r requirements.txt`

### Celery tasks not executing

1. Check Redis is running: `redis-cli ping` (should return `PONG`)
2. Ensure Celery worker is running: `celery -A app.celery worker --loglevel=info`
3. Check task queue: `redis-cli LLEN celery` (shows pending tasks)

### Circuit Breaker stuck in OPEN state

Manually reset via Redis CLI:
```bash
redis-cli DEL whatsapp:cb:state whatsapp:cb:failures whatsapp:cb:opened_at
```

Or wait 10 minutes for automatic HALF_OPEN transition.

### Database migration conflicts

If migrations are out of sync:
```bash
flask db stamp head  # Mark current state
flask db migrate -m "Fix migrations"
flask db upgrade
```

### WhatsApp messages not sending

1. Check Circuit Breaker status: Admin WhatsApp dashboard
2. Verify `MEGA_API_KEY` is set correctly
3. Check `HistoricoNotificacao` for error details in `resposta_api`
4. Verify phone number format (13 digits)

## Key Files to Understand

Start with these files to understand the system:

1. **`app/__init__.py`** - App factory, Celery initialization, blueprint registration
2. **`config.py`** - Configuration and environment detection
3. **`app/models/models.py`** - Core data models (Usuario, Unidade, RegistroPonto)
4. **`app/routes/os.py`** - Work order management (largest route module)
5. **`app/services/whatsapp_service.py`** - WhatsApp integration entry point
6. **`app/services/roteamento_service.py`** - Inbound message routing logic
7. **`app/tasks/whatsapp_tasks.py`** - Background task definitions

## Additional Documentation

- **`app/services/README_WHATSAPP.md`** - Detailed WhatsApp module documentation
- **`analise_conformidade_prd.md`** - Requirements analysis
- **`prd 2.txt`** - Product requirements document
