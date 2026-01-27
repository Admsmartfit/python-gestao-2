from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.estoque_models import PlanoManutencao, Equipamento, OrdemServico
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('manutencao', __name__, url_prefix='/manutencao')

@bp.route('/preventiva')
@login_required
def listar_planos():
    """Lista todos os planos de manutenção preventiva"""
    if current_user.tipo not in ['admin', 'gerente', 'tecnico']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('admin.dashboard'))

    planos = PlanoManutencao.query.order_by(PlanoManutencao.ativo.desc(), PlanoManutencao.nome).all()

    # Calcular próxima execução para cada plano
    for plano in planos:
        if plano.ultima_execucao:
            plano.proxima_execucao = plano.ultima_execucao + timedelta(days=plano.frequencia_dias)
            plano.dias_restantes = (plano.proxima_execucao - datetime.now()).days
        else:
            plano.proxima_execucao = None
            plano.dias_restantes = 0

    return render_template('manutencao/preventiva_lista.html', planos=planos)

@bp.route('/preventiva/novo', methods=['GET', 'POST'])
@login_required
def novo_plano():
    """Cria novo plano de manutenção preventiva"""
    if current_user.tipo not in ['admin', 'gerente']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('manutencao.listar_planos'))

    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo_aplicacao = request.form.get('tipo_aplicacao')
            frequencia_dias = int(request.form.get('frequencia_dias'))
            descricao_procedimento = request.form.get('descricao_procedimento')

            plano = PlanoManutencao(
                nome=nome,
                frequencia_dias=frequencia_dias,
                descricao_procedimento=descricao_procedimento,
                ativo=True
            )

            if tipo_aplicacao == 'equipamento':
                equipamento_id = request.form.get('equipamento_id')
                if equipamento_id:
                    plano.equipamento_id = int(equipamento_id)
            elif tipo_aplicacao == 'categoria':
                categoria = request.form.get('categoria_equipamento')
                plano.categoria_equipamento = categoria

            db.session.add(plano)
            db.session.commit()

            flash(f"Plano '{nome}' criado com sucesso!", "success")
            return redirect(url_for('manutencao.listar_planos'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar plano: {e}")
            flash(f"Erro ao criar plano: {str(e)}", "danger")

    # GET: Buscar equipamentos para o formulário
    equipamentos = Equipamento.query.filter_by(ativo=True).order_by(Equipamento.nome).all()

    return render_template('manutencao/preventiva_form.html',
                         equipamentos=equipamentos,
                         plano=None)

@bp.route('/preventiva/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_plano(id):
    """Edita plano de manutenção preventiva"""
    if current_user.tipo not in ['admin', 'gerente']:
        flash("Permissão negada.", "danger")
        return redirect(url_for('manutencao.listar_planos'))

    plano = PlanoManutencao.query.get_or_404(id)

    if request.method == 'POST':
        try:
            plano.nome = request.form.get('nome')
            plano.frequencia_dias = int(request.form.get('frequencia_dias'))
            plano.descricao_procedimento = request.form.get('descricao_procedimento')

            tipo_aplicacao = request.form.get('tipo_aplicacao')

            if tipo_aplicacao == 'equipamento':
                equipamento_id = request.form.get('equipamento_id')
                plano.equipamento_id = int(equipamento_id) if equipamento_id else None
                plano.categoria_equipamento = None
            elif tipo_aplicacao == 'categoria':
                categoria = request.form.get('categoria_equipamento')
                plano.categoria_equipamento = categoria
                plano.equipamento_id = None

            db.session.commit()

            flash(f"Plano '{plano.nome}' atualizado com sucesso!", "success")
            return redirect(url_for('manutencao.listar_planos'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar plano: {e}")
            flash(f"Erro ao editar plano: {str(e)}", "danger")

    equipamentos = Equipamento.query.filter_by(ativo=True).order_by(Equipamento.nome).all()

    return render_template('manutencao/preventiva_form.html',
                         equipamentos=equipamentos,
                         plano=plano)

@bp.route('/preventiva/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_plano(id):
    """Ativa/desativa plano de manutenção"""
    if current_user.tipo not in ['admin', 'gerente']:
        return jsonify({'success': False, 'erro': 'Permissão negada'}), 403

    try:
        plano = PlanoManutencao.query.get_or_404(id)
        plano.ativo = not plano.ativo
        db.session.commit()

        return jsonify({
            'success': True,
            'ativo': plano.ativo
        })
    except Exception as e:
        logger.error(f"Erro ao alterar status do plano: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500

@bp.route('/preventiva/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_plano(id):
    """Exclui plano de manutenção"""
    if current_user.tipo not in ['admin', 'gerente']:
        return jsonify({'success': False, 'erro': 'Permissão negada'}), 403

    try:
        plano = PlanoManutencao.query.get_or_404(id)
        nome = plano.nome

        db.session.delete(plano)
        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': f"Plano '{nome}' excluído com sucesso"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir plano: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500

@bp.route('/preventiva/<int:id>/executar', methods=['POST'])
@login_required
def executar_plano(id):
    """Cria OS baseada no plano de manutenção"""
    if current_user.tipo not in ['admin', 'gerente', 'tecnico']:
        return jsonify({'success': False, 'erro': 'Permissão negada'}), 403

    try:
        plano = PlanoManutencao.query.get_or_404(id)

        equipamentos_afetados = []

        # Determinar quais equipamentos receberão a OS
        if plano.equipamento_id:
            equipamentos_afetados = [plano.equipamento]
        elif plano.categoria_equipamento:
            equipamentos_afetados = Equipamento.query.filter_by(
                categoria=plano.categoria_equipamento,
                ativo=True
            ).all()

        if not equipamentos_afetados:
            return jsonify({
                'success': False,
                'erro': 'Nenhum equipamento encontrado para este plano'
            }), 400

        oss_criadas = []

        for equipamento in equipamentos_afetados:
            # Criar OS de manutenção preventiva
            os = OrdemServico(
                tipo='preventiva',
                prioridade='media',
                status='aberta',
                equipamento_id=equipamento.id,
                unidade_id=equipamento.unidade_id,
                descricao_problema=f"[MANUTENÇÃO PREVENTIVA] {plano.nome}",
                observacoes=plano.descricao_procedimento,
                tecnico_id=current_user.id,
                data_abertura=datetime.now()
            )

            db.session.add(os)
            oss_criadas.append({
                'equipamento': equipamento.nome,
                'unidade': equipamento.unidade.nome if equipamento.unidade else 'N/A'
            })

        # Atualizar última execução do plano
        plano.ultima_execucao = datetime.now()

        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': f'{len(oss_criadas)} OS(s) criada(s) com sucesso',
            'oss_criadas': oss_criadas
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao executar plano: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500

@bp.route('/preventiva/vencidos')
@login_required
def planos_vencidos():
    """API: Lista planos vencidos que precisam ser executados"""
    if current_user.tipo not in ['admin', 'gerente', 'tecnico']:
        return jsonify({'success': False, 'erro': 'Permissão negada'}), 403

    try:
        hoje = datetime.now()
        planos_ativos = PlanoManutencao.query.filter_by(ativo=True).all()

        vencidos = []

        for plano in planos_ativos:
            if plano.ultima_execucao:
                proxima_execucao = plano.ultima_execucao + timedelta(days=plano.frequencia_dias)
                if proxima_execucao <= hoje:
                    dias_atrasado = (hoje - proxima_execucao).days
                    vencidos.append({
                        'id': plano.id,
                        'nome': plano.nome,
                        'dias_atrasado': dias_atrasado,
                        'ultima_execucao': plano.ultima_execucao.strftime('%d/%m/%Y')
                    })
            else:
                # Nunca foi executado
                vencidos.append({
                    'id': plano.id,
                    'nome': plano.nome,
                    'dias_atrasado': 999,
                    'ultima_execucao': 'Nunca executado'
                })

        return jsonify({
            'success': True,
            'total': len(vencidos),
            'planos': vencidos
        })

    except Exception as e:
        logger.error(f"Erro ao buscar planos vencidos: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500
