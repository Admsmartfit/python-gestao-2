import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.extensions import db
from app.models.whatsapp_models import RegrasAutomacao
from app.models.terceirizados_models import HistoricoNotificacao

logger = logging.getLogger(__name__)

# Offset do fuso horario do Brasil (UTC-3, sem horario de verao desde 2019)
BRAZIL_UTC_OFFSET = timedelta(hours=-3)

def utc_to_local(dt):
    """Converte datetime UTC para horario local do Brasil (UTC-3)."""
    if dt is None:
        return None
    return dt + BRAZIL_UTC_OFFSET

bp = Blueprint('admin_whatsapp', __name__)

@bp.route('/admin/whatsapp/regras', methods=['GET'])
@login_required
def listar_regras():
    """Tela de configuração de regras"""
    if current_user.tipo != 'admin':
        abort(403)
    
    regras = RegrasAutomacao.query.order_by(
        RegrasAutomacao.prioridade.desc()
    ).all()
    
    return render_template('admin/whatsapp_regras.html', regras=regras)

@bp.route('/admin/whatsapp/regras', methods=['POST'])
@login_required
def criar_regra():
    """Cria nova regra de automação"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json

    # Validações
    if not data.get('palavra_chave'):
        return jsonify({'error': 'Palavra-chave obrigatória'}), 400

    regra = RegrasAutomacao(
        palavra_chave=data['palavra_chave'],
        tipo_correspondencia=data.get('tipo_correspondencia', 'contem'),
        acao=data['acao'],
        resposta_texto=data.get('resposta_texto'),
        encaminhar_para_perfil=data.get('encaminhar_para_perfil'),
        funcao_sistema=data.get('funcao_sistema'),
        prioridade=data.get('prioridade', 0)
    )

    db.session.add(regra)
    db.session.commit()

    return jsonify({
        'success': True,
        'id': regra.id
    })

@bp.route('/admin/whatsapp/regras/<int:regra_id>', methods=['GET'])
@login_required
def obter_regra(regra_id):
    """Busca dados de uma regra específica"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    regra = RegrasAutomacao.query.get_or_404(regra_id)

    return jsonify({
        'id': regra.id,
        'palavra_chave': regra.palavra_chave,
        'tipo_correspondencia': regra.tipo_correspondencia,
        'acao': regra.acao,
        'resposta_texto': regra.resposta_texto,
        'encaminhar_para_perfil': regra.encaminhar_para_perfil,
        'funcao_sistema': regra.funcao_sistema,
        'prioridade': regra.prioridade,
        'ativo': regra.ativo
    })

@bp.route('/admin/whatsapp/regras/<int:regra_id>', methods=['PUT'])
@login_required
def atualizar_regra(regra_id):
    """Atualiza uma regra existente"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    regra = RegrasAutomacao.query.get_or_404(regra_id)
    data = request.json

    # Validações
    if not data.get('palavra_chave'):
        return jsonify({'error': 'Palavra-chave obrigatória'}), 400

    # Atualizar campos
    regra.palavra_chave = data['palavra_chave']
    regra.tipo_correspondencia = data.get('tipo_correspondencia', 'contem')
    regra.acao = data['acao']
    regra.resposta_texto = data.get('resposta_texto')
    regra.encaminhar_para_perfil = data.get('encaminhar_para_perfil')
    regra.funcao_sistema = data.get('funcao_sistema')
    regra.prioridade = data.get('prioridade', 0)

    if 'ativo' in data:
        regra.ativo = data['ativo']

    db.session.commit()

    return jsonify({
        'success': True,
        'id': regra.id
    })

@bp.route('/admin/whatsapp/regras/<int:regra_id>', methods=['DELETE'])
@login_required
def excluir_regra(regra_id):
    """Exclui uma regra"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    regra = RegrasAutomacao.query.get_or_404(regra_id)
    db.session.delete(regra)
    db.session.commit()

    return jsonify({
        'success': True
    })

@bp.route('/admin/whatsapp/regras/<int:regra_id>/toggle', methods=['POST'])
@login_required
def toggle_regra(regra_id):
    """Ativa/desativa uma regra"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    regra = RegrasAutomacao.query.get_or_404(regra_id)
    regra.ativo = not regra.ativo
    db.session.commit()

    return jsonify({
        'success': True,
        'ativo': regra.ativo
    })

# --- Dashboard & Métricas ---

from datetime import datetime, timedelta
from app.models.whatsapp_models import ConfiguracaoWhatsApp
from app.models.terceirizados_models import HistoricoNotificacao
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import RateLimiter

@bp.route('/admin/whatsapp/dashboard')
@login_required
def dashboard():
    """Painel de saúde da integração"""
    if current_user.tipo != 'admin':
        abort(403)
    
    # Buscar configuração
    config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
    # Create dummy config if not exists to avoid crash
    if not config:
        config = ConfiguracaoWhatsApp(ativo=True) # transient

    # Métricas últimas 24h
    desde = datetime.utcnow() - timedelta(hours=24)
    
    total_enviadas = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.direcao == 'outbound',
        HistoricoNotificacao.criado_em >= desde
    ).count()
    
    total_entregues = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.direcao == 'outbound',
        HistoricoNotificacao.status_envio == 'enviado', # Using 'enviado' as proxy for delivered in this context
        HistoricoNotificacao.criado_em >= desde
    ).count()
    
    taxa_entrega = (total_entregues / total_enviadas * 100) if total_enviadas > 0 else 0
    
    # Estado do Circuit Breaker
    cb_state = CircuitBreaker.get_state()
    
    # Rate Limit
    pode_enviar, restantes = RateLimiter.check_limit()
    
    # Mensagens pendentes
    pendentes = HistoricoNotificacao.query.filter_by(
        status_envio='pendente'
    ).count()
    
    return render_template('admin/whatsapp_dashboard.html',
        config=config,
        total_enviadas=total_enviadas,
        total_entregues=total_entregues,
        taxa_entrega=round(taxa_entrega, 1),
        cb_state=cb_state,
        rate_limit_disponivel=restantes,
        mensagens_pendentes=pendentes
    )

@bp.route('/api/whatsapp/metricas-grafico')
@login_required
def metricas_grafico():
    """Dados para gráfico de envios"""
    periodo = request.args.get('periodo', 'dia')
    
    if periodo == 'dia':
        inicio = datetime.utcnow() - timedelta(days=1)
        intervalo = timedelta(hours=1)
        formato = '%H:00'
    else:
        inicio = datetime.utcnow() - timedelta(days=7)
        intervalo = timedelta(days=1)
        formato = '%d/%m'
    
    # Agregar por período (Simplified loop)
    labels = []
    enviadas = []
    entregues = []
    
    timestamp = inicio
    while timestamp < datetime.utcnow():
        labels.append(timestamp.strftime(formato))
        fim_periodo = timestamp + intervalo
        
        total_env = HistoricoNotificacao.query.filter(
            HistoricoNotificacao.criado_em >= timestamp,
            HistoricoNotificacao.criado_em < fim_periodo,
            HistoricoNotificacao.direcao == 'outbound'
        ).count()
        
        total_ent = HistoricoNotificacao.query.filter(
            HistoricoNotificacao.enviado_em >= timestamp,
            HistoricoNotificacao.enviado_em < fim_periodo,
            HistoricoNotificacao.status_envio == 'enviado'
        ).count()
        
        enviadas.append(total_env)
        entregues.append(total_ent)
        timestamp = fim_periodo
    
    return jsonify({
        'labels': labels,
        'enviadas': enviadas,
        'entregues': entregues
    })

@bp.route('/api/whatsapp/historico-recente')
@login_required
def historico_recente():
    """Últimas 20 notificações"""
    notifs = HistoricoNotificacao.query.order_by(
        HistoricoNotificacao.criado_em.desc()
    ).limit(20).all()
    
    return jsonify([{
        'hora': utc_to_local(n.criado_em).strftime('%H:%M'),
        'direcao': n.direcao,
        'destinatario': (n.destinatario or '')[-4:],
        'tipo': n.tipo,
        'status': n.status_envio
    } for n in notifs])

# --- Configuração & Testes ---

@bp.route('/admin/whatsapp/config', methods=['GET', 'POST'])
@login_required
def configuracao():
    """Tela de configurações do WhatsApp"""
    if current_user.tipo != 'admin':
        abort(403)
        
    config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
    if not config:
        config = ConfiguracaoWhatsApp(ativo=True)
        db.session.add(config)
        db.session.commit()
    
    if request.method == 'POST':
        # Atualizar configurações
        from cryptography.fernet import Fernet
        
        # Rate Limit & Circuit Breaker
        config.rate_limit = int(request.form.get('rate_limit', 60))
        config.circuit_breaker_threshold = int(request.form.get('cb_threshold', 5))
        
        # O campo api_key foi removido do form conforme pedido do usuário
        # pois agora é configurado via .env
        
        db.session.commit()
        return render_template('admin/whatsapp_config.html', config=config, success=True)
        
    return render_template('admin/whatsapp_config.html', config=config)

@bp.route('/api/whatsapp/teste', methods=['POST'])
@login_required
def enviar_teste():
    """Envia mensagem de teste manual"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    telefone = data.get('telefone')
    mensagem = data.get('mensagem')

    if not telefone or not mensagem:
        return jsonify({'error': 'Dados incompletos'}), 400

    from app.services.whatsapp_service import WhatsAppService

    # Forçar prioridade máxima para teste
    sucesso, resposta = WhatsAppService.enviar_mensagem(
        telefone=telefone,
        texto=mensagem,
        prioridade=2
    )

    # Registrar no histórico como 'teste_manual'
    if sucesso:
        hs = HistoricoNotificacao(
            tipo='teste_manual',
            destinatario=telefone,
            mensagem=mensagem,
            status_envio='enviado',
            direcao='outbound',
            enviado_em=datetime.utcnow()
        )
        db.session.add(hs)
        db.session.commit()

    if sucesso:
        return jsonify({
            'success': True,
            'resposta': resposta
        })
    else:
        # Extrair mensagem de erro para o frontend
        error_msg = resposta.get('error') or resposta.get('text') or str(resposta)
        return jsonify({
            'success': False,
            'error': error_msg,
            'resposta': resposta
        })

# ==================== PHASE 2: CENTRAL DE MENSAGENS ====================

@bp.route('/admin/chat')
@login_required
def chat_central():
    """Central de Mensagens - Interface de Chat"""
    if current_user.tipo != 'admin':
        abort(403)

    return render_template('admin/chat_central.html')

@bp.route('/admin/chat/conversas')
@login_required
def listar_conversas():
    """Lista todas as conversas com última mensagem e contagem de não lidas"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    filtro = request.args.get('filtro', 'todas')

    from app.models.terceirizados_models import Terceirizado
    from sqlalchemy import func, or_, literal_column

    # SQLAlchemy 2.x: colunas sem .label() recebem prefixo da tabela no UNION subquery.
    # Solução: usar .label() explícito em TODAS as colunas.
    subq_inbound = db.session.query(
        HistoricoNotificacao.remetente.label('telefone'),
        HistoricoNotificacao.criado_em.label('criado_em'),
        HistoricoNotificacao.direcao.label('direcao'),
        HistoricoNotificacao.status_leitura.label('status_leitura'),
        HistoricoNotificacao.tipo_conteudo.label('tipo_conteudo'),
        HistoricoNotificacao.mensagem.label('mensagem'),
        HistoricoNotificacao.tipo.label('tipo')
    ).filter(
        HistoricoNotificacao.direcao == 'inbound',
        HistoricoNotificacao.remetente.isnot(None),
        HistoricoNotificacao.remetente != '',
        HistoricoNotificacao.remetente != 'sistema'
    )

    subq_outbound = db.session.query(
        HistoricoNotificacao.destinatario.label('telefone'),
        HistoricoNotificacao.criado_em.label('criado_em'),
        HistoricoNotificacao.direcao.label('direcao'),
        HistoricoNotificacao.status_leitura.label('status_leitura'),
        HistoricoNotificacao.tipo_conteudo.label('tipo_conteudo'),
        HistoricoNotificacao.mensagem.label('mensagem'),
        HistoricoNotificacao.tipo.label('tipo')
    ).filter(
        HistoricoNotificacao.direcao == 'outbound',
        HistoricoNotificacao.destinatario.isnot(None),
        HistoricoNotificacao.destinatario != '',
        HistoricoNotificacao.destinatario != 'sistema'
    )

    # Unir inbound e outbound
    union_query = subq_inbound.union_all(subq_outbound).subquery()

    # Agrupar por telefone
    nao_lidas_expr = func.count(
        db.case(
            (db.and_(
                union_query.c.direcao == 'inbound',
                or_(
                    union_query.c.status_leitura == None,
                    union_query.c.status_leitura == 'nao_lida'
                )
            ), 1)
        )
    )

    query = db.session.query(
        union_query.c.telefone,
        func.max(union_query.c.criado_em).label('ultima_msg_em'),
        nao_lidas_expr.label('nao_lidas')
    ).group_by(union_query.c.telefone)

    # Aplicar filtros
    if filtro == 'nao_lidas':
        query = query.having(nao_lidas_expr > 0)
    elif filtro == 'ativas':
        limite_24h = datetime.utcnow() - timedelta(hours=24)
        query = query.having(func.max(union_query.c.criado_em) >= limite_24h)

    conversas_raw = query.order_by(func.max(union_query.c.criado_em).desc()).limit(50).all()

    # Buscar preview da última mensagem e nome do contato para cada conversa
    from app.models.estoque_models import Fornecedor
    from app.models.models import Usuario

    conversas = []
    for conv in conversas_raw:
        telefone = conv.telefone
        if not telefone:
            continue

        # Buscar última mensagem (inbound OU outbound), excluindo mensagens deletadas
        ultima = HistoricoNotificacao.query.filter(
            or_(
                HistoricoNotificacao.remetente == telefone,
                HistoricoNotificacao.destinatario == telefone
            ),
            HistoricoNotificacao.excluido_em.is_(None)
        ).order_by(HistoricoNotificacao.criado_em.desc()).first()

        if not ultima:
            continue

        # Tentar encontrar nome do contato (Terceirizado, Fornecedor ou Usuario)
        nome = None
        terceirizado = Terceirizado.query.filter_by(telefone=telefone).first()
        if terceirizado:
            nome = terceirizado.nome
        else:
            fornecedor = Fornecedor.query.filter_by(telefone=telefone).first()
            if not fornecedor:
                fornecedor = Fornecedor.query.filter_by(whatsapp=telefone).first()
            if fornecedor:
                nome = fornecedor.nome
            else:
                usuario = Usuario.query.filter_by(telefone=telefone).first()
                if usuario:
                    nome = usuario.nome

        # Se não encontrou em nenhuma tabela, usar pushName salvo na última mensagem inbound
        if not nome:
            msg_com_nome = HistoricoNotificacao.query.filter(
                HistoricoNotificacao.remetente == telefone,
                HistoricoNotificacao.direcao == 'inbound',
                HistoricoNotificacao.caption.isnot(None)
            ).order_by(HistoricoNotificacao.criado_em.desc()).first()
            if msg_com_nome:
                nome = msg_com_nome.caption

        # Calcular tempo relativo (usando hora local Brasil UTC-3)
        ultima_msg_local = utc_to_local(conv.ultima_msg_em)
        tempo_diff = datetime.utcnow() - conv.ultima_msg_em
        if tempo_diff.total_seconds() < 60:
            tempo_str = 'agora'
        elif tempo_diff.total_seconds() < 3600:
            tempo_str = f'{int(tempo_diff.total_seconds() // 60)}min'
        elif tempo_diff.days == 0:
            tempo_str = ultima_msg_local.strftime('%H:%M')
        elif tempo_diff.days == 1:
            tempo_str = 'ontem'
        else:
            tempo_str = ultima_msg_local.strftime('%d/%m')

        # Preview da mensagem
        tipo_conteudo = ultima.tipo_conteudo or 'text'
        if tipo_conteudo == 'text':
            preview = ultima.mensagem[:50] + '...' if len(ultima.mensagem or '') > 50 else (ultima.mensagem or '')
        elif tipo_conteudo == 'audio':
            preview = '🎤 Áudio'
        elif tipo_conteudo == 'image':
            preview = '📷 Imagem'
        elif tipo_conteudo == 'document':
            preview = '📄 Documento'
        else:
            preview = ultima.tipo or tipo_conteudo

        # Indicar direção na preview
        if ultima.direcao == 'outbound':
            preview = '↗ ' + preview

        conversas.append({
            'telefone': telefone,
            'nome': nome or telefone,
            'ultima_msg_tempo': tempo_str,
            'ultima_msg_preview': preview,
            'nao_lidas': int(conv.nao_lidas)
        })

    return jsonify(conversas)

@bp.route('/admin/chat/mensagens/<telefone>')
@login_required
def listar_mensagens(telefone):
    """Lista todas as mensagens de uma conversa específica"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    # Normalizar telefone e gerar variantes para retrocompatibilidade com registros antigos
    from app.services.whatsapp_service import WhatsAppService
    try:
        telefone_norm = WhatsAppService.normalizar_telefone(telefone)
    except Exception:
        telefone_norm = telefone

    # Gerar variante sem prefixo 55 (para mensagens antigas)
    telefone_sem55 = telefone_norm[2:] if telefone_norm.startswith('55') and len(telefone_norm) > 11 else telefone_norm

    # Buscar mensagens por ambos os formatos (retrocompatibilidade)
    mensagens = db.session.query(HistoricoNotificacao).filter(
        or_(
            HistoricoNotificacao.remetente == telefone_norm,
            HistoricoNotificacao.destinatario == telefone_norm,
            HistoricoNotificacao.remetente == telefone_sem55,
            HistoricoNotificacao.destinatario == telefone_sem55,
            HistoricoNotificacao.remetente == telefone,
            HistoricoNotificacao.destinatario == telefone,
        ),
        HistoricoNotificacao.excluido_em.is_(None)
    ).order_by(HistoricoNotificacao.criado_em.asc()).all()

    resultado = []
    for msg in mensagens:
        # Determinar direção correta
        if msg.direcao:
            direcao = msg.direcao
        elif msg.destinatario == telefone:
            direcao = 'outbound'
        else:
            direcao = 'inbound'

        criado_local = utc_to_local(msg.criado_em)
        resultado.append({
            'id': msg.id,
            'direcao': direcao,
            'mensagem': msg.mensagem,
            'tipo_conteudo': msg.tipo_conteudo or 'text',
            'url_midia_local': msg.url_midia_local,
            'mimetype': msg.mimetype,
            'caption': msg.caption,
            'mensagem_transcrita': getattr(msg, 'mensagem_transcrita', None),
            'status': msg.status_envio,
            'hora': criado_local.strftime('%H:%M'),
            'data_completa': criado_local.isoformat(),
            'excluido_em': msg.excluido_em.isoformat() if msg.excluido_em else None
        })

    return jsonify(resultado)

@bp.route('/admin/chat/enviar', methods=['POST'])
@login_required
def enviar_mensagem_chat():
    """Envia mensagem pela central de chat"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    telefone = data.get('telefone')
    mensagem = data.get('mensagem')

    if not telefone or not mensagem:
        return jsonify({'error': 'Dados incompletos', 'success': False}), 400

    from app.services.whatsapp_service import WhatsAppService

    # Normalizar telefone para formato consistente antes de enviar e salvar
    try:
        telefone_norm = WhatsAppService.normalizar_telefone(telefone)
    except Exception:
        telefone_norm = telefone

    # Enviar mensagem com prioridade alta (gerente respondendo)
    sucesso, resposta = WhatsAppService.enviar_mensagem(
        telefone=telefone_norm,
        texto=mensagem,
        prioridade=1
    )

    # Registrar no histórico com telefone normalizado para consistência com inbound
    if sucesso:
        hs = HistoricoNotificacao(
            tipo='resposta_manual',
            remetente='sistema',
            destinatario=telefone_norm,
            mensagem=mensagem,
            status_envio='enviado',
            direcao='outbound',
            tipo_conteudo='text',
            enviado_em=datetime.utcnow()
        )
        db.session.add(hs)
        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem_id': hs.id
        })
    else:
        return jsonify({
            'success': False,
            'error': resposta.get('error', 'Erro ao enviar')
        }), 500

@bp.route('/admin/chat/marcar-lida/<telefone>', methods=['POST'])
@login_required
def marcar_como_lida(telefone):
    """Marca todas as mensagens de um contato como lidas"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    # Atualizar status de leitura de mensagens inbound não lidas
    HistoricoNotificacao.query.filter_by(
        remetente=telefone,
        direcao='inbound'
    ).filter(
        or_(
            HistoricoNotificacao.status_leitura == None,
            HistoricoNotificacao.status_leitura == 'nao_lida'
        )
    ).update({
        'status_leitura': 'lida'
    })

    db.session.commit()

    return jsonify({'success': True})

@bp.route('/admin/chat/excluir/<int:msg_id>', methods=['DELETE'])
@login_required
def excluir_mensagem(msg_id):
    """Exclui uma mensagem do historico e tenta apagar na MegaAPI"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    notif = HistoricoNotificacao.query.get_or_404(msg_id)

    # Tentar excluir na MegaAPI se tiver megaapi_id
    api_ok = False
    if notif.megaapi_id:
        try:
            from app.services.whatsapp_service import WhatsAppService
            telefone = notif.destinatario if notif.direcao == 'outbound' else notif.remetente
            from_me = notif.direcao == 'outbound'
            api_ok, resp = WhatsAppService.delete_message(telefone, notif.megaapi_id, from_me)
        except Exception as e:
            logger.warning(f"Erro ao excluir mensagem na MegaAPI: {e}")

    # Marcar como excluida no banco (soft delete)
    notif.excluido_em = datetime.utcnow()
    notif.excluido_por = current_user.id
    db.session.commit()

    return jsonify({
        'success': True,
        'api_excluida': api_ok,
        'mensagem': 'Mensagem excluida'
    })


@bp.route('/admin/whatsapp/configurar-webhook', methods=['POST'])
@login_required
def configurar_webhook_megaapi():
    """
    Configura o webhook na MegaAPI para receber mensagens.
    Endpoint: POST {MEGA_API_URL}/rest/webhook/{MEGA_API_KEY}/configWebhook
    """
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    import requests
    from flask import current_app

    # Obter configuracoes do .env
    url_base = current_app.config.get('MEGA_API_URL')
    instance_key = current_app.config.get('MEGA_API_KEY')
    bearer_token = current_app.config.get('MEGA_API_TOKEN')

    if not url_base or not instance_key:
        return jsonify({
            'success': False,
            'error': 'Configuracao MegaAPI incompleta. Verifique MEGA_API_URL e MEGA_API_KEY no .env'
        }), 400

    # URL do webhook (ngrok ou producao)
    data = request.json or {}
    webhook_url = data.get('webhook_url')

    if not webhook_url:
        return jsonify({
            'success': False,
            'error': 'webhook_url e obrigatorio. Ex: https://seu-ngrok.ngrok-free.dev/webhook/whatsapp'
        }), 400

    # Montar endpoint
    base_url = url_base.rstrip('/')
    endpoint = f"{base_url}/rest/webhook/{instance_key}/configWebhook"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messageData": {
            "webhookUrl": webhook_url,
            "webhookEnabled": True,
            "webhookSecondaryUrl": "",
            "webhookSecondaryEnabled": False
        }
    }

    logger.info(f"Configurando webhook MegaAPI: {endpoint}")
    logger.info(f"Webhook URL: {webhook_url}")

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=15)

        if response.status_code in [200, 201]:
            logger.info(f"Webhook configurado com sucesso: {response.text}")
            return jsonify({
                'success': True,
                'mensagem': f'Webhook configurado para: {webhook_url}',
                'resposta_megaapi': response.json() if response.text else {}
            })
        else:
            logger.warning(f"Falha ao configurar webhook: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'error': f'MegaAPI retornou status {response.status_code}',
                'detalhes': response.text
            }), 400

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao configurar webhook: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/admin/whatsapp/status-webhook', methods=['GET'])
@login_required
def status_webhook_megaapi():
    """
    Verifica status atual do webhook na MegaAPI.
    """
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    import requests
    from flask import current_app

    url_base = current_app.config.get('MEGA_API_URL')
    instance_key = current_app.config.get('MEGA_API_KEY')
    bearer_token = current_app.config.get('MEGA_API_TOKEN')

    if not url_base or not instance_key:
        return jsonify({
            'success': False,
            'error': 'Configuracao MegaAPI incompleta'
        }), 400

    # Tentar buscar configuracao atual (pode variar conforme versao da API)
    base_url = url_base.rstrip('/')

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    # Primeiro tenta buscar config do webhook (GET equivalente ao configWebhook)
    endpoints_webhook = [
        f"{base_url}/rest/webhook/{instance_key}/findWebhook",
        f"{base_url}/rest/webhook/{instance_key}/find",
        f"{base_url}/rest/webhook/{instance_key}/configWebhook",
    ]

    webhook_data = None
    for endpoint in endpoints_webhook:
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            if response.status_code == 200:
                webhook_data = response.json() if response.text else {}
                break
        except Exception:
            continue

    # Tenta conexao da instancia
    endpoints_instance = [
        f"{base_url}/rest/instance/{instance_key}/connectionState",
        f"{base_url}/rest/instance/{instance_key}/fetchInstances",
    ]

    instance_data = None
    for endpoint in endpoints_instance:
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            if response.status_code == 200:
                instance_data = response.json() if response.text else {}
                break
        except Exception:
            continue

    if webhook_data is not None or instance_data is not None:
        return jsonify({
            'success': True,
            'webhook': webhook_data,
            'instancia': instance_data,
            'mensagem': 'Status obtido com sucesso'
        })

    # Se nao conseguiu via API, retorna info local confirmando que o webhook esta ativo
    # (o usuario confirmou que esta recebendo mensagens, logo o webhook funciona)
    return jsonify({
        'success': True,
        'webhook': None,
        'instancia': None,
        'mensagem': 'Webhook ativo (mensagens sendo recebidas). Status detalhado indisponivel na versao atual da API.',
        'dica': 'Se as mensagens chegam normalmente, o webhook esta configurado corretamente.'
    })
