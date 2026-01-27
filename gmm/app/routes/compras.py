from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.estoque_models import PedidoCompra, Fornecedor, Estoque, CatalogoFornecedor
from app.extensions import db
from datetime import datetime
import logging

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
    return render_template('compras/lista.html', pedidos=pedidos, status_atual=status_filter)

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
            if valor_total <= 500:
                status_inicial = 'aprovado'
                aprovador_id = 0 # Sistema

            pedido = PedidoCompra(
                estoque_id=estoque_id,
                quantidade=int(quantidade),
                fornecedor_id=fornecedor_id if fornecedor_id else None,
                unidade_destino_id=unidade_id if unidade_id else None,
                solicitante_id=current_user.id,
                status=status_inicial,
                aprovador_id=aprovador_id
            )
            db.session.add(pedido)
            db.session.commit()
            
            # Se aprovado automaticamente, já pode disparar o envio
            if pedido.status == 'aprovado':
                from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
                enviar_pedido_fornecedor.delay(pedido.id)
                msg_adic = " (Aprovado automaticamente)"
            else:
                msg_adic = ""

            flash(f"Pedido #{pedido.id} criado com sucesso!{msg_adic}", "success")
            return redirect(url_for('compras.listar'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar pedido: {e}")
            flash("Erro ao processar pedido.", "danger")

    pecas = Estoque.query.order_by(Estoque.nome).all()
    fornecedores = Fornecedor.query.order_by(Fornecedor.nome).all()
    from app.models.models import Unidade
    unidades = Unidade.query.all()
    
    return render_template('compras/novo.html', pecas=pecas, fornecedores=fornecedores, unidades=unidades)

@bp.route('/<int:id>')
@login_required
def detalhes(id):
    """View order details and quotes"""
    pedido = PedidoCompra.query.get_or_404(id)
    # Get other quotes for this item
    quotes = CatalogoFornecedor.query.filter_by(estoque_id=pedido.estoque_id).order_by(CatalogoFornecedor.preco_atual).all()
    
    return render_template('compras/detalhes.html', pedido=pedido, quotes=quotes)

@bp.route('/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar(id):
    """Manager approval of the request"""
    if current_user.tipo not in ['admin', 'gerente']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('compras.detalhes', id=id))
        
    pedido = PedidoCompra.query.get_or_404(id)
    if pedido.status != 'solicitado':
        flash("Este pedido já foi processado.", "info")
        return redirect(url_for('compras.detalhes', id=id))

    pedido.status = 'aprovado'
    pedido.aprovador_id = current_user.id
    db.session.commit()
    
    # Trigger PDF generation and sending via Celery
    from app.tasks.whatsapp_tasks import enviar_pedido_fornecedor
    enviar_pedido_fornecedor.delay(pedido.id)
    
    flash(f"Pedido #{id} aprovado. O processamento do PDF e envio foi iniciado.", "success")
         
    return redirect(url_for('compras.detalhes', id=id))

@bp.route('/<int:id>/receber', methods=['POST'])
@login_required
def receber(id):
    """US-011: Registra recebimento da compra e notifica solicitante."""
    pedido = PedidoCompra.query.get_or_404(id)
    
    if pedido.status == 'recebido':
        flash("Este pedido já foi recebido.", "info")
        return redirect(url_for('compras.detalhes', id=id))

    # 1. Atualiza Estoque
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

    # 3. Notifica Solicitante (US-011)
    from app.services.whatsapp_service import WhatsAppService
    if pedido.solicitante and pedido.solicitante.telefone:
        msg = f"📦 *CHEGOU!*\n\nO item *{pedido.estoque.nome}* do seu pedido #{pedido.id} acaba de ser recebido no estoque."
        WhatsAppService.enviar_mensagem(pedido.solicitante.telefone, msg)

    flash(f"Pedido #{id} marcado como recebido. Estoque atualizado e solicitante notificado.", "success")
    return redirect(url_for('compras.detalhes', id=id))

# [NOVO] Buscar Fornecedores por Item de Estoque
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
            todos_fornecedores = Fornecedor.query.all()
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
