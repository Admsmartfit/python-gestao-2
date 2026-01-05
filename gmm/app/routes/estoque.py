from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models.estoque_models import Estoque, EstoqueSaldo, MovimentacaoEstoque
from app.services.estoque_service import EstoqueService
from app.extensions import db

bp = Blueprint('estoque', __name__, url_prefix='/estoque')

@bp.route('/')
@login_required
def dashboard():
    """Painel global de estoque com Visão ABC e Alertas (RF-011)"""
    # 1. Obter saldos totais
    itens = Estoque.query.order_by(Estoque.nome).all()
    
    # 2. Curva ABC
    dados_abc, total_valor = EstoqueService.gerar_curva_abc()
    
    # 3. Alertas de estoque crítico
    criticos = Estoque.query.filter(Estoque.quantidade_atual <= Estoque.quantidade_minima).all()
    
    # 4. Movimentações recentes
    recentes = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).limit(10).all()
    
    return render_template('estoque/dashboard.html', 
                         itens=itens, 
                         dados_abc=dados_abc, 
                         total_valor=total_valor,
                         criticos=criticos,
                         recentes=recentes)

@bp.route('/movimentacoes')
@login_required
def movimentacoes():
    """Histórico completo de movimentações com paginação"""
    page = request.args.get('page', 1, type=int)
    movs = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).paginate(page=page, per_page=50)
    return render_template('estoque/movimentacoes.html', movs=movs)

@bp.route('/api/pecas')
@login_required
def api_pecas():
    """API simples para busca de peças no frontend"""
    q = request.args.get('q', '')
    query = Estoque.query
    if q:
        query = query.filter(Estoque.nome.ilike(f'%{q}%'))
    
    pecas = query.limit(10).all()
    return jsonify([{'id': p.id, 'nome': p.nome, 'codigo': p.codigo, 'qtd': float(p.quantidade_atual)} for p in pecas])
