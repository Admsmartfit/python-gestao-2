from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.estoque_models import (
    PedidoCompra, Fornecedor, Estoque, CatalogoFornecedor, ComunicacaoFornecedor,
    ListaCompra, ListaCompraItem, OrdemCompraLista,
    AprovacaoPedido, FaturamentoCompra, OrcamentoUnidade,
    CotacaoCompra, ConfiguracaoCompras
)
from app.extensions import db
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

bp = Blueprint('compras', __name__, url_prefix='/compras')

@bp.route('/')
@login_required
def listar():
    """Lista todos os pedidos de compra com filtros"""
    status_filter = request.args.get('status')
    query = PedidoCompra.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    pedidos = query.order_by(PedidoCompra.data_solicitacao.desc()).all()

    # Fila do comprador: aprovados aguardando processamento (do mais antigo para o mais recente)
    fila = []
    if current_user.tipo in ['admin', 'comprador', 'gerente']:
        fila = PedidoCompra.query.filter(
            PedidoCompra.status == 'aprovado'
        ).order_by(PedidoCompra.data_solicitacao.asc()).all()

    return render_template('compras/lista.html', pedidos=pedidos, status_atual=status_filter, fila=fila)

@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    """Manual purchase order creation"""
    if request.method == 'POST':
        try:
            estoque_id = request.form.get('estoque_id')
            quantidade = float(request.form.get('quantidade', 0))
            fornecedor_id = request.form.get('fornecedor_id')
            unidade_id = request.form.get('unidade_destino_id')
            
            if not estoque_id or quantidade <= 0:
                flash("Peça e quantidade são obrigatórios.", "warning")
                return redirect(url_for('compras.novo'))

            item = Estoque.query.get(estoque_id)
            valor_unitario = float(item.valor_unitario or 0)
            valor_total = valor_unitario * quantidade

            status_inicial = 'solicitado'
            aprovador_id = None
            os_id_ref = request.form.get('os_id') or None

            # Calcular tier de aprovação (limites configuráveis)
            cfg = ConfiguracaoCompras.get()
            valor_unitario_est = float(request.form.get('valor_unitario', 0) or 0)
            valor_total_est = valor_unitario_est * quantidade if valor_unitario_est else valor_total

            if valor_total_est <= float(cfg.tier1_limite):
                tier = 1
                status_inicial = 'aprovado'
                aprovador_id = 0
            elif valor_total_est <= float(cfg.tier2_limite):
                tier = 2
                status_inicial = 'solicitado'
                aprovador_id = None
            else:
                tier = 3
                status_inicial = 'aguardando_diretoria'
                aprovador_id = None

            data_entrega_str = request.form.get('data_entrega_prevista', '').strip()
            data_entrega = datetime.strptime(data_entrega_str, '%Y-%m-%d') if data_entrega_str else None

            pedido = PedidoCompra(
                estoque_id=estoque_id,
                quantidade=int(quantidade),
                fornecedor_id=fornecedor_id if fornecedor_id else None,
                unidade_destino_id=unidade_id if unidade_id else None,
                solicitante_id=current_user.id,
                status=status_inicial,
                aprovador_id=aprovador_id,
                os_id=int(os_id_ref) if os_id_ref else None,
                valor_unitario_estimado=valor_unitario_est or None,
                valor_total_estimado=valor_total_est or None,
                tier_aprovacao=tier,
                data_entrega_prevista=data_entrega,
            )
            db.session.add(pedido)
            db.session.commit()

            if tier == 1:
                from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
                enviar_pedido_fornecedor.delay(pedido.id)
                msg_adic = " — Aprovado automaticamente (Tier 1)"
            elif tier == 2:
                msg_adic = " — Aguardando aprovação do Gerente (Tier 2)"
            else:
                msg_adic = " — Aguardando consenso da Diretoria (Tier 3)"
                _notificar_diretores_tier3(pedido)

            flash(f"Pedido #{pedido.id} criado!{msg_adic}", "success")
            return redirect(url_for('compras.listar'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar pedido: {e}")
            flash("Erro ao processar pedido.", "danger")

    pecas = Estoque.query.order_by(Estoque.nome).all()
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    from app.models.models import Unidade
    unidades = Unidade.query.all()

    return render_template('compras/novo.html', pecas=pecas, fornecedores=fornecedores, unidades=unidades)

@bp.route('/<int:id>')
@login_required
def detalhes(id):
    """View order details, quotes and communication history"""
    pedido = PedidoCompra.query.get_or_404(id)
    quotes = CatalogoFornecedor.query.filter_by(estoque_id=pedido.estoque_id).order_by(CatalogoFornecedor.preco_atual).all()
    from app.models.models import Unidade
    unidades = Unidade.query.filter_by(ativa=True).order_by(Unidade.nome).all()
    fornecedores_cadastrados = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()

    return render_template('compras/detalhes_melhorado.html',
                           pedido=pedido, quotes=quotes, unidades=unidades,
                           fornecedores_cadastrados=fornecedores_cadastrados)

@bp.route('/<int:id>/alterar_unidade', methods=['POST'])
@login_required
def alterar_unidade(id):
    """Altera a unidade solicitante do pedido de compra"""
    pedido = PedidoCompra.query.get_or_404(id)
    data = request.json
    unidade_id = data.get('unidade_id')

    if unidade_id:
        from app.models.models import Unidade
        unidade = Unidade.query.get(unidade_id)
        if not unidade:
            return jsonify({'success': False, 'erro': 'Unidade nao encontrada'}), 404
        pedido.unidade_destino_id = unidade.id
    else:
        pedido.unidade_destino_id = None

    db.session.commit()
    return jsonify({'success': True, 'mensagem': 'Unidade solicitante atualizada'})

def _notificar_diretores_tier3(pedido):
    """Envia mensagem com botões One-Tap para todos os diretores/admins via WhatsApp."""
    try:
        from app.models.models import Usuario
        from app.services.whatsapp_service import WhatsAppService
        diretores = Usuario.query.filter(
            Usuario.tipo.in_(['admin', 'diretor']),
            Usuario.ativo == True,
            Usuario.telefone.isnot(None)
        ).all()
        item_nome = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido.id}')
        solicitante_nome = pedido.solicitante.nome if pedido.solicitante else 'Sistema'
        valor_str = pedido.valor_display if hasattr(pedido, 'valor_display') else '—'
        body = (
            f"⚡ *Aprovação Necessária — Tier 3*\n\n"
            f"📦 Pedido *#{pedido.id}*\n"
            f"💰 Valor estimado: *{valor_str}*\n"
            f"📝 Item: {item_nome}\n"
            f"👤 Solicitante: {solicitante_nome}\n\n"
            f"Sua aprovação é necessária. Por favor, avalie:"
        )
        buttons = [
            {"buttonId": f"aprovar_pedido_{pedido.id}", "buttonText": {"displayText": "✅ Aprovar"}, "type": 1},
            {"buttonId": f"rejeitar_pedido_{pedido.id}", "buttonText": {"displayText": "❌ Rejeitar"}, "type": 1},
        ]
        for diretor in diretores:
            WhatsAppService.send_buttons_message(phone=diretor.telefone, body=body, buttons=buttons)
    except Exception as e:
        logger.warning(f"Erro ao notificar diretores Tier 3: {e}")


@bp.route('/aprovacoes')
@login_required
def aprovacoes():
    """Painel de aprovações pendentes (Tier 2 = Gerente, Tier 3 = Diretoria)."""
    if current_user.tipo not in ['admin', 'gerente', 'diretor']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('compras.listar'))

    tier2 = PedidoCompra.query.filter_by(status='solicitado', tier_aprovacao=2).order_by(
        PedidoCompra.data_solicitacao.desc()).all()
    tier3 = PedidoCompra.query.filter_by(status='aguardando_diretoria', tier_aprovacao=3).order_by(
        PedidoCompra.data_solicitacao.desc()).all()

    # Enriquece tier3 com contagem de aprovações já registradas
    tier3_info = []
    for p in tier3:
        aprovs = AprovacaoPedido.query.filter_by(pedido_id=p.id, acao='aprovado').count()
        tier3_info.append({'pedido': p, 'aprovacoes_count': aprovs})

    cfg = ConfiguracaoCompras.get()
    return render_template('compras/aprovacoes.html', tier2=tier2, tier3_info=tier3_info, cfg=cfg)


@bp.route('/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar(id):
    """Aprovação de pedido — suporta Tier 2 (gerente) e Tier 3 (consenso diretoria)."""
    if current_user.tipo not in ['admin', 'gerente', 'diretor']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('compras.detalhes', id=id))

    pedido = PedidoCompra.query.get_or_404(id)
    observacao = request.form.get('observacao', '').strip()

    if pedido.status not in ('solicitado', 'aguardando_diretoria'):
        flash("Este pedido já foi processado.", "info")
        return redirect(url_for('compras.detalhes', id=id))

    # Registrar aprovação individual
    ja_aprovou = AprovacaoPedido.query.filter_by(pedido_id=id, aprovador_id=current_user.id, acao='aprovado').first()
    if ja_aprovou:
        flash("Você já aprovou este pedido.", "info")
        return redirect(url_for('compras.detalhes', id=id))

    registro = AprovacaoPedido(
        pedido_id=id,
        aprovador_id=current_user.id,
        acao='aprovado',
        observacao=observacao,
        via='web'
    )
    db.session.add(registro)

    tier = pedido.tier_aprovacao or 2
    is_admin = current_user.tipo == 'admin'

    if tier <= 2 or is_admin:
        # Tier 1/2: aprovação simples. Admin sempre aprova de imediato, qualquer tier.
        pedido.status = 'aprovado'
        pedido.aprovador_id = current_user.id
        db.session.commit()
        _notificar_solicitante(pedido, aprovado=True)
        _notificar_compradores(pedido)
        if pedido.tipo_pedido != 'cotacao' and pedido.fornecedor_id:
            from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
            enviar_pedido_fornecedor.delay(pedido.id)
        flash(f"Pedido #{id} aprovado com sucesso!", "success")
    else:
        # Tier 3: precisa de 2 aprovações (gerente/diretor)
        db.session.commit()  # salva o registro acima
        total_aprovacoes = AprovacaoPedido.query.filter_by(pedido_id=id, acao='aprovado').count()
        if total_aprovacoes >= 2:
            pedido.status = 'aprovado'
            pedido.aprovador_id = current_user.id
            db.session.commit()
            _notificar_solicitante(pedido, aprovado=True)
            _notificar_compradores(pedido)
            if pedido.tipo_pedido != 'cotacao' and pedido.fornecedor_id:
                from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
                enviar_pedido_fornecedor.delay(pedido.id)
            flash(f"Pedido #{id} aprovado! Consenso de diretoria atingido ({total_aprovacoes}/2).", "success")
        else:
            flash(f"Sua aprovação foi registrada ({total_aprovacoes}/2). Aguardando segundo diretor.", "info")

    return redirect(url_for('compras.aprovacoes'))

@bp.route('/<int:id>/receber', methods=['POST'])
@login_required
def receber(id):
    """US-011: Registra recebimento da compra e notifica solicitante."""
    pedido = PedidoCompra.query.get_or_404(id)
    
    if pedido.status == 'recebido':
        flash("Este pedido já foi recebido.", "info")
        return redirect(url_for('compras.detalhes', id=id))

    # 1. Atualiza Estoque
    # 1. Atualiza Estoque (somente para pedidos de catálogo com estoque vinculado)
    if pedido.estoque_id:
        from app.services.estoque_service import EstoqueService
        try:
            EstoqueService.repor_estoque(
                estoque_id=pedido.estoque_id,
                quantidade=pedido.quantidade,
                usuario_id=current_user.id,
                motivo=f"Recebimento Pedido #{pedido.id}",
                unidade_id=pedido.unidade_destino_id
            )
        except Exception as e:
            flash(f"Erro ao atualizar estoque: {e}", "danger")
            return redirect(url_for('compras.detalhes', id=id))

    # 2. Atualiza Pedido
    pedido.status = 'recebido'
    pedido.data_recebimento = datetime.now()
    db.session.commit()

    # 3. Notifica Solicitante
    from app.services.whatsapp_service import WhatsAppService
    if pedido.solicitante and pedido.solicitante.telefone:
        item = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido.id}')
        msg = f"📦 *CONCLUÍDO!*\n\n*{item}* do seu pedido #{pedido.id} foi recebido/concluído."
        WhatsAppService.enviar_mensagem(pedido.solicitante.telefone, msg)

    estoque_msg = " Estoque atualizado." if pedido.estoque_id else ""
    flash(f"Pedido #{id} marcado como recebido.{estoque_msg} Solicitante notificado.", "success")
    return redirect(url_for('compras.detalhes', id=id))

def _notificar_solicitante(pedido, aprovado: bool):
    """Notifica o solicitante via WhatsApp sobre resultado da aprovação."""
    try:
        from app.services.whatsapp_service import WhatsAppService
        if pedido.solicitante and pedido.solicitante.telefone:
            item = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido.id}')
            if aprovado:
                msg = f"✅ Seu pedido *#{pedido.id}* ({item}) foi *aprovado* e será processado."
            else:
                msg = f"❌ Seu pedido *#{pedido.id}* ({item}) foi *recusado*."
            WhatsAppService.enviar_mensagem(pedido.solicitante.telefone, msg)
    except Exception as e:
        logger.warning(f"Erro ao notificar solicitante: {e}")


def _notificar_compradores(pedido):
    """Notifica compradores/admins via WhatsApp quando um pedido é aprovado e precisa ser processado."""
    try:
        from app.models.models import Usuario
        from app.services.whatsapp_service import WhatsAppService
        compradores = Usuario.query.filter(
            Usuario.tipo.in_(['admin', 'comprador']),
            Usuario.ativo == True,
            Usuario.telefone.isnot(None)
        ).all()
        if not compradores:
            return
        item = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido.id}')
        solicitante = pedido.solicitante.nome if pedido.solicitante else 'Sistema'
        cotacao_info = ''
        if pedido.tipo_pedido == 'cotacao' and pedido.cotacoes:
            sel = next((c for c in pedido.cotacoes if c.selecionada), pedido.cotacoes[0])
            cotacao_info = f'\n🏢 Fornecedor indicado: *{sel.fornecedor_nome}* ({sel.valor_display})'
        msg = (
            f"✅ *Pedido #{pedido.id} APROVADO — Aguarda Processamento*\n\n"
            f"📦 {item}\n"
            f"💰 {pedido.valor_display}\n"
            f"👤 Solicitante: {solicitante}"
            f"{cotacao_info}\n\n"
            f"Acesse o sistema para encaminhar ao fornecedor."
        )
        for comp in compradores:
            WhatsAppService.enviar_mensagem(comp.telefone, msg)
    except Exception as e:
        logger.warning(f"Erro ao notificar compradores: {e}")


@bp.route('/<int:id>/rejeitar', methods=['POST'])
@login_required
def rejeitar(id):
    """Rejeitar pedido (qualquer tier)."""
    if current_user.tipo not in ['admin', 'gerente', 'diretor']:
        return jsonify({'error': 'Permissão negada'}), 403

    pedido = PedidoCompra.query.get_or_404(id)
    if pedido.status in ('recebido', 'cancelado', 'recusado'):
        flash("Pedido não pode ser rejeitado no status atual.", "warning")
        return redirect(url_for('compras.aprovacoes'))

    observacao = request.form.get('observacao', '').strip()
    registro = AprovacaoPedido(
        pedido_id=id,
        aprovador_id=current_user.id,
        acao='rejeitado',
        observacao=observacao,
        via='web'
    )
    db.session.add(registro)
    pedido.status = 'recusado'
    db.session.commit()
    _notificar_solicitante(pedido, aprovado=False)
    flash(f"Pedido #{id} recusado.", "warning")
    return redirect(url_for('compras.aprovacoes'))


@bp.route('/config/tiers', methods=['POST'])
@login_required
def salvar_config_tiers():
    """Salva limites de Tier (admin only)."""
    if current_user.tipo != 'admin':
        flash("Apenas administradores podem alterar os limites de tier.", "danger")
        return redirect(url_for('compras.aprovacoes'))

    cfg = ConfiguracaoCompras.get()
    try:
        t1 = float(request.form.get('tier1_limite', '500').replace(',', '.'))
        t2 = float(request.form.get('tier2_limite', '5000').replace(',', '.'))
        if t1 >= t2:
            flash("O limite do Tier 1 deve ser menor que o do Tier 2.", "warning")
            return redirect(url_for('compras.aprovacoes'))
        cfg.tier1_limite = t1
        cfg.tier2_limite = t2
        cfg.updated_by_id = current_user.id
        db.session.commit()
        flash(f"Limites atualizados: Tier 1 ≤ R${t1:,.0f} | Tier 2 ≤ R${t2:,.0f}", "success")
    except (ValueError, TypeError):
        flash("Valores inválidos.", "warning")
    return redirect(url_for('compras.aprovacoes'))


@bp.route('/cotacao/nova', methods=['GET', 'POST'])
@login_required
def cotacao_nova():
    """Solicitação de compra livre com múltiplos orçamentos (ex: serviços, reformas)."""
    from app.models.models import Unidade
    if request.method == 'POST':
        try:
            descricao = request.form.get('descricao', '').strip()
            if not descricao:
                flash("Descrição do que deseja comprar é obrigatória.", "warning")
                return redirect(url_for('compras.cotacao_nova'))

            unidade_id = request.form.get('unidade_destino_id') or None
            categoria = request.form.get('categoria_compra', 'outros')
            justificativa = request.form.get('justificativa', '').strip() or None

            # Coletar cotações submetidas
            fornecedores_nomes = request.form.getlist('cotacao_fornecedor')
            valores = request.form.getlist('cotacao_valor')
            prazos = request.form.getlist('cotacao_prazo')
            obs_list = request.form.getlist('cotacao_obs')
            links_list = request.form.getlist('cotacao_link')
            selecionada_idx = int(request.form.get('cotacao_selecionada', 0))

            cotacoes_validas = []
            for i, (fn, vl) in enumerate(zip(fornecedores_nomes, valores)):
                fn = fn.strip()
                vl_str = vl.replace(',', '.').strip()
                link = links_list[i].strip() if i < len(links_list) else ''
                if fn and vl_str:
                    cotacoes_validas.append({
                        'fornecedor_nome': fn,
                        'valor_total': float(vl_str),
                        'prazo_dias': int(prazos[i]) if prazos[i].strip().isdigit() else None,
                        'observacao': obs_list[i].strip() or None,
                        'link_produto': link or None,
                        'selecionada': (i == selecionada_idx),
                    })

            if not cotacoes_validas:
                flash("Informe pelo menos um orçamento.", "warning")
                return redirect(url_for('compras.cotacao_nova'))

            # Valor de referência = cotação selecionada (ou menor)
            valor_ref = cotacoes_validas[selecionada_idx]['valor_total'] if selecionada_idx < len(cotacoes_validas) \
                else min(c['valor_total'] for c in cotacoes_validas)

            cfg = ConfiguracaoCompras.get()
            if valor_ref <= float(cfg.tier1_limite):
                tier, status_ini, aprov_id = 1, 'aprovado', 0
            elif valor_ref <= float(cfg.tier2_limite):
                tier, status_ini, aprov_id = 2, 'solicitado', None
            else:
                tier, status_ini, aprov_id = 3, 'aguardando_diretoria', None

            pedido = PedidoCompra(
                estoque_id=None,
                quantidade=1,
                solicitante_id=current_user.id,
                unidade_destino_id=unidade_id,
                status=status_ini,
                aprovador_id=aprov_id,
                descricao_livre=descricao,
                categoria_compra=categoria,
                justificativa=justificativa,
                valor_total_estimado=valor_ref,
                tier_aprovacao=tier,
                tipo_pedido='cotacao',
            )
            db.session.add(pedido)
            db.session.flush()  # gera pedido.id

            for c in cotacoes_validas:
                db.session.add(CotacaoCompra(pedido_id=pedido.id, **c))

            db.session.commit()

            if tier == 1:
                flash(f"Solicitação #{pedido.id} criada e aprovada automaticamente (Tier 1).", "success")
            elif tier == 2:
                flash(f"Solicitação #{pedido.id} criada — aguardando aprovação do gerente.", "info")
            else:
                _notificar_diretores_tier3(pedido)
                flash(f"Solicitação #{pedido.id} criada — aguardando consenso da diretoria.", "info")

            return redirect(url_for('compras.listar'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar cotação: {e}")
            flash("Erro ao processar solicitação.", "danger")

    unidades = Unidade.query.order_by(Unidade.nome).all()
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    return render_template('compras/cotacao_nova.html', unidades=unidades, fornecedores=fornecedores)


@bp.route('/<int:id>/cotacao/selecionar/<int:cotacao_id>', methods=['POST'])
@login_required
def selecionar_cotacao(id, cotacao_id):
    """Marca uma cotação como selecionada (durante aprovação)."""
    if current_user.tipo not in ['admin', 'gerente', 'diretor']:
        return jsonify({'error': 'Permissão negada'}), 403
    CotacaoCompra.query.filter_by(pedido_id=id).update({'selecionada': False})
    cotacao = CotacaoCompra.query.filter_by(id=cotacao_id, pedido_id=id).first_or_404()
    cotacao.selecionada = True
    # Atualiza valor de referência do pedido
    pedido = PedidoCompra.query.get_or_404(id)
    pedido.valor_total_estimado = cotacao.valor_total
    db.session.commit()
    flash(f"Orçamento de '{cotacao.fornecedor_nome}' selecionado como referência.", "success")
    return redirect(url_for('compras.aprovacoes'))


@bp.route('/<int:id>/encaminhar', methods=['POST'])
@login_required
def encaminhar(id):
    """Comprador confirma o fornecedor vencedor e encaminha o pedido (status → 'pedido')."""
    if current_user.tipo not in ['admin', 'comprador', 'gerente']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('compras.detalhes', id=id))

    pedido = PedidoCompra.query.get_or_404(id)
    if pedido.status != 'aprovado':
        flash("Só é possível encaminhar pedidos com status 'aprovado'.", "warning")
        return redirect(url_for('compras.detalhes', id=id))

    cotacao_id = request.form.get('cotacao_id')
    obs = request.form.get('observacao', '').strip()

    if cotacao_id:
        CotacaoCompra.query.filter_by(pedido_id=id).update({'selecionada': False})
        cotacao = CotacaoCompra.query.filter_by(id=int(cotacao_id), pedido_id=id).first()
        if cotacao:
            cotacao.selecionada = True
            pedido.valor_total_estimado = cotacao.valor_total
            fornecedor_nome = cotacao.fornecedor_nome
        else:
            fornecedor_nome = '(não selecionado)'
    else:
        fornecedor_nome = pedido.fornecedor.nome if pedido.fornecedor else '(não selecionado)'

    pedido.status = 'pedido'
    if obs:
        pedido.justificativa = ((pedido.justificativa or '') + f'\n[Encaminhamento] {obs}').strip()

    db.session.commit()

    # Notifica solicitante
    try:
        from app.services.whatsapp_service import WhatsAppService
        if pedido.solicitante and pedido.solicitante.telefone:
            item = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido.id}')
            msg = (f"🚀 *Pedido #{pedido.id} encaminhado!*\n\n"
                   f"📦 {item}\n"
                   f"🏢 Fornecedor: *{fornecedor_nome}*\n\n"
                   f"Aguardando entrega/conclusão.")
            WhatsAppService.enviar_mensagem(pedido.solicitante.telefone, msg)
    except Exception as e:
        logger.warning(f"Erro ao notificar solicitante no encaminhamento: {e}")

    flash(f"Pedido #{id} encaminhado ao fornecedor '{fornecedor_nome}'.", "success")
    return redirect(url_for('compras.detalhes', id=id))


@bp.route('/fornecedor/cadastrar-rapido', methods=['POST'])
@login_required
def cadastrar_fornecedor_rapido():
    """Cadastro rápido de fornecedor a partir da tela de cotação (retorna JSON)."""
    if current_user.tipo not in ['admin', 'comprador', 'gerente', 'diretor']:
        return jsonify({'error': 'Permissão negada'}), 403
    data = request.json or {}
    nome = (data.get('nome') or '').strip()
    if not nome:
        return jsonify({'error': 'Nome obrigatório'}), 400
    # Evita duplicata pelo nome (case-insensitive)
    existente = Fornecedor.query.filter(
        db.func.lower(Fornecedor.nome) == nome.lower()
    ).first()
    if existente:
        return jsonify({'success': True, 'id': existente.id, 'nome': existente.nome, 'duplicado': True})
    tel = (data.get('telefone') or '').strip() or None
    email = (data.get('email') or '').strip() or ''
    forn = Fornecedor(
        nome=nome,
        telefone=tel,
        email=email,
        prazo_medio_entrega_dias=7,
        ativo=True,
    )
    db.session.add(forn)
    db.session.commit()
    return jsonify({'success': True, 'id': forn.id, 'nome': forn.nome, 'duplicado': False})


@bp.route('/<int:id>/faturamento', methods=['POST'])
@login_required
def registrar_faturamento(id):
    """Registra NF e boleto de um pedido aprovado."""
    if current_user.tipo not in ['admin', 'comprador', 'gerente']:
        return jsonify({'error': 'Permissão negada'}), 403

    pedido = PedidoCompra.query.get_or_404(id)
    fat = pedido.faturamento or FaturamentoCompra(pedido_id=id)

    fat.numero_nf = request.form.get('numero_nf', '').strip() or None
    val = request.form.get('valor_faturado', '').replace(',', '.').strip()
    fat.valor_faturado = float(val) if val else None
    venc = request.form.get('data_vencimento_boleto', '').strip()
    fat.data_vencimento_boleto = datetime.strptime(venc, '%Y-%m-%d').date() if venc else None
    fat.linha_digitavel = request.form.get('linha_digitavel', '').strip() or None
    fat.registrado_por_id = current_user.id

    if not pedido.faturamento:
        db.session.add(fat)

    pedido.status = 'faturado'
    db.session.commit()

    # Notificar financeiro
    try:
        from app.models.models import Usuario
        from app.services.whatsapp_service import WhatsAppService
        financeiros = Usuario.query.filter(Usuario.tipo == 'financeiro', Usuario.ativo == True).all()
        item = pedido.peca.nome if pedido.peca else (pedido.descricao_livre or f'Pedido #{pedido.id}')
        venc_str = fat.data_vencimento_boleto.strftime('%d/%m/%Y') if fat.data_vencimento_boleto else 'N/D'
        msg = (f"💰 *Novo Boleto para Pagamento*\n\n"
               f"Pedido #{pedido.id} — {item}\n"
               f"NF: {fat.numero_nf or 'N/D'}\n"
               f"Valor: R$ {float(fat.valor_faturado or 0):,.2f}\n"
               f"Vencimento: {venc_str}")
        for fin in financeiros:
            if fin.telefone:
                WhatsAppService.enviar_mensagem(fin.telefone, msg)
    except Exception as e:
        logger.warning(f"Erro ao notificar financeiro: {e}")

    flash(f"Faturamento do Pedido #{id} registrado com sucesso!", "success")
    return redirect(url_for('compras.detalhes', id=id))


@bp.route('/<int:id>/rating', methods=['POST'])
@login_required
def registrar_rating(id):
    """Registra avaliação do fornecedor (1-5 estrelas) ao receber o pedido."""
    pedido = PedidoCompra.query.get_or_404(id)
    try:
        rating = int(request.form.get('rating', 0))
        if 1 <= rating <= 5:
            pedido.rating_fornecedor = rating
            db.session.commit()
            flash(f"Avaliação ({rating}★) registrada!", "success")
    except (ValueError, TypeError):
        flash("Rating inválido.", "warning")
    return redirect(url_for('compras.detalhes', id=id))


@bp.route('/buscar_fornecedores', methods=['POST'])
@login_required
def buscar_fornecedores():
    """Busca todos os fornecedores que fornecem um item específico"""
    try:
        estoque_id = request.json.get('estoque_id')

        if not estoque_id:
            return jsonify({'success': False, 'erro': 'Item não informado'}), 400

        # Buscar fornecedores através do catálogo
        catalogo_items = CatalogoFornecedor.query.filter_by(estoque_id=estoque_id).all()

        fornecedores_resultado = []
        for cat in catalogo_items:
            f = cat.fornecedor
            fornecedores_resultado.append({
                'id': f.id,
                'nome': f.nome,
                'email': f.email,
                'telefone': f.telefone,
                'preco_atual': float(cat.preco_atual) if cat.preco_atual else None,
                'prazo_dias': cat.prazo_estimado_dias,
                'tem_whatsapp': bool(f.telefone),
                'tem_email': bool(f.email),
                'endereco': f.endereco
            })

        # Se não houver no catálogo, retornar todos os fornecedores ativos
        if not fornecedores_resultado:
            todos_fornecedores = Fornecedor.query.filter_by(ativo=True).all()
            for f in todos_fornecedores:
                fornecedores_resultado.append({
                    'id': f.id,
                    'nome': f.nome,
                    'email': f.email,
                    'telefone': f.telefone,
                    'preco_atual': None,
                    'prazo_dias': f.prazo_medio_entrega_dias,
                    'tem_whatsapp': bool(f.telefone),
                    'tem_email': bool(f.email),
                    'endereco': f.endereco
                })

        return jsonify({
            'success': True,
            'fornecedores': fornecedores_resultado,
            'total': len(fornecedores_resultado)
        })

    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 500

# [NOVO] Criar Pedidos para Múltiplos Fornecedores
@bp.route('/criar_pedidos_multiplos', methods=['POST'])
@login_required
def criar_pedidos_multiplos():
    """Cria pedidos de compra para múltiplos fornecedores selecionados"""
    try:
        fornecedor_ids = request.json.get('fornecedor_ids', [])
        estoque_id = request.json.get('estoque_id')
        quantidade = request.json.get('quantidade')
        unidade_destino_id = request.json.get('unidade_destino_id')

        if not fornecedor_ids or not estoque_id or not quantidade:
            return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400

        quantidade = int(quantidade)
        item = Estoque.query.get(estoque_id)
        if not item:
            return jsonify({'success': False, 'erro': 'Item não encontrado'}), 404

        valor_unitario = float(item.valor_unitario or 0)
        valor_total = valor_unitario * quantidade

        # Determinar status inicial baseado no valor
        status_inicial = 'solicitado'
        aprovador_id = None
        if valor_total <= 500:
            status_inicial = 'aprovado'
            aprovador_id = 0  # Sistema

        pedidos_criados = []

        for fornecedor_id in fornecedor_ids:
            fornecedor = Fornecedor.query.get(fornecedor_id)
            if not fornecedor:
                continue

            pedido = PedidoCompra(
                estoque_id=estoque_id,
                quantidade=quantidade,
                fornecedor_id=fornecedor_id,
                unidade_destino_id=unidade_destino_id,
                solicitante_id=current_user.id,
                status=status_inicial,
                aprovador_id=aprovador_id
            )

            db.session.add(pedido)
            db.session.flush()  # Para obter o ID

            # Se aprovado automaticamente, envia para o fornecedor
            if status_inicial == 'aprovado':
                from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
                enviar_pedido_fornecedor.delay(pedido.id)

            pedidos_criados.append({
                'id': pedido.id,
                'fornecedor': fornecedor.nome,
                'status': status_inicial,
                'canal': 'WhatsApp' if fornecedor.telefone else ('Email' if fornecedor.email else 'Contato Manual')
            })

        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': f'{len(pedidos_criados)} pedidos criados com sucesso',
            'pedidos': pedidos_criados
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar pedidos múltiplos: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500

# [NOVO] Registrar Comunicação com Fornecedor
@bp.route('/<int:pedido_id>/registrar_comunicacao', methods=['POST'])
@login_required
def registrar_comunicacao(pedido_id):
    """Registra uma comunicação (enviada ou recebida) com fornecedor"""
    try:
        # Verificar se o pedido existe
        PedidoCompra.query.get_or_404(pedido_id)
        data = request.json

        fornecedor_id = data.get('fornecedor_id')
        tipo_comunicacao = data.get('tipo', data.get('tipo_comunicacao'))  # whatsapp, email, telefone, site
        mensagem = data.get('mensagem')
        direcao = data.get('direcao', 'enviado')  # enviado ou recebido
        status = data.get('status', 'enviado')

        if not fornecedor_id or not tipo_comunicacao:
            return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400

        if direcao not in ('enviado', 'recebido'):
            return jsonify({'success': False, 'erro': 'Direcao invalida'}), 400

        comunicacao = ComunicacaoFornecedor(
            pedido_compra_id=pedido_id,
            fornecedor_id=fornecedor_id,
            tipo_comunicacao=tipo_comunicacao,
            direcao=direcao,
            mensagem=mensagem,
            status=status,
            data_envio=datetime.now()
        )

        # Se for resposta recebida, atualizar a comunicacao original
        if direcao == 'recebido':
            comunicacao_original = ComunicacaoFornecedor.query.filter(
                ComunicacaoFornecedor.pedido_compra_id == pedido_id,
                ComunicacaoFornecedor.fornecedor_id == fornecedor_id,
                ComunicacaoFornecedor.direcao == 'enviado',
                ComunicacaoFornecedor.status.in_(['enviado', 'entregue', 'pendente'])
            ).order_by(ComunicacaoFornecedor.data_envio.desc()).first()

            if comunicacao_original:
                comunicacao_original.resposta = mensagem[:2000] if mensagem else None
                comunicacao_original.status = 'respondido'
                comunicacao_original.data_resposta = datetime.now()

        db.session.add(comunicacao)
        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': 'Comunicacao registrada com sucesso',
            'comunicacao_id': comunicacao.id
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao registrar comunicação: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500

# [NOVO] Registrar Resposta de Fornecedor
@bp.route('/comunicacao/<int:com_id>/resposta', methods=['POST'])
@login_required
def registrar_resposta(com_id):
    """Registra a resposta de um fornecedor"""
    try:
        comunicacao = ComunicacaoFornecedor.query.get_or_404(com_id)
        data = request.json

        resposta = data.get('resposta')
        if not resposta:
            return jsonify({'success': False, 'erro': 'Resposta não informada'}), 400

        comunicacao.resposta = resposta
        comunicacao.status = 'respondido'
        comunicacao.data_resposta = datetime.now()

        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': 'Resposta registrada com sucesso'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao registrar resposta: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500

# [NOVO] Listar Comunicações de um Pedido
@bp.route('/<int:pedido_id>/comunicacoes', methods=['GET'])
@login_required
def listar_comunicacoes(pedido_id):
    """Lista todas as comunicações de um pedido"""
    try:
        comunicacoes = ComunicacaoFornecedor.query.filter_by(
            pedido_compra_id=pedido_id
        ).order_by(ComunicacaoFornecedor.data_envio.desc()).all()

        resultado = []
        for com in comunicacoes:
            resultado.append({
                'id': com.id,
                'fornecedor': com.fornecedor.nome,
                'tipo': com.tipo_comunicacao,
                'direcao': com.direcao,
                'mensagem': com.mensagem,
                'status': com.status,
                'resposta': com.resposta,
                'data_envio': com.data_envio.strftime('%d/%m/%Y %H:%M'),
                'data_resposta': com.data_resposta.strftime('%d/%m/%Y %H:%M') if com.data_resposta else None
            })

        return jsonify({
            'success': True,
            'comunicacoes': resultado,
            'total': len(resultado)
        })

    except Exception as e:
        logger.error(f"Erro ao listar comunicações: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500


@bp.route('/api/buscar-respostas-email', methods=['POST'])
@login_required
def buscar_respostas_email():
    """
    Dispara verificação imediata da caixa IMAP em busca de respostas de fornecedores.
    Chamado pelo botão "Atualizar" na tela de detalhes do pedido.
    """
    try:
        from app.services.email_service import EmailService
        EmailService.fetch_and_process_replies()
        return jsonify({'success': True, 'msg': 'Caixa de email verificada.'})
    except Exception as e:
        logger.error(f"Erro ao buscar respostas de email: {e}", exc_info=True)
        return jsonify({'success': False, 'erro': str(e)}), 500


# [NOVO] Enviar Solicitação de Orçamento
@bp.route('/<int:pedido_id>/solicitar_orcamento', methods=['POST'])
@login_required
def solicitar_orcamento(pedido_id):
    """Envia solicitação de orçamento para fornecedores via WhatsApp/Email"""
    try:
        pedido = PedidoCompra.query.get_or_404(pedido_id)
        data = request.json

        fornecedor_ids = data.get('fornecedor_ids', [])
        mensagem_custom = data.get('mensagem')
        canal_preferido = data.get('canal')  # 'whatsapp', 'email' ou None (auto)

        if not fornecedor_ids:
            return jsonify({'success': False, 'erro': 'Nenhum fornecedor selecionado'}), 400

        enviados = []
        erros = []

        for fornecedor_id in fornecedor_ids:
            fornecedor = Fornecedor.query.get(fornecedor_id)
            if not fornecedor:
                continue

            # Dados da unidade solicitante
            unidade = pedido.unidade_destino
            unidade_info = ""
            if unidade:
                unidade_info = f"\n*Unidade Solicitante:* {unidade.nome}"
                if unidade.razao_social:
                    unidade_info += f"\nRazao Social: {unidade.razao_social}"
                if unidade.cnpj:
                    unidade_info += f"\nCNPJ: {unidade.cnpj}"
                if unidade.endereco:
                    unidade_info += f"\nEndereco: {unidade.endereco}"
                if unidade.telefone:
                    unidade_info += f"\nTelefone: {unidade.telefone}"

            # Mensagem padrao
            mensagem = mensagem_custom or f"""*SOLICITACAO DE ORCAMENTO*

Pedido: #{pedido.id}
Item: {pedido.peca.nome}
Codigo: {pedido.peca.codigo}
Quantidade: {pedido.quantidade} {pedido.peca.unidade_medida}
{unidade_info}

Por favor, envie seu melhor preco e prazo de entrega.

Solicitado por: {current_user.nome}"""

            tipo_comunicacao = None
            sucesso = False

            # Enviar por WhatsApp (usa campo whatsapp OU telefone do fornecedor)
            numero_whatsapp = fornecedor.whatsapp or fornecedor.telefone
            if canal_preferido != 'email' and numero_whatsapp:
                try:
                    from app.services.whatsapp_service import WhatsAppService
                    logger.info(f"Enviando WhatsApp para {fornecedor.nome} - Tel: {numero_whatsapp}")
                    ok, resp = WhatsAppService.enviar_mensagem(
                        telefone=numero_whatsapp,
                        texto=mensagem,
                        prioridade=1
                    )
                    if ok:
                        tipo_comunicacao = 'whatsapp'
                        sucesso = True
                        logger.info(f"WhatsApp enviado com sucesso para {fornecedor.nome}")
                    else:
                        logger.warning(f"WhatsApp falhou para {fornecedor.nome}: {resp}")
                except Exception as e:
                    logger.error(f"Erro ao enviar WhatsApp para {fornecedor.nome}: {e}", exc_info=True)

            # Enviar por Email (se canal preferido ou fallback)
            if not sucesso and fornecedor.email:
                try:
                    from app.services.email_service import EmailService
                    ok = EmailService.enviar_solicitacao_orcamento(pedido, fornecedor, mensagem, cc=current_user.email)
                    if ok:
                        tipo_comunicacao = 'email'
                        sucesso = True
                        logger.info(f"Email enviado com sucesso para {fornecedor.nome}")
                    else:
                        logger.warning(f"Email falhou para {fornecedor.nome}")
                except Exception as e:
                    logger.error(f"Erro ao enviar email para {fornecedor.nome}: {e}", exc_info=True)

            # Registrar comunicação
            if sucesso:
                comunicacao = ComunicacaoFornecedor(
                    pedido_compra_id=pedido_id,
                    fornecedor_id=fornecedor_id,
                    tipo_comunicacao=tipo_comunicacao,
                    direcao='enviado',
                    mensagem=mensagem,
                    status='enviado',
                    data_envio=datetime.now()
                )
                db.session.add(comunicacao)

                enviados.append({
                    'fornecedor': fornecedor.nome,
                    'canal': tipo_comunicacao
                })
            else:
                erros.append({
                    'fornecedor': fornecedor.nome,
                    'motivo': 'Sem WhatsApp ou Email cadastrado'
                })

        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': f'{len(enviados)} solicitações enviadas',
            'enviados': enviados,
            'erros': erros
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao solicitar orçamentos: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500


# =============================================================================
# ETAPA 4 — PAINEL DO SOLICITANTE
# =============================================================================

@bp.route('/painel-solicitante', methods=['GET', 'POST'])
@login_required
def painel_solicitante():
    """Painel simplificado para gerentes/técnicos solicitarem compras."""
    from app.models.models import Unidade

    if request.method == 'POST':
        descricao = request.form.get('descricao_livre', '').strip()
        categoria = request.form.get('categoria_compra', 'outros')
        quantidade = request.form.get('quantidade', 1)
        justificativa = request.form.get('justificativa', '').strip()
        estoque_id_form = request.form.get('estoque_id') or None
        unidade_id = request.form.get('unidade_id') or None

        if not descricao and not estoque_id_form:
            flash('Informe o item ou selecione um produto do catálogo.', 'warning')
            return redirect(url_for('compras.painel_solicitante'))

        pedido = PedidoCompra(
            estoque_id=int(estoque_id_form) if estoque_id_form else None,
            descricao_livre=descricao if not estoque_id_form else None,
            categoria_compra=categoria,
            quantidade=float(quantidade),
            justificativa=justificativa,
            unidade_destino_id=int(unidade_id) if unidade_id else current_user.unidade_id if hasattr(current_user, 'unidade_id') else None,
            solicitante_id=current_user.id,
            status='analise_cadastro' if not estoque_id_form else 'solicitado',
        )
        db.session.add(pedido)
        db.session.commit()
        flash('Solicitação enviada com sucesso!', 'success')
        return redirect(url_for('compras.painel_solicitante'))

    # Últimas solicitações do usuário
    minhas_solicitacoes = PedidoCompra.query.filter_by(
        solicitante_id=current_user.id
    ).order_by(PedidoCompra.data_solicitacao.desc()).limit(20).all()

    unidades = Unidade.query.order_by(Unidade.nome).all()

    # Todos os itens do catálogo para busca
    itens_rapidos = Estoque.query.order_by(Estoque.nome).all()

    # Listas padrão disponíveis para uso rápido
    listas = ListaCompra.query.filter_by(ativo=True).order_by(ListaCompra.nome).all()

    return render_template('compras/painel_solicitante.html',
                           minhas_solicitacoes=minhas_solicitacoes,
                           unidades=unidades,
                           itens_rapidos=itens_rapidos,
                           listas=listas)


# =============================================================================
# LISTAS DE COMPRA PADRÃO
# =============================================================================

@bp.route('/listas', methods=['GET'])
@login_required
def listas_compra():
    """Gerencia listas de compra padrão / recorrentes."""
    if current_user.tipo not in ['admin', 'gerente']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('ponto.index'))

    from app.models.models import Unidade
    listas = ListaCompra.query.filter_by(ativo=True).order_by(ListaCompra.nome).all()
    itens_catalogo = Estoque.query.order_by(Estoque.nome).all()
    unidades = Unidade.query.order_by(Unidade.nome).all()
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    return render_template('compras/listas.html',
                           listas=listas,
                           itens_catalogo=itens_catalogo,
                           unidades=unidades,
                           fornecedores=fornecedores)


@bp.route('/listas/nova', methods=['POST'])
@login_required
def nova_lista_compra():
    if current_user.tipo not in ['admin', 'gerente']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('ponto.index'))

    nome = request.form.get('nome', '').strip()
    descricao = request.form.get('descricao', '').strip()
    periodicidade = request.form.get('periodicidade_dias') or None

    if not nome:
        flash('Nome da lista é obrigatório.', 'warning')
        return redirect(url_for('compras.listas_compra'))

    lista = ListaCompra(
        nome=nome,
        descricao=descricao or None,
        periodicidade_dias=int(periodicidade) if periodicidade else None,
        criador_id=current_user.id,
    )
    db.session.add(lista)
    db.session.commit()
    flash(f'Lista "{nome}" criada com sucesso!', 'success')
    return redirect(url_for('compras.listas_compra'))


@bp.route('/listas/<int:lista_id>/excluir', methods=['POST'])
@login_required
def excluir_lista_compra(lista_id):
    if current_user.tipo not in ['admin', 'gerente']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('ponto.index'))

    lista = ListaCompra.query.get_or_404(lista_id)
    lista.ativo = False
    db.session.commit()
    flash('Lista arquivada.', 'info')
    return redirect(url_for('compras.listas_compra'))


@bp.route('/listas/<int:lista_id>/item/adicionar', methods=['POST'])
@login_required
def adicionar_item_lista(lista_id):
    if current_user.tipo not in ['admin', 'gerente']:
        return jsonify({'ok': False, 'erro': 'Acesso negado'}), 403

    lista = ListaCompra.query.get_or_404(lista_id)
    estoque_id = request.form.get('estoque_id') or None
    descricao = request.form.get('descricao_livre', '').strip()
    quantidade = request.form.get('quantidade', 1)
    categoria = request.form.get('categoria_compra', 'outros')
    fornecedor_id = request.form.get('fornecedor_id') or None

    if not estoque_id and not descricao:
        flash('Selecione um item do catálogo ou informe uma descrição.', 'warning')
        return redirect(url_for('compras.listas_compra'))

    item = ListaCompraItem(
        lista_id=lista.id,
        estoque_id=int(estoque_id) if estoque_id else None,
        descricao_livre=descricao if not estoque_id else None,
        quantidade=float(quantidade),
        categoria_compra=categoria,
        fornecedor_id=int(fornecedor_id) if fornecedor_id else None,
    )
    db.session.add(item)
    db.session.commit()
    return redirect(url_for('compras.listas_compra'))


@bp.route('/listas/item/<int:item_id>/remover', methods=['POST'])
@login_required
def remover_item_lista(item_id):
    if current_user.tipo not in ['admin', 'gerente']:
        return jsonify({'ok': False, 'erro': 'Acesso negado'}), 403

    item = ListaCompraItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


@bp.route('/listas/<int:lista_id>/usar', methods=['GET', 'POST'])
@login_required
def usar_lista_compra(lista_id):
    """Tela dedicada para revisar e enviar uma lista como uma única ordem de compra."""
    from app.models.models import Unidade
    if current_user.tipo not in ['admin', 'gerente', 'tecnico']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('ponto.index'))

    lista = ListaCompra.query.get_or_404(lista_id)

    if request.method == 'POST':
        unidade_id = request.form.get('unidade_id') or None
        observacao = request.form.get('observacao', '').strip() or None

        # Coleta itens selecionados
        itens_pedido = []
        for item_lista in lista.itens:
            if not request.form.get(f'incluir_{item_lista.id}'):
                continue
            try:
                qtd = float(request.form.get(f'quantidade_{item_lista.id}', 0))
            except (ValueError, TypeError):
                qtd = 0
            if qtd <= 0:
                continue
            itens_pedido.append((item_lista, qtd))

        if not itens_pedido:
            flash('Selecione ao menos um item com quantidade válida.', 'warning')
            unidades = Unidade.query.order_by(Unidade.nome).all()
            return render_template('compras/usar_lista.html', lista=lista, unidades=unidades)

        # Cria a OrdemCompraLista (entrada única no painel de compras)
        ordem = OrdemCompraLista(
            lista_id=lista.id,
            nome=lista.nome,
            solicitante_id=current_user.id,
            unidade_destino_id=int(unidade_id) if unidade_id else None,
            observacao=observacao,
        )
        db.session.add(ordem)
        db.session.flush()  # gera ordem.id

        for item_lista, qtd in itens_pedido:
            status = 'solicitado' if item_lista.estoque_id else 'analise_cadastro'
            pedido = PedidoCompra(
                estoque_id=item_lista.estoque_id,
                descricao_livre=item_lista.descricao_livre,
                categoria_compra=item_lista.categoria_compra,
                quantidade=qtd,
                fornecedor_id=item_lista.fornecedor_id,
                status=status,
                solicitante_id=current_user.id,
                unidade_destino_id=int(unidade_id) if unidade_id else None,
                ordem_lista_id=ordem.id,
            )
            db.session.add(pedido)

        db.session.commit()
        flash(f'Ordem "{lista.nome}" enviada com {len(itens_pedido)} iten(s) para o setor de compras!', 'success')
        return redirect(url_for('compras.painel_solicitante'))

    unidades = Unidade.query.order_by(Unidade.nome).all()
    return render_template('compras/usar_lista.html', lista=lista, unidades=unidades)


@bp.route('/ordens-lista/<int:ordem_id>')
@login_required
def ordem_lista_detalhes(ordem_id):
    """Detalhe de uma ordem de compra gerada a partir de uma lista padrão."""
    if current_user.tipo not in ['admin', 'comprador', 'gerente']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('ponto.index'))
    ordem = OrdemCompraLista.query.get_or_404(ordem_id)
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    return render_template('compras/ordem_lista.html', ordem=ordem, fornecedores=fornecedores)
