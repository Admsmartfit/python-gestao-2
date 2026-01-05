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

            pedido = PedidoCompra(
                estoque_id=estoque_id,
                quantidade=quantidade,
                fornecedor_id=fornecedor_id if fornecedor_id else None,
                unidade_destino_id=unidade_id if unidade_id else None,
                solicitante_id=current_user.id,
                status='solicitado'
            )
            db.session.add(pedido)
            db.session.commit()
            
            flash(f"Pedido #{pedido.id} criado com sucesso!", "success")
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
    
    # Trigger email to supplier if configured
    from app.services.email_service import EmailService
    if pedido.fornecedor and pedido.fornecedor.email:
         EmailService.enviar_pedido_fornecedor(pedido)
         flash(f"Pedido #{id} aprovado e enviado para {pedido.fornecedor.nome}.", "success")
    else:
         flash(f"Pedido #{id} aprovado. (Fornecedor sem e-mail cadastrado)", "success")
         
    return redirect(url_for('compras.detalhes', id=id))
