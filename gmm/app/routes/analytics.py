from flask import Blueprint, render_template, jsonify, request, send_file
from flask_login import login_required, current_user
from app.services.analytics_service import AnalyticsService
from app.models.models import Unidade, Usuario
from datetime import datetime, timedelta
import csv
import io

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

# ── v4.0: Importações para analytics de compras ────────────────────────────
from app.models.estoque_models import PedidoCompra, Fornecedor, OrcamentoUnidade, AprovacaoPedido

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.tipo not in ['admin', 'gerente', 'comprador']:
        return render_template('errors/403.html'), 403
    
    unidades = Unidade.query.filter_by(ativa=True).all()
    return render_template('analytics/dashboard.html', unidades=unidades)

@bp.route('/desempenho-tecnico')
@login_required
def desempenho_tecnico():
    if current_user.tipo not in ['admin', 'gerente', 'comprador']:
        return render_template('errors/403.html'), 403
    
    unidades = Unidade.query.filter_by(ativa=True).all()
    # Passamos a data de início padrão calculada no backend
    data_inicio = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    return render_template('analytics/performance_tecnica.html', 
                         unidades=unidades, 
                         data_inicio_padrao=data_inicio)

@bp.route('/compras')
@login_required
def compras_bi():
    """Dashboard de BI de Compras — v4.0"""
    if current_user.tipo not in ['admin', 'gerente', 'comprador', 'diretor']:
        return render_template('errors/403.html'), 403
    unidades = Unidade.query.filter_by(ativa=True).all()
    return render_template('analytics/compras.html', unidades=unidades)


@bp.route('/api/compras/budget')
@login_required
def api_compras_budget():
    """Budget Tracking: orçado vs empenhado vs realizado por unidade no mês."""
    from sqlalchemy import func, extract
    from app.extensions import db

    ano = request.args.get('ano', datetime.utcnow().year, type=int)
    mes = request.args.get('mes', datetime.utcnow().month, type=int)

    # Orçado por unidade
    orcados = db.session.query(
        OrcamentoUnidade.unidade_id,
        func.sum(OrcamentoUnidade.valor_orcado).label('orcado')
    ).filter_by(ano=ano, mes=mes).group_by(OrcamentoUnidade.unidade_id).all()

    # Empenhado = pedidos aprovados/faturados no mês
    empenhados = db.session.query(
        PedidoCompra.unidade_destino_id,
        func.sum(PedidoCompra.valor_total_estimado).label('empenhado')
    ).filter(
        PedidoCompra.status.in_(['aprovado', 'faturado', 'recebido']),
        extract('year', PedidoCompra.data_solicitacao) == ano,
        extract('month', PedidoCompra.data_solicitacao) == mes
    ).group_by(PedidoCompra.unidade_destino_id).all()

    unidades_map = {u.id: u.nome for u in Unidade.query.all()}
    orcado_map = {r.unidade_id: float(r.orcado or 0) for r in orcados}
    emp_map = {r.unidade_destino_id: float(r.empenhado or 0) for r in empenhados}

    all_ids = set(orcado_map) | set(emp_map)
    result = []
    for uid in all_ids:
        result.append({
            'unidade': unidades_map.get(uid, f'Unidade {uid}'),
            'orcado': orcado_map.get(uid, 0),
            'empenhado': emp_map.get(uid, 0),
        })
    return jsonify(sorted(result, key=lambda x: x['unidade']))


@bp.route('/api/compras/leadtime')
@login_required
def api_compras_leadtime():
    """Lead time médio: Solicitação → Aprovação → Recebimento."""
    from sqlalchemy import func
    from app.extensions import db

    dias = request.args.get('dias', 90, type=int)
    desde = datetime.utcnow() - timedelta(days=dias)

    pedidos = PedidoCompra.query.filter(
        PedidoCompra.data_solicitacao >= desde,
        PedidoCompra.status.in_(['recebido', 'faturado'])
    ).all()

    lt_aprovacao = []
    lt_recebimento = []
    for p in pedidos:
        aprovacao = AprovacaoPedido.query.filter_by(pedido_id=p.id, acao='aprovado').order_by(
            AprovacaoPedido.created_at).first()
        if aprovacao:
            lt_aprovacao.append((aprovacao.created_at - p.data_solicitacao).total_seconds() / 3600)
        if p.data_recebimento and p.data_solicitacao:
            lt_recebimento.append((p.data_recebimento - p.data_solicitacao).total_seconds() / 3600)

    avg = lambda lst: round(sum(lst) / len(lst), 1) if lst else 0
    return jsonify({
        'media_horas_aprovacao': avg(lt_aprovacao),
        'media_horas_recebimento': avg(lt_recebimento),
        'total_pedidos': len(pedidos)
    })


@bp.route('/api/compras/fornecedores-ranking')
@login_required
def api_fornecedores_ranking():
    """Ranking de fornecedores por rating médio e pontualidade."""
    from sqlalchemy import func
    from app.extensions import db

    ranking = db.session.query(
        Fornecedor.id,
        Fornecedor.nome,
        func.avg(PedidoCompra.rating_fornecedor).label('rating_medio'),
        func.count(PedidoCompra.id).label('total_pedidos'),
        func.sum(
            db.case((
                db.and_(
                    PedidoCompra.data_recebimento.isnot(None),
                    PedidoCompra.data_entrega_prevista.isnot(None),
                    PedidoCompra.data_recebimento <= PedidoCompra.data_entrega_prevista
                ), 1
            ), else_=0)
        ).label('entregas_no_prazo')
    ).join(PedidoCompra, PedidoCompra.fornecedor_id == Fornecedor.id).filter(
        PedidoCompra.status.in_(['recebido', 'faturado'])
    ).group_by(Fornecedor.id, Fornecedor.nome).having(func.count(PedidoCompra.id) > 0).all()

    result = []
    for r in ranking:
        result.append({
            'id': r.id,
            'nome': r.nome,
            'rating_medio': round(float(r.rating_medio or 0), 1),
            'total_pedidos': r.total_pedidos,
            'entregas_no_prazo': int(r.entregas_no_prazo or 0),
            'pct_pontualidade': round(int(r.entregas_no_prazo or 0) / r.total_pedidos * 100, 0) if r.total_pedidos else 0
        })
    result.sort(key=lambda x: x['rating_medio'], reverse=True)
    return jsonify({'top': result[:5], 'bottom': list(reversed(result))[:5]})


@bp.route('/api/compras/orcamento/salvar', methods=['POST'])
@login_required
def salvar_orcamento():
    """Salva ou atualiza orçamento de uma unidade."""
    if current_user.tipo not in ['admin', 'gerente']:
        return jsonify({'error': 'Permissão negada'}), 403
    data = request.json
    from app.extensions import db
    orc = OrcamentoUnidade.query.filter_by(
        unidade_id=data['unidade_id'], ano=data['ano'], mes=data['mes']
    ).first()
    if not orc:
        orc = OrcamentoUnidade(unidade_id=data['unidade_id'], ano=data['ano'], mes=data['mes'],
                               criado_por_id=current_user.id)
        db.session.add(orc)
    orc.valor_orcado = float(data.get('valor_orcado', 0))
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/api/kpi/geral')
@login_required
def api_kpi_geral():
    unidade_id = request.args.get('unidade_id', type=int)
    days = request.args.get('days', default=30, type=int)
    
    if current_user.tipo == 'gerente' and not unidade_id:
        unidade_id = current_user.unidade_padrao_id
        
    kpis = AnalyticsService.get_kpi_geral(unidade_id, days)
    stock = AnalyticsService.get_stock_metrics(unidade_id)
    kpis.update(stock)
    
    return jsonify(kpis)

@bp.route('/api/charts/custos')
@login_required
def api_charts_custos():
    unidade_id = request.args.get('unidade_id', type=int)
    days = request.args.get('days', default=30, type=int)
    
    data = AnalyticsService.get_cost_evolution(unidade_id, days)
    return jsonify(data)

@bp.route('/api/tecnicos/performance')
@login_required
def api_tecnicos_performance():
    unidade_id = request.args.get('unidade_id', type=int)
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if start_str and end_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
    data = AnalyticsService.get_performance_tecnicos(start_date, end_date, unidade_id)
    return jsonify(data)

@bp.route('/api/tecnicos/<int:usuario_id>/logs-diarios')
@login_required
def api_tecnico_logs_diarios(usuario_id):
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if start_str and end_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
    data = AnalyticsService.get_daily_logs(usuario_id, start_date, end_date)
    return jsonify(data)

@bp.route('/api/export/csv')
@login_required
def export_csv():
    # Similar ao performance técnicos mas retorna arquivo
    unidade_id = request.args.get('unidade_id', type=int)
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if start_str and end_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d')
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
    data = AnalyticsService.get_performance_tecnicos(start_date, end_date, unidade_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Técnico', 'Horas Ponto', 'Horas OS', 'Ociosidade %', 'Custo Peças', 'OS Concluídas'])
    
    for row in data:
        writer.writerow([
            row['tecnico_nome'],
            row['horas_ponto'],
            row['horas_os'],
            row['ociosidade_percentual'],
            row['custo_pecas'],
            row['os_concluidas']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'performance_tecnica_{start_date.strftime("%Y%m%d")}.csv'
    )
