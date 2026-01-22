# PRD - Sistema de Respostas Automáticas WhatsApp
## Produto: GMM - Gestão Moderna de Manutenção

**Versão:** 1.0
**Data:** 06/01/2026
**Autor:** Análise de Sistema GMM

---

## 1. CONTEXTO E ANÁLISE DO SISTEMA ATUAL

### 1.1 Arquitetura Atual de WhatsApp

O sistema GMM já possui uma integração robusta com WhatsApp através da **MegaAPI**, com os seguintes componentes:

#### **Modelos de Dados:**
- **Usuario** - Usuários do sistema (admin, tecnico, comum) com telefone
- **Terceirizado** - Prestadores de serviço externos com telefone (formato: 5511999999999)
- **ChamadoExterno** - Chamados para terceirizados vinculados a OS
- **HistoricoNotificacao** - Log completo de mensagens (inbound/outbound)
- **RegrasAutomacao** - Regras de resposta automática (já existente!)
- **EstadoConversa** - Máquina de estados para conversas contextuais

#### **Fluxo de Comunicação Atual:**

**INBOUND (Mensagens Recebidas):**
```
MegaAPI → Webhook /webhook/whatsapp
  └─ Validação HMAC
  └─ Registro em HistoricoNotificacao (direcao='inbound')
  └─ Enfileiramento: processar_mensagem_inbound.delay()
      └─ RoteamentoService.processar()
          ├─ 1. Identifica remetente (Terceirizado.telefone)
          ├─ 2. Verifica estado ativo (EstadoConversa < 24h)
          ├─ 3. Parse de comandos (#COMPRA, #STATUS, EQUIP:)
          ├─ 4. Match RegrasAutomacao (por prioridade)
          ├─ 5. NLP Analysis (extração de entidades)
          └─ 6. Fallback: Menu Interativo
```

**OUTBOUND (Mensagens Enviadas):**
```
Criação de HistoricoNotificacao (direcao='outbound')
  └─ enviar_whatsapp_task.delay(notificacao_id)
      ├─ Circuit Breaker check
      ├─ Rate Limiter (60/min, bypass se prioridade >= 2)
      ├─ POST MegaAPI + Bearer token
      ├─ Update status (enviado/falhou)
      └─ Retry: 3 tentativas com backoff exponencial
```

### 1.2 Identificação de Tipos de Usuário

Atualmente, o sistema identifica usuários por **telefone**:

| Tipo | Tabela | Campo Telefone | Pode Receber WhatsApp? |
|------|--------|----------------|------------------------|
| **Usuário Cadastrado** | `usuarios` | `telefone` (opcional) | ✅ SIM |
| **Fornecedor/Terceirizado** | `terceirizados` | `telefone` (obrigatório) | ✅ SIM |
| **Não Cadastrado** | - | - | ❌ NÃO (ignorado) |

**Regra Atual (roteamento_service.py:25-31):**
```python
terceirizado = Terceirizado.query.filter_by(telefone=remetente).first()
if not terceirizado:
    return {'acao': 'ignorar', 'motivo': 'Remetente não cadastrado'}
```

---

## 2. PROBLEMA IDENTIFICADO

### 2.1 Gap de Comunicação com Usuários Internos

**Problema:** O sistema atual **IGNORA** mensagens de usuários cadastrados (tabela `usuarios`) que não estão na tabela `terceirizados`.

**Impacto:**
- ❌ Gestores não recebem respostas automáticas
- ❌ Técnicos internos não podem interagir via WhatsApp
- ❌ Compradores não recebem confirmações
- ❌ Apenas terceirizados externos têm acesso ao bot

### 2.2 Oportunidades de Automação

Com base na análise do código, identificamos os seguintes pontos para respostas automáticas:

#### **Para FORNECEDORES/TERCEIRIZADOS:**
1. ✅ **Já implementado:** Menu interativo com opções
2. ✅ **Já implementado:** Comandos estruturados (#COMPRA, #STATUS)
3. ✅ **Já implementado:** Aceitação de OS via botões
4. ⚠️ **Parcial:** Notificação ao solicitante após ação

#### **Para USUÁRIOS INTERNOS:**
1. ❌ **Não implementado:** Respostas de boas-vindas
2. ❌ **Não implementado:** Status de pedidos de compra
3. ❌ **Não implementado:** Confirmação de recebimento de solicitações
4. ❌ **Não implementado:** Encaminhamento de respostas de terceirizados

---

## 3. OBJETIVOS DO PRD

### 3.1 Objetivo Geral
Expandir o sistema de respostas automáticas para:
1. **Reconhecer e responder usuários internos** (não apenas terceirizados)
2. **Implementar notificações bidirecionais** (solicitante ↔ terceirizado)
3. **Criar respostas contextuais** para fornecedores e terceirizados
4. **Padronizar fluxos de comunicação** com templates reutilizáveis

### 3.2 Objetivos Específicos

#### **ETAPA 1 - Reconhecimento de Usuários Internos**
- [ ] Expandir `RoteamentoService` para reconhecer `Usuario.telefone`
- [ ] Criar respostas diferenciadas por tipo de usuário (admin, tecnico, comum)
- [ ] Implementar validação de permissões por perfil

#### **ETAPA 2 - Respostas Automáticas para Fornecedores**
- [ ] Confirmação automática de recebimento de OS
- [ ] Atualização de status via comandos simplificados
- [ ] Solicitação de materiais com validação de estoque
- [ ] Template de "OS Concluída" com foto obrigatória

#### **ETAPA 3 - Respostas Automáticas para Terceirizados**
- [ ] Menu contextual baseado em especialidades
- [ ] Notificação de novas OS disponíveis
- [ ] Confirmação de agendamento
- [ ] Avaliação pós-atendimento via botões

#### **ETAPA 4 - Notificações ao Solicitante/Responsável**
- [ ] Notificar solicitante quando terceirizado aceita OS
- [ ] Notificar responsável quando fornecedor conclui serviço
- [ ] Alertar atrasos com base em SLA
- [ ] Encaminhar mensagens de terceirizados para gestores

---

## 4. ESPECIFICAÇÃO TÉCNICA - ETAPAS E TAREFAS

---

### **ETAPA 1: Reconhecimento de Usuários Internos**

**Objetivo:** Permitir que usuários da tabela `usuarios` também recebam respostas automáticas.

#### **Tarefa 1.1: Expandir Identificação de Remetentes**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**
Modificar método `processar()` para buscar tanto em `Terceirizado` quanto em `Usuario`:

```python
@staticmethod
def processar(remetente: str, texto: str) -> dict:
    from app.models.models import Usuario
    from app.models.terceirizados_models import Terceirizado

    # 1. Identifica Tipo de Remetente
    terceirizado = Terceirizado.query.filter_by(telefone=remetente).first()
    usuario = Usuario.query.filter_by(telefone=remetente, ativo=True).first()

    if not terceirizado and not usuario:
        return {
            'acao': 'enviar_mensagem',
            'telefone': remetente,
            'mensagem': "⚠️ Telefone não cadastrado. Entre em contato com o administrador."
        }

    # 2. Determina Perfil
    if terceirizado:
        return RoteamentoService._processar_terceirizado(terceirizado, texto)
    elif usuario:
        return RoteamentoService._processar_usuario(usuario, texto)
```

**Critérios de Aceite:**
- ✅ Mensagens de usuários internos não são mais ignoradas
- ✅ Sistema diferencia entre terceirizado e usuário
- ✅ Cada tipo recebe fluxo específico

---

#### **Tarefa 1.2: Criar Fluxo para Usuários Internos**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**
Criar método `_processar_usuario()` com respostas por tipo:

```python
@staticmethod
def _processar_usuario(usuario, texto):
    """Processa mensagens de usuários internos (admin, tecnico, comum)."""

    # 1. Verifica comandos administrativos
    if usuario.tipo == 'admin':
        if texto.upper().startswith('#ADMIN'):
            return RoteamentoService._processar_comando_admin(usuario, texto)

    # 2. Menu padrão baseado em tipo
    if usuario.tipo == 'admin':
        return RoteamentoService._menu_admin(usuario)
    elif usuario.tipo == 'tecnico':
        return RoteamentoService._menu_tecnico(usuario)
    else:  # comum
        return RoteamentoService._menu_usuario_comum(usuario)
```

**Menus por Tipo:**

**Admin:**
```
📊 Menu Administrativo
Olá [Nome], você tem acesso a:

1️⃣ Status do Sistema
2️⃣ Aprovar Pedidos Pendentes
3️⃣ Ver Chamados em Aberto
4️⃣ Relatório de SLA

Digite o número da opção desejada.
```

**Técnico:**
```
🔧 Menu Técnico
Olá [Nome]!

1️⃣ Minhas OS Abertas
2️⃣ Solicitar Peça
3️⃣ Consultar Estoque
4️⃣ Reportar Problema

Digite o número da opção desejada.
```

**Usuário Comum:**
```
👤 Sistema GMM
Olá [Nome]!

1️⃣ Abrir Chamado
2️⃣ Consultar Meus Chamados
3️⃣ Falar com Suporte

Digite o número da opção desejada.
```

**Critérios de Aceite:**
- ✅ Cada tipo de usuário recebe menu específico
- ✅ Opções respeitam permissões do perfil
- ✅ Comandos numéricos funcionam

---

#### **Tarefa 1.3: Implementar Estado de Conversa para Usuários**

**Arquivo:** `app/models/whatsapp_models.py`

**Ação:**
Expandir modelo `EstadoConversa` para suportar usuários:

```python
class EstadoConversa(db.Model):
    # ... campos existentes ...

    # Novo campo para diferenciar tipo de usuário
    usuario_tipo = db.Column(db.String(20))  # 'terceirizado', 'usuario_admin', 'usuario_tecnico', 'usuario_comum'
    usuario_id = db.Column(db.Integer)  # ID na tabela correspondente
```

**Migration:**
```bash
flask db migrate -m "Adiciona campos usuario_tipo e usuario_id em EstadoConversa"
flask db upgrade
```

**Critérios de Aceite:**
- ✅ Migration executada sem erros
- ✅ Campos aceitos em novos registros
- ✅ Busca por estado funciona para ambos os tipos

---

### **ETAPA 2: Respostas Automáticas para Fornecedores**

**Objetivo:** Criar respostas contextuais para fornecedores cadastrados.

#### **Tarefa 2.1: Confirmação Automática de Recebimento de OS**

**Arquivo:** `app/routes/terceirizados.py` (ou onde OS é criada para terceirizado)

**Contexto:** Atualmente, quando uma OS é criada para um terceirizado, ele recebe notificação mas não há confirmação automática de recebimento.

**Ação:**
Adicionar regra de automação padrão para confirmação:

```python
# Em app/tasks/whatsapp_tasks.py ou onde notificação é enviada

def enviar_notificacao_os_terceirizado(chamado_id, terceirizado_id):
    """Envia notificação de nova OS para terceirizado com botões de confirmação."""
    from app.models.terceirizados_models import ChamadoExterno, Terceirizado
    from app.services.whatsapp_service import WhatsAppService

    chamado = ChamadoExterno.query.get(chamado_id)
    terceirizado = Terceirizado.query.get(terceirizado_id)

    mensagem = f"""🔔 *NOVA ORDEM DE SERVIÇO*

📋 *Chamado:* #{chamado.numero_chamado}
📝 *Título:* {chamado.titulo}
⏰ *Prazo:* {chamado.prazo_combinado.strftime('%d/%m/%Y %H:%M')}
🎯 *Prioridade:* {chamado.prioridade.upper()}

📄 *Descrição:*
{chamado.descricao}

⚠️ Por favor, confirme o recebimento respondendo:
*SIM* - Aceito o chamado
*NÃO* - Não posso atender
"""

    # Cria estado de conversa aguardando confirmação
    from app.models.whatsapp_models import EstadoConversa
    from app.extensions import db
    import json

    estado = EstadoConversa(
        telefone=terceirizado.telefone,
        chamado_id=chamado_id,
        estado_atual='aguardando_confirmacao_os',
        contexto=json.dumps({
            'fluxo': 'confirmacao_os',
            'chamado_id': chamado_id,
            'data_envio': datetime.utcnow().isoformat()
        }),
        usuario_tipo='terceirizado',
        usuario_id=terceirizado_id
    )
    db.session.add(estado)
    db.session.commit()

    WhatsAppService.enviar_mensagem(
        telefone=terceirizado.telefone,
        texto=mensagem,
        prioridade=1
    )
```

**Processamento da Resposta:**

```python
# Em app/services/roteamento_service.py

@staticmethod
def _processar_terceirizado(terceirizado, texto):
    """Processa mensagens de terceirizados."""

    # 1. Verifica estado ativo
    estado = EstadoConversa.query.filter_by(
        telefone=terceirizado.telefone,
        usuario_tipo='terceirizado'
    ).order_by(EstadoConversa.updated_at.desc()).first()

    if estado and estado.estado_atual == 'aguardando_confirmacao_os':
        return RoteamentoService._processar_confirmacao_os(terceirizado, texto, estado)

    # ... resto do fluxo existente ...

@staticmethod
def _processar_confirmacao_os(terceirizado, texto, estado):
    """Processa confirmação de OS por terceirizado."""
    from app.extensions import db
    from app.models.terceirizados_models import ChamadoExterno
    import json

    contexto = json.loads(estado.contexto)
    chamado_id = contexto['chamado_id']
    chamado = ChamadoExterno.query.get(chamado_id)

    texto_lower = texto.lower().strip()

    # Aceite
    if texto_lower in ['sim', 's', 'aceito', 'ok', 'confirmo']:
        chamado.status = 'aceito'
        chamado.data_inicio = datetime.utcnow()
        db.session.delete(estado)  # Limpa estado
        db.session.commit()

        # NOTIFICA SOLICITANTE (Tarefa 4.1)
        RoteamentoService._notificar_solicitante_os_aceita(chamado)

        resposta = f"""✅ *CHAMADO ACEITO*

Obrigado por confirmar, {terceirizado.nome}!

📋 Chamado #{chamado.numero_chamado} registrado como ACEITO.
⏰ Prazo de conclusão: {chamado.prazo_combinado.strftime('%d/%m/%Y às %H:%M')}

Para atualizar o status, envie:
*#STATUS ANDAMENTO* - Quando iniciar
*#STATUS CONCLUIDO* - Ao finalizar
"""
        return {'acao': 'responder', 'resposta': resposta}

    # Recusa
    elif texto_lower in ['nao', 'não', 'n', 'recuso', 'não posso']:
        chamado.status = 'recusado'
        db.session.delete(estado)
        db.session.commit()

        # NOTIFICA SOLICITANTE (Tarefa 4.1)
        RoteamentoService._notificar_solicitante_os_recusada(chamado, terceirizado)

        resposta = f"""❌ *CHAMADO RECUSADO*

Entendido. O chamado #{chamado.numero_chamado} foi marcado como RECUSADO.

O solicitante será notificado e outro prestador será acionado.

Obrigado!
"""
        return {'acao': 'responder', 'resposta': resposta}

    # Não entendeu
    else:
        resposta = "⚠️ Não entendi. Responda *SIM* para aceitar ou *NÃO* para recusar o chamado."
        return {'acao': 'responder', 'resposta': resposta}
```

**Critérios de Aceite:**
- ✅ Terceirizado recebe notificação com prazo
- ✅ Estado de conversa criado corretamente
- ✅ Respostas SIM/NÃO são processadas
- ✅ Status do chamado atualizado
- ✅ Estado limpo após confirmação

---

#### **Tarefa 2.2: Atualização de Status via Comandos**

**Arquivo:** `app/services/comando_parser.py` e `comando_executores.py`

**Ação:**
Expandir comandos para atualização de status:

```python
# comando_parser.py
class ComandoParser:
    @staticmethod
    def parse(texto: str) -> dict:
        # ... comandos existentes ...

        # Novo comando: #STATUS
        match = re.match(r'#STATUS\s+(ANDAMENTO|CONCLUIDO|PAUSADO)', texto.upper())
        if match:
            return {
                'comando': 'STATUS_UPDATE',
                'params': {'novo_status': match.group(1).lower()}
            }
```

```python
# comando_executores.py
class ComandoExecutores:
    @staticmethod
    def executar_status_update(params, terceirizado):
        """Atualiza status do último chamado ativo do terceirizado."""
        from app.models.terceirizados_models import ChamadoExterno
        from app.extensions import db

        # Busca último chamado aceito
        chamado = ChamadoExterno.query.filter_by(
            terceirizado_id=terceirizado.id
        ).filter(
            ChamadoExterno.status.in_(['aceito', 'em_andamento', 'pausado'])
        ).order_by(ChamadoExterno.criado_em.desc()).first()

        if not chamado:
            return {
                'sucesso': False,
                'resposta': "❌ Você não tem chamados ativos para atualizar."
            }

        novo_status = params['novo_status']
        status_map = {
            'andamento': 'em_andamento',
            'concluido': 'concluido',
            'pausado': 'pausado'
        }

        chamado.status = status_map.get(novo_status, chamado.status)

        if novo_status == 'concluido':
            chamado.data_conclusao = datetime.utcnow()
            # Inicia fluxo de conclusão (Tarefa 2.4)
            RoteamentoService._iniciar_fluxo_conclusao(terceirizado, chamado)

        db.session.commit()

        # NOTIFICA SOLICITANTE (Tarefa 4.2)
        RoteamentoService._notificar_solicitante_atualizacao(chamado, novo_status)

        resposta = f"""✅ *STATUS ATUALIZADO*

📋 Chamado: #{chamado.numero_chamado}
🔄 Novo Status: *{chamado.status.replace('_', ' ').upper()}*

O solicitante foi notificado.
"""
        return {'sucesso': True, 'resposta': resposta}
```

**Processamento no RoteamentoService:**

```python
# Em _processar_terceirizado()
comando = ComandoParser.parse(texto)
if comando:
    cmd_key = comando['comando']
    # ... comandos existentes ...
    elif cmd_key == 'STATUS_UPDATE':
        res = ComandoExecutores.executar_status_update(comando['params'], terceirizado)

    return {'acao': 'responder', 'resposta': res['resposta']}
```

**Critérios de Aceite:**
- ✅ Comando #STATUS ANDAMENTO funciona
- ✅ Comando #STATUS CONCLUIDO funciona
- ✅ Comando #STATUS PAUSADO funciona
- ✅ Status do chamado atualizado no banco
- ✅ Solicitante notificado da mudança

---

#### **Tarefa 2.3: Solicitação de Materiais**

**Arquivo:** `app/services/roteamento_service.py`

**Contexto:** Terceirizados precisam solicitar peças/materiais durante atendimento.

**Ação:**
Criar fluxo conversacional para solicitação:

```python
@staticmethod
def _iniciar_fluxo_solicitacao_peca(terceirizado):
    """Já existe parcialmente - expandir."""
    from app.extensions import db

    # Verifica se tem chamado ativo
    chamado_ativo = ChamadoExterno.query.filter_by(
        terceirizado_id=terceirizado.id,
        status='em_andamento'
    ).first()

    if not chamado_ativo:
        return {
            'acao': 'responder',
            'resposta': "⚠️ Você precisa ter um chamado ativo para solicitar peças.\n\nPrimeiro aceite um chamado ou inicie o atendimento."
        }

    estado = EstadoConversa(
        telefone=terceirizado.telefone,
        chamado_id=chamado_ativo.id,
        estado_atual='solicitacao_peca_codigo',
        contexto=json.dumps({
            'fluxo': 'solicitar_peca',
            'etapa': 'aguardando_codigo',
            'chamado_id': chamado_ativo.id
        }),
        usuario_tipo='terceirizado',
        usuario_id=terceirizado.id
    )
    db.session.add(estado)
    db.session.commit()

    mensagem = f"""📦 *SOLICITAÇÃO DE PEÇA*

📋 Chamado: #{chamado_ativo.numero_chamado}

Informe o código ou nome da peça necessária:

_Exemplo: ROL001 ou Rolamento 6205_
"""
    return {'acao': 'responder', 'resposta': mensagem}

@staticmethod
def _processar_solicitacao_peca(terceirizado, texto, estado):
    """Processa etapas do fluxo de solicitação."""
    from app.models.estoque_models import Estoque, PedidoCompra
    from app.extensions import db
    import json

    contexto = json.loads(estado.contexto)
    etapa = contexto['etapa']

    # Etapa 1: Código informado
    if etapa == 'aguardando_codigo':
        # Busca item no estoque
        item = Estoque.query.filter(
            db.or_(
                Estoque.codigo.ilike(f'%{texto}%'),
                Estoque.nome.ilike(f'%{texto}%')
            )
        ).first()

        if not item:
            return {
                'acao': 'responder',
                'resposta': f"❌ Item '{texto}' não encontrado no estoque.\n\nTente outro código ou nome."
            }

        # Atualiza contexto
        contexto['item_id'] = item.id
        contexto['item_nome'] = item.nome
        contexto['etapa'] = 'aguardando_quantidade'
        estado.contexto = json.dumps(contexto)
        estado.estado_atual = 'solicitacao_peca_quantidade'
        db.session.commit()

        return {
            'acao': 'responder',
            'resposta': f"""✅ Item encontrado: *{item.nome}*

📊 Estoque disponível: {item.quantidade_atual} {item.unidade_medida}

Informe a quantidade necessária:
"""
        }

    # Etapa 2: Quantidade informada
    elif etapa == 'aguardando_quantidade':
        try:
            quantidade = int(texto)
        except ValueError:
            return {
                'acao': 'responder',
                'resposta': "⚠️ Por favor, informe um número válido."
            }

        item = Estoque.query.get(contexto['item_id'])

        if quantidade > item.quantidade_atual:
            return {
                'acao': 'responder',
                'resposta': f"""⚠️ *QUANTIDADE INSUFICIENTE*

Solicitado: {quantidade} {item.unidade_medida}
Disponível: {item.quantidade_atual} {item.unidade_medida}

Deseja criar um pedido de compra? (SIM/NÃO)
"""
            }

        # Cria pedido de separação
        from app.models.models import Usuario
        chamado = ChamadoExterno.query.get(contexto['chamado_id'])

        pedido = PedidoCompra(
            estoque_id=item.id,
            quantidade=quantidade,
            solicitante_id=chamado.criado_por,  # Usuario que criou o chamado
            chamado_id=chamado.id,
            status='aguardando_separacao',
            observacoes=f'Solicitado por {terceirizado.nome} via WhatsApp'
        )
        db.session.add(pedido)
        db.session.delete(estado)
        db.session.commit()

        # NOTIFICA RESPONSÁVEL PELO ESTOQUE (Tarefa 4.3)
        RoteamentoService._notificar_estoque_separacao(pedido, terceirizado)

        return {
            'acao': 'responder',
            'resposta': f"""✅ *SOLICITAÇÃO REGISTRADA*

📦 Item: {item.nome}
📊 Quantidade: {quantidade} {item.unidade_medida}
📋 Pedido: #{pedido.id}

O setor de estoque foi notificado e separará o material em breve.

Você receberá confirmação quando estiver disponível para retirada.
"""
        }
```

**Critérios de Aceite:**
- ✅ Fluxo completo de solicitação funciona
- ✅ Validação de estoque em tempo real
- ✅ Criação de PedidoCompra automático
- ✅ Notificação ao responsável pelo estoque
- ✅ Confirmação ao terceirizado

---

#### **Tarefa 2.4: Template "OS Concluída" com Foto**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**
Criar fluxo de conclusão com solicitação de foto:

```python
@staticmethod
def _iniciar_fluxo_conclusao(terceirizado, chamado):
    """Inicia fluxo de conclusão solicitando foto."""
    from app.extensions import db
    import json

    estado = EstadoConversa(
        telefone=terceirizado.telefone,
        chamado_id=chamado.id,
        estado_atual='conclusao_aguardando_foto',
        contexto=json.dumps({
            'fluxo': 'conclusao_os',
            'etapa': 'aguardando_foto',
            'chamado_id': chamado.id
        }),
        usuario_tipo='terceirizado',
        usuario_id=terceirizado.id
    )
    db.session.add(estado)
    db.session.commit()

    mensagem = f"""📸 *CONCLUSÃO DE OS*

Para finalizar o chamado #{chamado.numero_chamado}, por favor envie:

1️⃣ Foto do serviço concluído (obrigatório)
2️⃣ Comentário final (opcional)

_Aguardando foto..._
"""

    from app.services.whatsapp_service import WhatsAppService
    WhatsAppService.enviar_mensagem(
        telefone=terceirizado.telefone,
        texto=mensagem,
        prioridade=1
    )

@staticmethod
def _processar_conclusao_foto(terceirizado, mensagem_webhook, estado):
    """Processa recebimento de foto de conclusão.

    Args:
        mensagem_webhook: Objeto do webhook contendo dados da mídia
    """
    from app.extensions import db
    from app.models.estoque_models import AnexosOS
    import json
    import requests

    contexto = json.loads(estado.contexto)
    chamado_id = contexto['chamado_id']
    chamado = ChamadoExterno.query.get(chamado_id)

    # 1. Verifica se mensagem contém mídia
    if not mensagem_webhook.get('media_url'):
        return {
            'acao': 'responder',
            'resposta': "⚠️ Por favor, envie uma foto do serviço concluído."
        }

    # 2. Baixa foto da MegaAPI
    media_url = mensagem_webhook['media_url']
    media_type = mensagem_webhook.get('media_type', 'image')

    if media_type != 'image':
        return {
            'acao': 'responder',
            'resposta': "⚠️ Por favor, envie uma *foto* (não áudio ou documento)."
        }

    try:
        # Download da imagem
        response = requests.get(media_url, timeout=30)
        response.raise_for_status()

        # Salva arquivo
        import os
        from werkzeug.utils import secure_filename

        upload_dir = f"app/static/uploads/chamados/{chamado_id}"
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"conclusao_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(response.content)

        # Registra anexo (adaptado para ChamadoExterno)
        # Nota: pode precisar criar modelo AnexosChamado similar a AnexosOS

        # 3. Atualiza contexto para aguardar comentário
        contexto['etapa'] = 'aguardando_comentario'
        contexto['foto_path'] = filepath
        estado.contexto = json.dumps(contexto)
        estado.estado_atual = 'conclusao_aguardando_comentario'
        db.session.commit()

        return {
            'acao': 'responder',
            'resposta': f"""✅ *FOTO RECEBIDA*

Agora envie um comentário final sobre o serviço realizado (ou digite PULAR):
"""
        }

    except Exception as e:
        logger.error(f"Erro ao processar foto: {str(e)}")
        return {
            'acao': 'responder',
            'resposta': "❌ Erro ao processar a foto. Tente enviar novamente."
        }

@staticmethod
def _processar_conclusao_comentario(terceirizado, texto, estado):
    """Processa comentário final e conclui chamado."""
    from app.extensions import db
    import json

    contexto = json.loads(estado.contexto)
    chamado_id = contexto['chamado_id']
    chamado = ChamadoExterno.query.get(chamado_id)

    # Atualiza chamado
    if texto.upper() != 'PULAR':
        chamado.feedback = texto

    chamado.status = 'concluido'
    chamado.data_conclusao = datetime.utcnow()

    db.session.delete(estado)
    db.session.commit()

    # NOTIFICA SOLICITANTE (Tarefa 4.4)
    RoteamentoService._notificar_solicitante_os_concluida(chamado, contexto.get('foto_path'))

    # Solicita avaliação
    return RoteamentoService._solicitar_avaliacao(terceirizado, chamado)

@staticmethod
def _solicitar_avaliacao(terceirizado, chamado):
    """Solicita avaliação do atendimento."""
    from app.extensions import db
    import json

    estado = EstadoConversa(
        telefone=terceirizado.telefone,
        chamado_id=chamado.id,
        estado_atual='aguardando_avaliacao',
        contexto=json.dumps({
            'fluxo': 'avaliacao',
            'chamado_id': chamado.id
        }),
        usuario_tipo='terceirizado',
        usuario_id=terceirizado.id
    )
    db.session.add(estado)
    db.session.commit()

    mensagem = f"""⭐ *AVALIAÇÃO DO ATENDIMENTO*

Como você avalia o suporte recebido para o chamado #{chamado.numero_chamado}?

Envie uma nota de 1 a 5:
⭐ 1 - Muito Ruim
⭐⭐ 2 - Ruim
⭐⭐⭐ 3 - Regular
⭐⭐⭐⭐ 4 - Bom
⭐⭐⭐⭐⭐ 5 - Excelente

Digite apenas o número (1 a 5):
"""
    return {'acao': 'responder', 'resposta': mensagem}
```

**Critérios de Aceite:**
- ✅ Foto obrigatória para conclusão
- ✅ Download e armazenamento de foto funciona
- ✅ Comentário opcional aceito
- ✅ Chamado marcado como concluído
- ✅ Solicitação de avaliação enviada

---

### **ETAPA 3: Respostas Automáticas para Terceirizados Especializados**

**Objetivo:** Criar respostas contextuais baseadas em especialidades do terceirizado.

#### **Tarefa 3.1: Menu Contextual por Especialidade**

**Arquivo:** `app/services/roteamento_service.py`

**Contexto:** Campo `Terceirizado.especialidades` armazena JSON com especialidades.

**Ação:**
Modificar menu inicial para incluir especialidades:

```python
@staticmethod
def _menu_terceirizado(terceirizado):
    """Menu adaptado às especialidades do terceirizado."""
    from app.services.whatsapp_service import WhatsAppService
    import json

    # Parse especialidades
    try:
        especialidades = json.loads(terceirizado.especialidades) if terceirizado.especialidades else []
    except:
        especialidades = []

    sections = [
        {
            "title": "Minhas Atividades",
            "rows": [
                {"id": "minhas_os", "title": "📋 Meus Chamados", "description": "Ver chamados atribuídos"},
                {"id": "os_disponiveis", "title": "🆕 Novos Chamados", "description": "Ver chamados disponíveis"}
            ]
        }
    ]

    # Adiciona seção de materiais se trabalha com manutenção
    if any(esp in especialidades for esp in ['Manutenção Elétrica', 'Manutenção Mecânica', 'Hidráulica']):
        sections.append({
            "title": "Materiais",
            "rows": [
                {"id": "solicitar_peca", "title": "📦 Solicitar Peça", "description": "Pedir material para serviço"},
                {"id": "consultar_estoque", "title": "📊 Ver Estoque", "description": "Consultar disponibilidade"}
            ]
        })

    # Adiciona seção de equipamentos se trabalha com equipamentos
    if 'Refrigeração' in especialidades or 'Ar Condicionado' in especialidades:
        sections.append({
            "title": "Equipamentos",
            "rows": [
                {"id": "diagnostico_rapido", "title": "🔍 Diagnóstico", "description": "Ferramenta de diagnóstico rápido"},
                {"id": "manual_tecnico", "title": "📖 Manuais", "description": "Acessar manuais técnicos"}
            ]
        })

    WhatsAppService.send_list_message(
        phone=terceirizado.telefone,
        header=f"🤖 ASSISTENTE GMM",
        body=f"""Olá {terceirizado.nome}!

🔧 Especialidades: {', '.join(especialidades) if especialidades else 'Geral'}

Como posso ajudar você hoje?""",
        sections=sections,
        button_text="Ver Opções"
    )

    return {'acao': 'aguardar_interacao'}
```

**Critérios de Aceite:**
- ✅ Especialidades lidas do JSON
- ✅ Menu adaptado dinamicamente
- ✅ Opções relevantes mostradas
- ✅ Funciona mesmo sem especialidades

---

#### **Tarefa 3.2: Notificação de Novas OS Disponíveis**

**Arquivo:** `app/tasks/whatsapp_tasks.py`

**Contexto:** Quando uma OS é criada sem técnico atribuído, notificar terceirizados qualificados.

**Ação:**
Criar task para notificação proativa:

```python
@celery.task
def notificar_terceirizados_os_disponivel(chamado_id):
    """Notifica terceirizados com especialidade compatível sobre nova OS."""
    from app.models.terceirizados_models import ChamadoExterno, Terceirizado
    from app.services.whatsapp_service import WhatsAppService
    import json

    chamado = ChamadoExterno.query.get(chamado_id)
    if not chamado:
        return

    # Busca terceirizados ativos com especialidade compatível
    # Assumindo que chamado tem campo 'especialidade_requerida'
    especialidade = chamado.especialidade_requerida or 'Geral'

    terceirizados = Terceirizado.query.filter_by(ativo=True).all()

    notificados = 0
    for terc in terceirizados:
        # Verifica especialidade
        try:
            especialidades = json.loads(terc.especialidades) if terc.especialidades else []
        except:
            especialidades = []

        if especialidade not in especialidades and especialidade != 'Geral':
            continue

        # Verifica abrangência
        if not terc.abrangencia_global:
            # Verifica se unidade está na lista de unidades do terceirizado
            if chamado.os_origem and chamado.os_origem.unidade_id:
                if chamado.os_origem.unidade not in terc.unidades:
                    continue

        # Envia notificação
        mensagem = f"""🆕 *NOVO CHAMADO DISPONÍVEL*

📋 #{chamado.numero_chamado}
📝 {chamado.titulo}
⏰ Prazo: {chamado.prazo_combinado.strftime('%d/%m/%Y %H:%M')}
🎯 Prioridade: {chamado.prioridade.upper()}
💰 Valor: R$ {chamado.valor_orcado or 0:.2f}

📍 Local: {chamado.os_origem.unidade.nome if chamado.os_origem else 'N/A'}

Deseja aceitar este chamado? Responda:
*SIM* - Aceito
*DETALHES* - Ver mais informações
"""

        # Cria estado de conversa
        from app.models.whatsapp_models import EstadoConversa
        from app.extensions import db

        estado = EstadoConversa(
            telefone=terc.telefone,
            chamado_id=chamado_id,
            estado_atual='oferta_os_disponivel',
            contexto=json.dumps({
                'fluxo': 'oferta_os',
                'chamado_id': chamado_id
            }),
            usuario_tipo='terceirizado',
            usuario_id=terc.id
        )
        db.session.add(estado)
        db.session.commit()

        WhatsAppService.enviar_mensagem(
            telefone=terc.telefone,
            texto=mensagem,
            prioridade=1
        )

        notificados += 1

    logger.info(f"Notificados {notificados} terceirizados sobre chamado {chamado_id}")
    return notificados
```

**Trigger da Notificação:**

```python
# Em app/routes/terceirizados.py (ao criar chamado)

@bp.route('/chamados/novo', methods=['POST'])
@login_required
def criar_chamado():
    # ... código de criação do chamado ...

    db.session.add(novo_chamado)
    db.session.commit()

    # Enfileira notificação proativa
    from app.tasks.whatsapp_tasks import notificar_terceirizados_os_disponivel
    notificar_terceirizados_os_disponivel.delay(novo_chamado.id)

    flash('Chamado criado! Terceirizados serão notificados.', 'success')
    return redirect(url_for('terceirizados.listar_chamados'))
```

**Critérios de Aceite:**
- ✅ Task enfileirada ao criar chamado
- ✅ Filtro por especialidade funciona
- ✅ Filtro por abrangência funciona
- ✅ Estado de conversa criado
- ✅ Notificação enviada com sucesso

---

#### **Tarefa 3.3: Agendamento de Visita**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**
Permitir que terceirizado agende visita:

```python
@staticmethod
def _iniciar_agendamento_visita(terceirizado, chamado_id):
    """Inicia fluxo de agendamento de visita."""
    from app.extensions import db
    import json

    estado = EstadoConversa(
        telefone=terceirizado.telefone,
        chamado_id=chamado_id,
        estado_atual='agendamento_data',
        contexto=json.dumps({
            'fluxo': 'agendamento',
            'chamado_id': chamado_id,
            'etapa': 'aguardando_data'
        }),
        usuario_tipo='terceirizado',
        usuario_id=terceirizado.id
    )
    db.session.add(estado)
    db.session.commit()

    mensagem = """📅 *AGENDAMENTO DE VISITA*

Informe a data e hora prevista para a visita:

Formato: DD/MM/AAAA HH:MM

_Exemplo: 15/01/2026 14:30_
"""
    return {'acao': 'responder', 'resposta': mensagem}

@staticmethod
def _processar_agendamento(terceirizado, texto, estado):
    """Processa data de agendamento."""
    from app.extensions import db
    from app.models.terceirizados_models import ChamadoExterno
    import json
    from datetime import datetime

    contexto = json.loads(estado.contexto)
    chamado_id = contexto['chamado_id']

    # Parse data
    try:
        data_visita = datetime.strptime(texto.strip(), '%d/%m/%Y %H:%M')
    except ValueError:
        return {
            'acao': 'responder',
            'resposta': "⚠️ Formato inválido. Use: DD/MM/AAAA HH:MM\n\n_Exemplo: 15/01/2026 14:30_"
        }

    # Valida se data é futura
    if data_visita < datetime.now():
        return {
            'acao': 'responder',
            'resposta': "⚠️ A data deve ser futura."
        }

    # Atualiza chamado
    chamado = ChamadoExterno.query.get(chamado_id)
    chamado.data_inicio = data_visita
    chamado.status = 'agendado'

    db.session.delete(estado)
    db.session.commit()

    # NOTIFICA SOLICITANTE (Tarefa 4.5)
    RoteamentoService._notificar_solicitante_agendamento(chamado, data_visita)

    return {
        'acao': 'responder',
        'resposta': f"""✅ *VISITA AGENDADA*

📅 Data: {data_visita.strftime('%d/%m/%Y às %H:%M')}
📋 Chamado: #{chamado.numero_chamado}

O solicitante foi notificado.

Você receberá um lembrete 1 dia antes.
"""
    }
```

**Critérios de Aceite:**
- ✅ Parsing de data funciona
- ✅ Validação de data futura
- ✅ Chamado atualizado com data
- ✅ Status alterado para "agendado"
- ✅ Solicitante notificado

---

### **ETAPA 4: Notificações Bidirecionais (Solicitante ↔ Terceirizado)**

**Objetivo:** Implementar encaminhamento automático de atualizações entre solicitantes e prestadores.

#### **Tarefa 4.1: Notificar Solicitante - OS Aceita/Recusada**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**
Criar métodos de notificação:

```python
@staticmethod
def _notificar_solicitante_os_aceita(chamado):
    """Notifica solicitante que terceirizado aceitou OS."""
    from app.services.whatsapp_service import WhatsAppService
    from app.models.models import Usuario

    # Busca solicitante
    solicitante = Usuario.query.get(chamado.criado_por)
    if not solicitante or not solicitante.telefone:
        logger.warning(f"Solicitante do chamado {chamado.id} não tem telefone cadastrado")
        return

    terceirizado = chamado.terceirizado

    mensagem = f"""✅ *CHAMADO ACEITO*

📋 Chamado #{chamado.numero_chamado} foi aceito!

👤 Prestador: {terceirizado.nome}
🏢 Empresa: {terceirizado.nome_empresa or 'N/A'}
📞 Telefone: {terceirizado.telefone}
⭐ Avaliação: {terceirizado.avaliacao_media or 'Sem avaliação'}

📝 Título: {chamado.titulo}
⏰ Aceito em: {chamado.data_inicio.strftime('%d/%m/%Y às %H:%M') if chamado.data_inicio else 'Agora'}

Você receberá atualizações sobre o andamento.
"""

    WhatsAppService.enviar_mensagem(
        telefone=solicitante.telefone,
        texto=mensagem,
        prioridade=1
    )

@staticmethod
def _notificar_solicitante_os_recusada(chamado, terceirizado):
    """Notifica solicitante que terceirizado recusou OS."""
    from app.services.whatsapp_service import WhatsAppService
    from app.models.models import Usuario

    solicitante = Usuario.query.get(chamado.criado_por)
    if not solicitante or not solicitante.telefone:
        return

    mensagem = f"""❌ *CHAMADO RECUSADO*

📋 Chamado #{chamado.numero_chamado}

O prestador {terceirizado.nome} recusou o atendimento.

🔄 Providências:
- Outro prestador será acionado automaticamente
- Você receberá notificação quando alguém aceitar

⏰ Aguarde contato em breve.
"""

    WhatsAppService.enviar_mensagem(
        telefone=solicitante.telefone,
        texto=mensagem,
        prioridade=1
    )

    # Re-notifica outros terceirizados
    from app.tasks.whatsapp_tasks import notificar_terceirizados_os_disponivel
    notificar_terceirizados_os_disponivel.delay(chamado.id)
```

**Critérios de Aceite:**
- ✅ Solicitante notificado ao aceite
- ✅ Solicitante notificado ao recusa
- ✅ Informações do terceirizado incluídas
- ✅ Re-notificação automática em caso de recusa

---

#### **Tarefa 4.2: Notificar Solicitante - Atualização de Status**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**

```python
@staticmethod
def _notificar_solicitante_atualizacao(chamado, novo_status):
    """Notifica solicitante sobre mudança de status."""
    from app.services.whatsapp_service import WhatsAppService
    from app.models.models import Usuario

    solicitante = Usuario.query.get(chamado.criado_por)
    if not solicitante or not solicitante.telefone:
        return

    status_emoji = {
        'em_andamento': '⚙️',
        'pausado': '⏸️',
        'concluido': '✅',
        'cancelado': '❌'
    }

    status_texto = {
        'em_andamento': 'EM ANDAMENTO',
        'pausado': 'PAUSADO',
        'concluido': 'CONCLUÍDO',
        'cancelado': 'CANCELADO'
    }

    emoji = status_emoji.get(novo_status, '🔄')
    texto_status = status_texto.get(novo_status, novo_status.upper())

    mensagem = f"""{emoji} *STATUS ATUALIZADO*

📋 Chamado: #{chamado.numero_chamado}
🔄 Novo Status: *{texto_status}*
👤 Prestador: {chamado.terceirizado.nome}

📝 {chamado.titulo}
"""

    # Adiciona informação contextual
    if novo_status == 'em_andamento':
        mensagem += "\n\n⚙️ O prestador iniciou o atendimento."
    elif novo_status == 'pausado':
        mensagem += "\n\n⏸️ O atendimento foi temporariamente pausado. Você será notificado quando retomar."
    elif novo_status == 'concluido':
        mensagem += "\n\n✅ Serviço concluído! Você receberá os detalhes em instantes."

    WhatsAppService.enviar_mensagem(
        telefone=solicitante.telefone,
        texto=mensagem,
        prioridade=1
    )
```

**Critérios de Aceite:**
- ✅ Notificação enviada em cada mudança de status
- ✅ Emoji e texto apropriados
- ✅ Informação contextual incluída

---

#### **Tarefa 4.3: Notificar Responsável - Solicitação de Material**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**

```python
@staticmethod
def _notificar_estoque_separacao(pedido, terceirizado):
    """Notifica responsável pelo estoque sobre solicitação de separação."""
    from app.services.whatsapp_service import WhatsAppService
    from app.models.models import Usuario

    # Busca usuários com perfil de almoxarife/estoque
    # Assumindo que há um tipo de usuário ou campo específico
    responsaveis = Usuario.query.filter(
        Usuario.tipo.in_(['admin', 'estoque']),
        Usuario.ativo == True,
        Usuario.telefone.isnot(None)
    ).all()

    if not responsaveis:
        logger.warning("Nenhum responsável de estoque com telefone cadastrado")
        return

    item = pedido.estoque
    chamado = pedido.chamado

    mensagem = f"""📦 *SOLICITAÇÃO DE SEPARAÇÃO*

📋 Pedido: #{pedido.id}
👤 Solicitante: {terceirizado.nome}
📞 Telefone: {terceirizado.telefone}

🔧 Chamado Relacionado: #{chamado.numero_chamado if chamado else 'N/A'}

📦 *Item Solicitado:*
Código: {item.codigo}
Nome: {item.nome}
Quantidade: {pedido.quantidade} {item.unidade_medida}

📊 Estoque Atual: {item.quantidade_atual} {item.unidade_medida}

⚠️ Por favor, separe o material para retirada.

Para confirmar separação, acesse o sistema ou responda:
*#SEPARADO {pedido.id}*
"""

    for responsavel in responsaveis:
        WhatsAppService.enviar_mensagem(
            telefone=responsavel.telefone,
            texto=mensagem,
            prioridade=1
        )
```

**Comando de Confirmação:**

```python
# Em comando_parser.py
match = re.match(r'#SEPARADO\s+(\d+)', texto.upper())
if match:
    return {
        'comando': 'CONFIRMAR_SEPARACAO',
        'params': {'pedido_id': int(match.group(1))}
    }

# Em comando_executores.py
@staticmethod
def executar_confirmar_separacao(params, usuario):
    """Confirma separação de material."""
    from app.models.estoque_models import PedidoCompra
    from app.extensions import db
    from app.services.whatsapp_service import WhatsAppService

    pedido_id = params['pedido_id']
    pedido = PedidoCompra.query.get(pedido_id)

    if not pedido:
        return {'sucesso': False, 'resposta': "❌ Pedido não encontrado."}

    if pedido.status != 'aguardando_separacao':
        return {'sucesso': False, 'resposta': f"⚠️ Pedido já processado (Status: {pedido.status})."}

    # Atualiza status
    pedido.status = 'separado'
    pedido.separado_por = usuario.id
    pedido.data_separacao = datetime.utcnow()
    db.session.commit()

    # Notifica terceirizado que solicitou
    if pedido.chamado and pedido.chamado.terceirizado:
        terceirizado = pedido.chamado.terceirizado
        notif_terc = f"""✅ *MATERIAL SEPARADO*

📦 Pedido #{pedido.id}
📦 Item: {pedido.estoque.nome}
📊 Quantidade: {pedido.quantidade} {pedido.estoque.unidade_medida}

✅ Material disponível para retirada.

📍 Retire no almoxarifado.
"""
        WhatsAppService.enviar_mensagem(
            telefone=terceirizado.telefone,
            texto=notif_terc,
            prioridade=1
        )

    return {
        'sucesso': True,
        'resposta': f"""✅ *SEPARAÇÃO CONFIRMADA*

📦 Pedido #{pedido.id}
📦 {pedido.estoque.nome}

O solicitante foi notificado.
"""
    }
```

**Critérios de Aceite:**
- ✅ Responsáveis de estoque notificados
- ✅ Comando #SEPARADO funciona
- ✅ Status atualizado no pedido
- ✅ Terceirizado notificado da separação

---

#### **Tarefa 4.4: Notificar Solicitante - OS Concluída com Foto**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**

```python
@staticmethod
def _notificar_solicitante_os_concluida(chamado, foto_path=None):
    """Notifica solicitante da conclusão com foto anexa."""
    from app.services.whatsapp_service import WhatsAppService
    from app.models.models import Usuario

    solicitante = Usuario.query.get(chamado.criado_por)
    if not solicitante or not solicitante.telefone:
        return

    # Mensagem principal
    caption = f"""✅ *CHAMADO CONCLUÍDO*

📋 #{chamado.numero_chamado}
📝 {chamado.titulo}

👤 Prestador: {chamado.terceirizado.nome}
📅 Concluído em: {chamado.data_conclusao.strftime('%d/%m/%Y às %H:%M')}

💬 *Comentário Final:*
{chamado.feedback or 'Sem comentário.'}

📸 Foto do serviço concluído em anexo.

⭐ *Avalie o atendimento:*
Para avaliar, responda com nota de 1 a 5.
"""

    # Envia com foto se disponível
    if foto_path:
        import os
        if os.path.exists(foto_path):
            WhatsAppService.enviar_mensagem(
                telefone=solicitante.telefone,
                texto=caption,
                prioridade=1,
                arquivo_path=foto_path,
                tipo_midia='image',
                caption=caption
            )
        else:
            # Fallback sem foto
            WhatsAppService.enviar_mensagem(
                telefone=solicitante.telefone,
                texto=caption.replace('📸 Foto do serviço concluído em anexo.', ''),
                prioridade=1
            )
    else:
        WhatsAppService.enviar_mensagem(
            telefone=solicitante.telefone,
            texto=caption.replace('📸 Foto do serviço concluído em anexo.', ''),
            prioridade=1
        )

    # Cria estado para aguardar avaliação
    from app.models.whatsapp_models import EstadoConversa
    from app.extensions import db
    import json

    estado = EstadoConversa(
        telefone=solicitante.telefone,
        chamado_id=chamado.id,
        estado_atual='aguardando_avaliacao_solicitante',
        contexto=json.dumps({
            'fluxo': 'avaliacao_solicitante',
            'chamado_id': chamado.id
        }),
        usuario_tipo='usuario',
        usuario_id=solicitante.id
    )
    db.session.add(estado)
    db.session.commit()
```

**Processamento da Avaliação:**

```python
@staticmethod
def _processar_avaliacao_solicitante(usuario, texto, estado):
    """Processa avaliação do solicitante."""
    from app.extensions import db
    from app.models.terceirizados_models import ChamadoExterno, Terceirizado
    import json

    contexto = json.loads(estado.contexto)
    chamado_id = contexto['chamado_id']
    chamado = ChamadoExterno.query.get(chamado_id)

    # Parse nota
    try:
        nota = int(texto.strip())
        if nota < 1 or nota > 5:
            raise ValueError
    except ValueError:
        return {
            'acao': 'responder',
            'resposta': "⚠️ Por favor, envie uma nota de 1 a 5."
        }

    # Registra avaliação
    chamado.avaliacao = nota

    # Atualiza média do terceirizado
    terceirizado = chamado.terceirizado
    chamados_avaliados = ChamadoExterno.query.filter_by(
        terceirizado_id=terceirizado.id
    ).filter(ChamadoExterno.avaliacao.isnot(None)).all()

    if chamados_avaliados:
        media = sum(c.avaliacao for c in chamados_avaliados) / len(chamados_avaliados)
        terceirizado.avaliacao_media = round(media, 2)

    db.session.delete(estado)
    db.session.commit()

    # Agradecimento
    estrelas = '⭐' * nota
    resposta = f"""{estrelas} *AVALIAÇÃO REGISTRADA*

Obrigado por avaliar!

Sua nota: {nota}/5

Sua opinião nos ajuda a melhorar nossos serviços.
"""

    return {'acao': 'responder', 'resposta': resposta}
```

**Critérios de Aceite:**
- ✅ Foto enviada junto com mensagem
- ✅ Estado de avaliação criado
- ✅ Avaliação processada corretamente
- ✅ Média do terceirizado atualizada

---

#### **Tarefa 4.5: Notificar Solicitante - Agendamento**

**Arquivo:** `app/services/roteamento_service.py`

**Ação:**

```python
@staticmethod
def _notificar_solicitante_agendamento(chamado, data_visita):
    """Notifica solicitante sobre agendamento de visita."""
    from app.services.whatsapp_service import WhatsAppService
    from app.models.models import Usuario

    solicitante = Usuario.query.get(chamado.criado_por)
    if not solicitante or not solicitante.telefone:
        return

    mensagem = f"""📅 *VISITA AGENDADA*

📋 Chamado: #{chamado.numero_chamado}
👤 Prestador: {chamado.terceirizado.nome}
📞 Contato: {chamado.terceirizado.telefone}

📅 *Data e Hora:*
{data_visita.strftime('%d/%m/%Y às %H:%M')}

📍 Local: {chamado.os_origem.unidade.nome if chamado.os_origem else 'Conforme chamado'}

⚠️ Certifique-se de que haverá alguém no local para receber o prestador.

Você receberá um lembrete 1 dia antes.
"""

    WhatsAppService.enviar_mensagem(
        telefone=solicitante.telefone,
        texto=mensagem,
        prioridade=1
    )

    # Agenda lembrete (Celery Beat ou task com countdown)
    from app.tasks.whatsapp_tasks import enviar_lembrete_agendamento
    data_lembrete = data_visita - timedelta(days=1)
    countdown_seconds = (data_lembrete - datetime.utcnow()).total_seconds()

    if countdown_seconds > 0:
        enviar_lembrete_agendamento.apply_async(
            args=[chamado.id, 'solicitante'],
            countdown=countdown_seconds
        )
        enviar_lembrete_agendamento.apply_async(
            args=[chamado.id, 'terceirizado'],
            countdown=countdown_seconds
        )
```

**Task de Lembrete:**

```python
# Em app/tasks/whatsapp_tasks.py

@celery.task
def enviar_lembrete_agendamento(chamado_id, destinatario_tipo):
    """Envia lembrete de visita agendada."""
    from app.models.terceirizados_models import ChamadoExterno
    from app.services.whatsapp_service import WhatsAppService

    chamado = ChamadoExterno.query.get(chamado_id)
    if not chamado or not chamado.data_inicio:
        return

    if destinatario_tipo == 'solicitante':
        from app.models.models import Usuario
        usuario = Usuario.query.get(chamado.criado_por)
        if not usuario or not usuario.telefone:
            return

        mensagem = f"""⏰ *LEMBRETE - VISITA AMANHÃ*

📋 Chamado: #{chamado.numero_chamado}
👤 Prestador: {chamado.terceirizado.nome}

📅 Visita agendada para:
{chamado.data_inicio.strftime('%d/%m/%Y às %H:%M')}

Lembre-se de providenciar acesso ao local.
"""
        telefone = usuario.telefone

    elif destinatario_tipo == 'terceirizado':
        mensagem = f"""⏰ *LEMBRETE - VISITA AMANHÃ*

📋 Chamado: #{chamado.numero_chamado}

📅 Visita agendada para:
{chamado.data_inicio.strftime('%d/%m/%Y às %H:%M')}

📍 Local: {chamado.os_origem.unidade.endereco if chamado.os_origem else 'Conforme chamado'}

Boa sorte!
"""
        telefone = chamado.terceirizado.telefone

    else:
        return

    WhatsAppService.enviar_mensagem(
        telefone=telefone,
        texto=mensagem,
        prioridade=1
    )
```

**Critérios de Aceite:**
- ✅ Solicitante notificado do agendamento
- ✅ Lembrete agendado corretamente
- ✅ Lembrete enviado 24h antes
- ✅ Ambos (solicitante e terceirizado) recebem lembrete

---

### **ETAPA 5: Templates e Padronização**

**Objetivo:** Criar sistema de templates reutilizáveis para mensagens.

#### **Tarefa 5.1: Criar Serviço de Templates**

**Arquivo:** `app/services/template_service.py` (já existe, expandir)

**Ação:**

```python
# app/services/template_service.py

class TemplateService:
    """Gerencia templates de mensagens WhatsApp."""

    TEMPLATES = {
        # Terceirizados
        'terceirizado.os_nova': """🔔 *NOVA ORDEM DE SERVIÇO*

📋 *Chamado:* #{numero_chamado}
📝 *Título:* {titulo}
⏰ *Prazo:* {prazo}
🎯 *Prioridade:* {prioridade}

📄 *Descrição:*
{descricao}

⚠️ Confirme o recebimento:
*SIM* - Aceito
*NÃO* - Não posso
""",

        'terceirizado.os_aceita': """✅ *CHAMADO ACEITO*

Obrigado, {nome}!

📋 #{numero_chamado} registrado como ACEITO.
⏰ Prazo: {prazo}

Comandos úteis:
*#STATUS ANDAMENTO* - Iniciar
*#STATUS CONCLUIDO* - Finalizar
""",

        'terceirizado.material_disponivel': """✅ *MATERIAL SEPARADO*

📦 Pedido #{pedido_id}
📦 Item: {item_nome}
📊 Quantidade: {quantidade} {unidade}

✅ Disponível para retirada.
📍 Retire no almoxarifado.
""",

        # Usuários/Solicitantes
        'solicitante.os_aceita': """✅ *CHAMADO ACEITO*

📋 #{numero_chamado}

👤 Prestador: {prestador_nome}
🏢 Empresa: {prestador_empresa}
📞 Telefone: {prestador_telefone}
⭐ Avaliação: {prestador_avaliacao}

📝 {titulo}
⏰ Aceito em: {data_aceite}

Você receberá atualizações.
""",

        'solicitante.status_atualizado': """{emoji} *STATUS ATUALIZADO*

📋 #{numero_chamado}
🔄 Novo Status: *{status}*
👤 Prestador: {prestador_nome}

{mensagem_contexto}
""",

        'solicitante.os_concluida': """✅ *CHAMADO CONCLUÍDO*

📋 #{numero_chamado}
📝 {titulo}

👤 Prestador: {prestador_nome}
📅 Concluído em: {data_conclusao}

💬 *Comentário:*
{feedback}

⭐ Avalie de 1 a 5:
""",

        # Estoque/Admin
        'estoque.solicitacao_separacao': """📦 *SOLICITAÇÃO DE SEPARAÇÃO*

📋 Pedido: #{pedido_id}
👤 Solicitante: {solicitante_nome}
📞 {solicitante_telefone}

📦 *Item:*
{item_codigo} - {item_nome}
Qtd: {quantidade} {unidade}

📊 Estoque: {estoque_atual} {unidade}

Confirme: *#SEPARADO {pedido_id}*
""",

        # Lembretes
        'lembrete.visita_solicitante': """⏰ *LEMBRETE - VISITA AMANHÃ*

📋 #{numero_chamado}
👤 Prestador: {prestador_nome}

📅 {data_hora}

Providencie acesso ao local.
""",

        'lembrete.visita_terceirizado': """⏰ *LEMBRETE - VISITA AMANHÃ*

📋 #{numero_chamado}

📅 {data_hora}
📍 {endereco}

Boa sorte!
"""
    }

    @staticmethod
    def renderizar(template_key: str, **kwargs) -> str:
        """
        Renderiza template com variáveis.

        Args:
            template_key: Chave do template (ex: 'terceirizado.os_nova')
            **kwargs: Variáveis para substituição

        Returns:
            str: Mensagem renderizada
        """
        template = TemplateService.TEMPLATES.get(template_key)
        if not template:
            logger.error(f"Template '{template_key}' não encontrado")
            return ""

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Variável ausente no template '{template_key}': {str(e)}")
            return template

    @staticmethod
    def listar_templates() -> list:
        """Retorna lista de templates disponíveis."""
        return list(TemplateService.TEMPLATES.keys())
```

**Uso:**

```python
# Exemplo em roteamento_service.py

from app.services.template_service import TemplateService

mensagem = TemplateService.renderizar(
    'terceirizado.os_nova',
    numero_chamado=chamado.numero_chamado,
    titulo=chamado.titulo,
    prazo=chamado.prazo_combinado.strftime('%d/%m/%Y %H:%M'),
    prioridade=chamado.prioridade.upper(),
    descricao=chamado.descricao
)
```

**Critérios de Aceite:**
- ✅ Todos os templates definidos
- ✅ Método renderizar funciona
- ✅ Tratamento de erro para variáveis ausentes
- ✅ Templates usados em todo o código

---

#### **Tarefa 5.2: Criar Regras de Automação Padrão**

**Arquivo:** `gmm/seed_regras_automacao.py` (novo)

**Ação:**
Criar script para popular regras padrão:

```python
# seed_regras_automacao.py

from app import create_app
from app.extensions import db
from app.models.whatsapp_models import RegrasAutomacao

def seed_regras():
    """Popula regras de automação padrão."""
    app = create_app()
    with app.app_context():
        regras_padrao = [
            {
                'palavra_chave': 'AJUDA',
                'tipo_correspondencia': 'exata',
                'acao': 'responder',
                'resposta_texto': """🤖 *COMANDOS DISPONÍVEIS*

*Para Terceirizados:*
• #STATUS ANDAMENTO - Iniciar atendimento
• #STATUS CONCLUIDO - Finalizar chamado
• #STATUS PAUSADO - Pausar atendimento
• EQUIP:ID - Ver equipamento via QR Code

*Para Usuários:*
• Digite o número da opção do menu
• Responda às perguntas do assistente

*Comandos Gerais:*
• AJUDA - Ver esta mensagem
• MENU - Voltar ao menu inicial
""",
                'prioridade': 100,
                'ativo': True
            },
            {
                'palavra_chave': 'MENU',
                'tipo_correspondencia': 'exata',
                'acao': 'executar_funcao',
                'funcao_sistema': 'exibir_menu_principal',
                'prioridade': 90,
                'ativo': True
            },
            {
                'palavra_chave': 'BOM DIA',
                'tipo_correspondencia': 'contem',
                'acao': 'responder',
                'resposta_texto': 'Bom dia! 👋 Como posso ajudar você hoje? Digite MENU para ver as opções.',
                'prioridade': 10,
                'ativo': True
            },
            {
                'palavra_chave': 'BOA TARDE',
                'tipo_correspondencia': 'contem',
                'acao': 'responder',
                'resposta_texto': 'Boa tarde! 👋 Como posso ajudar você hoje? Digite MENU para ver as opções.',
                'prioridade': 10,
                'ativo': True
            },
            {
                'palavra_chave': 'BOA NOITE',
                'tipo_correspondencia': 'contem',
                'acao': 'responder',
                'resposta_texto': 'Boa noite! 👋 Como posso ajudar você hoje? Digite MENU para ver as opções.',
                'prioridade': 10,
                'ativo': True
            },
            {
                'palavra_chave': 'OI|OLA|OLÁ',
                'tipo_correspondencia': 'regex',
                'acao': 'responder',
                'resposta_texto': 'Olá! 👋 Bem-vindo ao sistema GMM. Digite MENU para ver as opções disponíveis.',
                'prioridade': 10,
                'ativo': True
            },
            {
                'palavra_chave': 'OBRIGADO|OBRIGADA',
                'tipo_correspondencia': 'regex',
                'acao': 'responder',
                'resposta_texto': 'De nada! 😊 Estou aqui para ajudar. Digite MENU se precisar de algo mais.',
                'prioridade': 5,
                'ativo': True
            }
        ]

        for regra_data in regras_padrao:
            # Verifica se já existe
            existe = RegrasAutomacao.query.filter_by(
                palavra_chave=regra_data['palavra_chave']
            ).first()

            if not existe:
                regra = RegrasAutomacao(**regra_data)
                db.session.add(regra)
                print(f"✅ Regra criada: {regra_data['palavra_chave']}")
            else:
                print(f"⚠️  Regra já existe: {regra_data['palavra_chave']}")

        db.session.commit()
        print("\n✅ Seed de regras concluído!")

if __name__ == '__main__':
    seed_regras()
```

**Execução:**

```bash
python gmm/seed_regras_automacao.py
```

**Critérios de Aceite:**
- ✅ Script executa sem erros
- ✅ Regras padrão criadas
- ✅ Não duplica regras existentes
- ✅ Regras funcionam no sistema

---

## 5. CRONOGRAMA DE IMPLEMENTAÇÃO

### **Sprint 1 (2 semanas) - Fundação**
- ✅ Tarefa 1.1: Expandir identificação de remetentes
- ✅ Tarefa 1.2: Criar fluxo para usuários internos
- ✅ Tarefa 1.3: Implementar estado de conversa
- ✅ Tarefa 5.1: Criar serviço de templates
- ✅ Tarefa 5.2: Seed de regras padrão

**Entregável:** Sistema reconhece e responde usuários internos com menus básicos.

---

### **Sprint 2 (2 semanas) - Fornecedores**
- ✅ Tarefa 2.1: Confirmação automática de OS
- ✅ Tarefa 2.2: Atualização de status via comandos
- ✅ Tarefa 4.1: Notificar solicitante (aceite/recusa)
- ✅ Tarefa 4.2: Notificar solicitante (status)

**Entregável:** Fluxo completo de confirmação e atualização de OS funcionando.

---

### **Sprint 3 (2 semanas) - Materiais e Conclusão**
- ✅ Tarefa 2.3: Solicitação de materiais
- ✅ Tarefa 2.4: Template de conclusão com foto
- ✅ Tarefa 4.3: Notificar estoque
- ✅ Tarefa 4.4: Notificar conclusão com foto

**Entregável:** Gestão de materiais e conclusão com foto implementadas.

---

### **Sprint 4 (2 semanas) - Terceirizados e Agendamento**
- ✅ Tarefa 3.1: Menu contextual por especialidade
- ✅ Tarefa 3.2: Notificação de OS disponíveis
- ✅ Tarefa 3.3: Agendamento de visita
- ✅ Tarefa 4.5: Notificar agendamento e lembretes

**Entregável:** Sistema completo de gestão de terceirizados com proatividade.

---

## 6. TESTES E VALIDAÇÃO

### **6.1 Casos de Teste**

#### **CT-01: Reconhecimento de Usuário Interno**
- **Dado:** Usuário interno envia mensagem
- **Quando:** Sistema identifica telefone
- **Então:** Menu apropriado ao perfil é exibido

#### **CT-02: Confirmação de OS por Terceirizado**
- **Dado:** Terceirizado recebe notificação de nova OS
- **Quando:** Responde "SIM"
- **Então:** Status atualizado e solicitante notificado

#### **CT-03: Solicitação de Material**
- **Dado:** Terceirizado em atendimento
- **Quando:** Solicita peça via fluxo
- **Então:** Pedido criado e estoque notificado

#### **CT-04: Conclusão com Foto**
- **Dado:** Terceirizado finaliza chamado
- **Quando:** Envia #STATUS CONCLUIDO
- **Então:** Foto solicitada, recebida e enviada ao solicitante

#### **CT-05: Avaliação Bidirecional**
- **Dado:** OS concluída
- **Quando:** Solicitante avalia
- **Então:** Média do terceirizado atualizada

### **6.2 Testes de Integração**

```python
# tests/integration/test_respostas_automaticas.py

def test_usuario_interno_recebe_menu():
    """Testa que usuário interno recebe menu apropriado."""
    pass

def test_confirmacao_os_terceirizado():
    """Testa fluxo de confirmação de OS."""
    pass

def test_notificacao_bidirecional():
    """Testa que solicitante é notificado de ações do terceirizado."""
    pass
```

---

## 7. MÉTRICAS DE SUCESSO

### **KPIs**

1. **Taxa de Resposta Automática:** > 80% das mensagens respondidas sem intervenção humana
2. **Tempo Médio de Confirmação:** < 30 minutos para aceite/recusa de OS
3. **Taxa de Conclusão com Foto:** > 90% das OS concluídas com foto anexa
4. **Satisfação (NPS):** Média de avaliação > 4.0/5.0
5. **Redução de Chamadas Telefônicas:** 50% de redução em contatos telefônicos

### **Monitoramento**

- Dashboard com métricas em tempo real
- Alertas para taxa de resposta < 70%
- Relatório semanal de eficiência do bot

---

## 8. RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| MegaAPI instável | Média | Alto | Circuit Breaker + fallback SMS |
| Usuários não entendem bot | Alta | Médio | Mensagens claras + comando AJUDA |
| Fotos muito grandes | Média | Baixo | Validação de tamanho (max 5MB) |
| Spam de mensagens | Baixa | Alto | Rate limiting por usuário |
| Conflito de estados | Média | Médio | TTL de 24h + limpeza automática |

---

## 9. DOCUMENTAÇÃO ADICIONAL

### **9.1 Atualizar CLAUDE.md**

Adicionar seção sobre respostas automáticas:

```markdown
## WhatsApp - Respostas Automáticas

### Tipos de Usuário Reconhecidos
- **Terceirizados:** Menu com chamados, materiais, equipamentos
- **Usuários Admin:** Aprovações, relatórios, status do sistema
- **Usuários Técnicos:** Minhas OS, solicitar peças, consultar estoque
- **Usuários Comuns:** Abrir chamados, consultar status

### Templates Disponíveis
Use `TemplateService.renderizar(template_key, **kwargs)` para mensagens padronizadas.

### Comandos Principais
- `#STATUS ANDAMENTO/CONCLUIDO/PAUSADO` - Atualizar status
- `#SEPARADO {id}` - Confirmar separação de material
- `EQUIP:{id}` - Acessar equipamento via QR Code
- `MENU` - Voltar ao menu principal
- `AJUDA` - Ver comandos disponíveis
```

### **9.2 Atualizar README**

Adicionar seção de uso para terceirizados e usuários.

---

## 10. CONCLUSÃO

Este PRD detalha a expansão completa do sistema de respostas automáticas WhatsApp do GMM, com foco em:

✅ **Reconhecimento universal** de usuários (internos e externos)
✅ **Fluxos bidirecionais** entre solicitantes e prestadores
✅ **Automação inteligente** com validações e contexto
✅ **Templates reutilizáveis** para manutenibilidade
✅ **Notificações proativas** baseadas em eventos

**Resultado esperado:** Redução de 50% em contatos telefônicos e aumento de 80% na taxa de resposta automática, com satisfação média > 4.0/5.0.

---

**Próximos Passos:**
1. Revisar e aprovar PRD
2. Criar issues/tasks no GitHub
3. Iniciar Sprint 1
4. Configurar monitoramento de métricas
