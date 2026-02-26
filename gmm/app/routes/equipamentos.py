from flask import Blueprint, render_template, request, abort, jsonify, redirect, url_for, flash
from flask_login import login_required
from app.models.estoque_models import Equipamento, OrdemServico, MovimentacaoEstoque
from app.extensions import db
from sqlalchemy import desc

bp = Blueprint('equipamentos', __name__, url_prefix='/equipamentos')

@bp.route('/')
@login_required
def listar():
    """Lista todos os equipamentos com busca simples"""
    q = request.args.get('q', '')
    query = Equipamento.query
    if q:
        query = query.filter(Equipamento.nome.ilike(f'%{q}%'))
    
    equipamentos = query.order_by(Equipamento.nome).all()
    return render_template('equipamentos_lista.html', equipamentos=equipamentos)

@bp.route('/<int:id>')
@login_required
def detalhes(id):
    """Dossiê completo do equipamento (RF-004)"""
    equipamento = Equipamento.query.get_or_404(id)
    
    # 1. Histórico de Manutenções
    historico_os = OrdemServico.query.filter_by(equipamento_id=id)\
        .order_by(OrdemServico.data_abertura.desc()).all()
    
    # 2. Peças Trocadas (Via Movimentações ligadas às OSs do equipamento)
    pecas_trocadas = MovimentacaoEstoque.query.join(OrdemServico)\
        .filter(OrdemServico.equipamento_id == id, MovimentacaoEstoque.tipo_movimentacao == 'consumo')\
        .order_by(MovimentacaoEstoque.data_movimentacao.desc()).all()
    
    # 3. KPIs Locais
    total_custo_pecas = sum([m.quantidade * (m.estoque.valor_unitario or 0) for m in pecas_trocadas])
    qtd_os = len(historico_os)
    
    # MTBF Simplificado (Tempo total / Qtd falhas corretivas)
    corretivas = [os for os in historico_os if os.tipo_manutencao == 'corretiva']
    mtbf = "N/A"
    if len(corretivas) > 1:
        # Pega a data da primeira e da última OS corretiva
        delta = corretivas[0].data_abertura - corretivas[-1].data_abertura
        dias = delta.days
        # Evita divisão por zero
        divisor = len(corretivas) - 1 if len(corretivas) > 1 else 1
        media_dias = dias // divisor
        mtbf = f"{media_dias} dias"

    return render_template('equipamento_detalhe.html', 
                         eq=equipamento,
                         historico_os=historico_os,
                         pecas=pecas_trocadas,
                         kpis={
                             'custo_total': total_custo_pecas,
                             'qtd_os': qtd_os,
                             'mtbf': mtbf
                         })

@bp.route('/<int:id>/gerar-qr')
@login_required
def gerar_qr(id):
    """Gera o arquivo de QR Code no servidor (conforme PRD v3.1)"""
    from app.services.qr_service import QRService

    Equipamento.query.get_or_404(id)
    try:
        path = QRService.gerar_etiqueta_equipamento(id)
        return redirect(path)
    except Exception as e:
        flash(f'Erro ao gerar QR Code: {str(e)}', 'danger')
        return redirect(url_for('equipamentos.detalhes', id=id))


@bp.route('/<int:id>/vincular-qr', methods=['POST'])
@login_required
def vincular_qr_externo(id):
    """Vincula um QR code externo (de outra empresa) a este equipamento."""
    equipamento = Equipamento.query.get_or_404(id)
    codigo = (request.json or {}).get('codigo', '').strip()

    if not codigo:
        return jsonify({'ok': False, 'msg': 'Código não informado.'}), 400

    # Checar se já está vinculado a outro equipamento
    existente = Equipamento.query.filter(
        Equipamento.qrcode_externo == codigo,
        Equipamento.id != id
    ).first()
    if existente:
        return jsonify({'ok': False, 'msg': f'QR já vinculado ao equipamento "{existente.nome}" (#{existente.id}).'}), 409

    equipamento.qrcode_externo = codigo
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'QR code externo vinculado com sucesso.'})


@bp.route('/<int:id>/desvincular-qr', methods=['POST'])
@login_required
def desvincular_qr_externo(id):
    """Remove o vínculo do QR code externo deste equipamento."""
    equipamento = Equipamento.query.get_or_404(id)
    equipamento.qrcode_externo = None
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'QR code externo removido.'})


@bp.route('/api/buscar-por-qr')
@login_required
def buscar_por_qr():
    """Lookup de equipamento pelo conteúdo de um QR code externo."""
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({'encontrado': False}), 400

    equipamento = Equipamento.query.filter_by(qrcode_externo=codigo, ativo=True).first()
    if not equipamento:
        return jsonify({'encontrado': False})

    return jsonify({
        'encontrado': True,
        'id': equipamento.id,
        'nome': equipamento.nome,
        'categoria': equipamento.categoria,
        'unidade': equipamento.unidade.nome if equipamento.unidade else ''
    })
