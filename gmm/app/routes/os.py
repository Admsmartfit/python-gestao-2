import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime

logger = logging.getLogger(__name__)
from app.extensions import db
from app.models.models import Unidade, Usuario
from app.models.estoque_models import OrdemServico, Estoque, CategoriaEstoque, Equipamento, AnexosOS, PedidoCompra, EstoqueSaldo, MovimentacaoEstoque, Fornecedor
from app.models.terceirizados_models import Terceirizado, ChamadoExterno
from app.services.os_service import OSService
from app.services.estoque_service import EstoqueService
from app.services.email_service import EmailService
from app.models.terceirizados_models import HistoricoNotificacao


bp = Blueprint('os', __name__, url_prefix='/os')

@bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova_os():
    if request.method == 'POST':
        try:
            prazo_str = request.form.get('prazo_conclusao')
            prazo_dt = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M') if prazo_str else None
            
            nova_os = OrdemServico(
                numero_os=OSService.gerar_numero_os(),
                tecnico_id=request.form.get('tecnico_id'),
                unidade_id=request.form.get('unidade_id'),
                equipamento_id=request.form.get('equipamento_id'),
                prazo_conclusao=prazo_dt,
                tipo_manutencao=request.form.get('tipo_manutencao'),
                prioridade=request.form.get('prioridade'),
                descricao_problema=request.form.get('descricao_problema'),
                status='aberta',
                origem_criacao='web'
            )

            # US-005: Se o prazo não foi informado manualmente, calcula pelo SLA
            if not nova_os.prazo_conclusao:
                nova_os.prazo_conclusao = OSService.calcular_sla(nova_os.prioridade)
            
            db.session.add(nova_os)
            db.session.commit() # Commit para gerar o ID da OS
            
            # Processar Fotos (Agora salva na tabela anexos_os e retorna lista pro JSON)
            fotos = request.files.getlist('fotos_antes')
            if fotos and fotos[0].filename != '':
                caminhos = OSService.processar_fotos(fotos, nova_os.id, tipo='foto_antes')
                nova_os.fotos_antes = caminhos
                db.session.commit()

            db.session.commit()

            flash(f'OS {nova_os.numero_os} criada com sucesso!', 'success')
            return redirect(url_for('os.detalhes', id=nova_os.id))
            
        except ValueError:
            db.session.rollback()
            flash('Erro no formato da data do prazo.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar OS: {str(e)}', 'danger')

    unidades = Unidade.query.filter_by(ativa=True).all()
    tecnicos = Usuario.query.filter(Usuario.tipo.in_(['tecnico', 'admin'])).all()

    # Suporte para pré-seleção via query string (QR Code)
    equipamento_id = request.args.get('equipamento_id', type=int)
    equipamento_preselect = None
    if equipamento_id:
        equipamento_preselect = Equipamento.query.get(equipamento_id)

    return render_template('os_nova.html',
                          unidades=unidades,
                          tecnicos=tecnicos,
                          equipamento_preselect=equipamento_preselect)
    
@bp.route('/<int:id>', methods=['GET'])
@login_required
def detalhes(id):
    os_obj = OrdemServico.query.get_or_404(id)
    categorias = CategoriaEstoque.query.all()
    
    # Carregar todas as peças para o modal de solicitação
    todas_pecas = Estoque.query.order_by(Estoque.nome).all()
    
    # Filtra terceirizados: Globais (abrangencia_global=True) OU que atendam a Unidade da OS
    terceirizados = Terceirizado.query.filter(
        (Terceirizado.abrangencia_global == True) | 
        (Terceirizado.unidades.any(id=os_obj.unidade_id))
    ).filter_by(ativo=True).order_by(Terceirizado.nome).all()

    # [Novo] Carrega usuários para o select de notificação na transferência
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    
    return render_template('os_detalhes.html', 
                         os=os_obj, 
                         categorias=categorias,
                         todas_pecas=todas_pecas,
                         terceirizados=terceirizados,
                         usuarios=usuarios)

@bp.route('/<int:id>/iniciar', methods=['POST'])
@login_required
def iniciar_os(id):
    """US-004: Registra o início da execução da OS."""
    os_obj = OrdemServico.query.get_or_404(id)
    
    if os_obj.status != 'aberta':
        flash('Esta OS já foi iniciada ou concluída.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    os_obj.status = 'em_andamento'
    os_obj.data_inicio = datetime.now()
    db.session.commit()
    
    # US-010: Notificar solicitante que OS começou
    from app.services.whatsapp_service import WhatsAppService
    if os_obj.unidade and os_obj.unidade.telefone:
        msg = f"🛠️ *OS INICIADA*\n\nA OS #{os_obj.numero_os} ({os_obj.titulo or os_obj.equipamento_rel.nome}) foi iniciada pelo técnico."
        WhatsAppService.enviar_mensagem(os_obj.unidade.telefone, msg)

    flash('OS iniciada! O tempo de execução está sendo contabilizado.', 'success')
    return redirect(url_for('os.detalhes', id=id))

@bp.route('/<int:id>/concluir', methods=['POST'])
@login_required
def concluir_os(id):
    os_obj = OrdemServico.query.get_or_404(id)
    
    if os_obj.status == 'concluida':
        flash('Esta OS já está concluída.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    solucao = request.form.get('descricao_solucao')
    
    # Processar fotos do "Depois"
    fotos = request.files.getlist('fotos_depois')
    if fotos and fotos[0].filename != '':
        caminhos = OSService.processar_fotos(fotos, os_obj.id, tipo='foto_depois')
        os_obj.fotos_depois = caminhos

    # US-004: Calcular tempo de execução em minutos
    # if os_obj.data_inicio:
    #     delta = datetime.now() - os_obj.data_inicio
    #     minutos = int(delta.total_seconds() / 60)
    #     os_obj.tempo_execucao_minutos = (os_obj.tempo_execucao_minutos or 0) + minutos

    os_obj.descricao_solucao = solucao
    os_obj.status = 'concluida'
    os_obj.data_conclusao = datetime.now()
    
    db.session.commit()

    # US-010: Notificar conclusão
    from app.services.whatsapp_service import WhatsAppService
    if os_obj.unidade and os_obj.unidade.telefone:
        msg = f"✅ *OS CONCLUÍDA*\n\nA OS #{os_obj.numero_os} foi finalizada.\n\n*Solução:* {solucao}"
        WhatsAppService.enviar_mensagem(os_obj.unidade.telefone, msg)

    flash('Ordem de Serviço concluída com sucesso!', 'success')
    return redirect(url_for('os.detalhes', id=id))

@bp.route('/<int:id>/adicionar-peca', methods=['POST'])
@login_required
def adicionar_peca(id):
    data = request.get_json()
    try:
        # Atualizado para receber o flag de alerta
        novo_saldo, alerta_minimo = EstoqueService.consumir_item(
            os_id=id,
            estoque_id=data['estoque_id'],
            quantidade=data['quantidade'],
            usuario_id=current_user.id
        )
        os_obj = OrdemServico.query.get(id)
        
        msg = "Peça adicionada."
        if alerta_minimo:
            msg += " ATENÇÃO: Item atingiu estoque mínimo!"

        return jsonify({
            'success': True, 
            'novo_estoque': float(novo_saldo), 
            'custo_total_os': float(os_obj.custo_total),
            'mensagem': msg,
            'alerta': alerta_minimo
        })
    except Exception as e:
        erro_msg = str(e)
        os_obj = OrdemServico.query.get(id)
        
        # Se o erro sugerir transferência ou compra, retornamos dados extras
        if os_obj:
            estoque_id = data.get('estoque_id')
            qtd_pedida = float(data.get('quantidade', 0))
            item = Estoque.query.get(estoque_id)
            
            if item:
                if "Solicite transferência" in erro_msg or "Solicite compra" in erro_msg:
                    # Busca distribuição
                    saldos = EstoqueSaldo.query.filter(
                        EstoqueSaldo.estoque_id == estoque_id,
                        EstoqueSaldo.quantidade > 0
                    ).all()
                    
                    sugestoes = []
                    for s in saldos:
                        if s.unidade_id != os_obj.unidade_id:
                            sugestoes.append({
                                'unidade_id': s.unidade_id,
                                'unidade_nome': s.unidade.nome,
                                'saldo': float(s.quantidade)
                            })
                    
                    return jsonify({
                        'success': False,
                        'erro': erro_msg,
                        'sugestoes_transferencia': sugestoes,
                        'unidade_destino_id': os_obj.unidade_id,
                        'unidade_destino_nome': os_obj.unidade.nome,
                        'quantidade_solicitada': qtd_pedida
                    }), 400
                
        return jsonify({'success': False, 'erro': erro_msg}), 400

@bp.route('/<int:id>/solicitar-compra-peca', methods=['POST'])
@login_required
def solicitar_compra_peca(id):
    """Cria uma solicitação de compra (PedidoCompra) vinculada à peça."""
    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        quantidade = data.get('quantidade')
        
        if not estoque_id or not quantidade or float(quantidade) <= 0:
            return jsonify({'success': False, 'erro': 'Quantidade deve ser maior que zero.'}), 400

        item = Estoque.query.get(estoque_id)
        if not item:
            return jsonify({'success': False, 'erro': 'Item não encontrado.'}), 404

        from app.models.estoque_models import CatalogoFornecedor, Fornecedor
        
        # 1. Tenta buscar no catálogo vinculado
        cat = CatalogoFornecedor.query.filter_by(estoque_id=estoque_id).first()
        if cat:
            fornecedor_id = cat.fornecedor_id
        else:
            # 2. Tenta buscar qualquer fornecedor disponível
            f = Fornecedor.query.first()
            if not f:
                return jsonify({'success': False, 'erro': 'Nenhum fornecedor cadastrado no sistema.'}), 400
            fornecedor_id = f.id

        # US-006: Cálculo de valor e Aprovação Automática
        valor_unitario = float(item.valor_unitario or 0)
        valor_total = valor_unitario * float(quantidade)
        
        status_inicial = 'pendente'
        aprovador_id = None

        if valor_total <= 500:
            status_inicial = 'aprovado'
            aprovador_id = 0 # ID 0 ou ID do sistema para aprovacao automatica

        # Buscar unidade da OS para vincular ao pedido
        os_obj = OrdemServico.query.get(id)
        unidade_os_id = os_obj.unidade_id if os_obj else None

        novo_pedido = PedidoCompra(
            fornecedor_id=fornecedor_id,
            estoque_id=estoque_id,
            quantidade=int(quantidade),
            status=status_inicial,
            data_solicitacao=datetime.now(),
            solicitante_id=current_user.id,
            aprovador_id=aprovador_id,
            unidade_destino_id=unidade_os_id
        )
        
        db.session.add(novo_pedido)
        db.session.commit()

        # Notificar setor de compras por email
        try:
            # Busca nome do solicitante
            solicitante_nome = current_user.username
            if hasattr(current_user, 'nome') and current_user.nome:
                solicitante_nome = current_user.nome

            EmailService.notify_purchase_request(
                novo_pedido, 
                item.nome, 
                solicitante_nome
            )
        except Exception as e:
            # Logar erro mas não impedir o retorno de sucesso do pedido
            print(f"Erro ao enviar email de notificação: {e}")
        
        return jsonify({
            'success': True,
            'mensagem': f'Pedido #{novo_pedido.id} criado'
        })

    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 400

# [NOVA ROTA] Entrada de Estoque (Restock)
@bp.route('/api/estoque/entrada', methods=['POST'])
@login_required
def entrada_estoque():
    """Registra entrada de novas peças (compra/reposição)."""
    if current_user.tipo not in ['admin', 'gerente', 'tecnico', 'comprador']:
         return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        quantidade = data.get('quantidade')
        unidade_id = data.get('unidade_id')
        motivo = data.get('motivo')
        valor_novo = data.get('valor_novo')

        if not estoque_id or not quantidade:
            return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400

        novo_saldo = EstoqueService.repor_estoque(
            estoque_id=estoque_id,
            quantidade=quantidade,
            usuario_id=current_user.id,
            motivo=motivo,
            unidade_id=unidade_id,
            valor_novo=valor_novo
        )
        return jsonify({'success': True, 'novo_saldo': float(novo_saldo)})
    except ValueError as e:
        return jsonify({'success': False, 'erro': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'erro': f"Erro interno: {str(e)}"}), 500

# [NOVA ROTA] Upload de Anexos em OS Aberta
@bp.route('/<int:id>/anexos', methods=['POST'])
@login_required
def upload_anexos(id):
    os_obj = OrdemServico.query.get_or_404(id)
    if os_obj.status in ['concluida', 'cancelada']:
        flash('Não é possível anexar arquivos a uma OS fechada.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    fotos = request.files.getlist('fotos')
    if fotos:
        try:
            OSService.processar_fotos(fotos, os_obj.id, tipo='documento') # ou 'foto_extra'
            db.session.commit()
            flash('Arquivos anexados com sucesso!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash(f'Erro no upload: {str(e)}', 'danger')
            
    return redirect(url_for('os.detalhes', id=id))
    
@bp.route('/api/estoque/<int:id>/disponibilidade')
@login_required
def disponibilidade_estoque(id):
    """
    API para verificar saldo global e distribuição por unidade de um item.
    """
    item = Estoque.query.get_or_404(id)
    saldos = EstoqueSaldo.query.filter_by(estoque_id=id).all()
    
    distribuicao = []
    for s in saldos:
        if s.quantidade > 0:
            distribuicao.append({
                'unidade_id': s.unidade_id,
                'unidade_nome': s.unidade.nome,
                'saldo': float(s.quantidade),
                'localizacao': s.localizacao or '-'
            })
            
    saldo_global = float(item.quantidade_atual)
    
    return jsonify({
        'item_id': item.id,
        'item_nome': item.nome,
        'saldo_global': saldo_global,
        'unidade_medida': item.unidade_medida,
        'distribuicao': distribuicao,
        'recomendacao': 'transferencia' if saldo_global > 0 else 'compra'
    })

@bp.route('/api/pecas/buscar')
@login_required
def buscar_pecas():
    termo = request.args.get('q', '')
    if len(termo) < 2: return jsonify([])
    pecas = Estoque.query.filter(Estoque.nome.ilike(f'%{termo}%')).limit(10).all()
    return jsonify([{'id': p.id, 'nome': p.nome, 'unidade': p.unidade_medida, 'saldo': float(p.quantidade_atual)} for p in pecas])


@bp.route('/api/pecas/<int:peca_id>/disponibilidade')
@login_required
def verificar_disponibilidade_peca(peca_id):
    """
    Verifica disponibilidade global de uma peça em todas as unidades.
    Retorna informações para decidir entre Transferência ou Compra.

    Returns:
        {
            'tem_estoque_local': bool,
            'saldo_local': float,
            'tem_estoque_outras_unidades': bool,
            'outras_unidades': [
                {
                    'unidade_id': int,
                    'unidade_nome': str,
                    'saldo': float
                }
            ],
            'saldo_global_total': float,
            'recomendacao': 'consumir' | 'transferir' | 'comprar'
        }
    """
    try:
        # Busca a peça principal
        peca = Estoque.query.get_or_404(peca_id)

        # Saldo na unidade atual (da peça selecionada)
        saldo_local = float(peca.quantidade_atual)
        unidade_local_id = peca.unidade_id

        # Busca saldos em outras unidades (mesmo nome de peça)
        outras_unidades = []
        saldo_global = 0

        # Query: Busca todas as peças com mesmo nome em outras unidades
        pecas_outras_unidades = Estoque.query.filter(
            Estoque.nome == peca.nome,
            Estoque.unidade_id != unidade_local_id,
            Estoque.quantidade_atual > 0
        ).all()

        for p in pecas_outras_unidades:
            saldo = float(p.quantidade_atual)
            saldo_global += saldo
            outras_unidades.append({
                'unidade_id': p.unidade_id,
                'unidade_nome': p.unidade.nome,
                'saldo': saldo,
                'estoque_id': p.id
            })

        # Determina recomendação
        if saldo_local > 0:
            recomendacao = 'consumir'
        elif saldo_global > 0:
            recomendacao = 'transferir'
        else:
            recomendacao = 'comprar'

        return jsonify({
            'success': True,
            'tem_estoque_local': saldo_local > 0,
            'saldo_local': saldo_local,
            'tem_estoque_outras_unidades': len(outras_unidades) > 0,
            'outras_unidades': outras_unidades,
            'saldo_global_total': saldo_global,
            'recomendacao': recomendacao,
            'peca_nome': peca.nome,
            'unidade_atual': peca.unidade.nome if peca.unidade else 'N/A'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'erro': str(e)
        }), 500

@bp.route('/estoque/painel')
@login_required
def painel_estoque():
    from decimal import Decimal
    itens = Estoque.query.order_by(Estoque.nome).all()

    # Reconciliar quantidade_atual com a soma real dos EstoqueSaldo
    # (os dois podem divergir se movimentacoes foram criadas fora do service)
    needs_commit = False
    for item in itens:
        saldo_real = sum((s.quantidade or Decimal(0)) for s in item.saldos)
        if abs(float(saldo_real) - float(item.quantidade_atual or 0)) > 0.001:
            item.quantidade_atual = saldo_real
            needs_commit = True
    if needs_commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    unidades = Unidade.query.order_by(Unidade.nome).all()
    return render_template('estoque.html', estoque=itens, unidades=unidades)

@bp.route('/api/estoque/solicitar-compra', methods=['POST'])
@login_required
def solicitar_compra():
    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        quantidade = data.get('quantidade')
        
        if not estoque_id or not quantidade or float(quantidade) <= 0:
            return jsonify({'success': False, 'erro': 'Quantidade deve ser maior que zero.'}), 400

        item = Estoque.query.get(estoque_id)
        if not item:
            return jsonify({'success': False, 'erro': 'Item não encontrado.'}), 404

        from app.models.estoque_models import CatalogoFornecedor, Fornecedor
        
        # 1. Tenta buscar no catálogo vinculado
        vinculo = CatalogoFornecedor.query.filter_by(estoque_id=estoque_id).first()
        if vinculo:
            fornecedor_id = vinculo.fornecedor_id
        else:
            # 2. Tenta buscar qualquer fornecedor disponível
            primeiro_forn = Fornecedor.query.first()
            if primeiro_forn:
                fornecedor_id = primeiro_forn.id
            else:
                return jsonify({'success': False, 'erro': 'Nenhum fornecedor cadastrado no sistema.'}), 400

        # US-006: Aprovação Automática no Painel de Compras
        valor_unitario = float(item.valor_unitario or 0)
        valor_total = valor_unitario * float(quantidade)
        
        status_inicial = 'pendente'
        if valor_total <= 500:
            status_inicial = 'aprovado'

        # Unidade de destino (enviada pelo frontend ou do item de estoque)
        unidade_destino_id = data.get('unidade_destino_id') or (item.unidade_id if item.unidade_id else None)

        pedido = PedidoCompra(
            estoque_id=estoque_id,
            fornecedor_id=fornecedor_id,
            quantidade=int(quantidade),
            status=status_inicial,
            data_solicitacao=datetime.now(),
            solicitante_id=current_user.id,
            unidade_destino_id=unidade_destino_id
        )

        db.session.add(pedido)
        db.session.commit()
        return jsonify({
            'success': True, 
            'mensagem': f'Pedido #{pedido.id} criado'
        })
    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 400

# [MODIFICADO] Solicitar Transferência entre Unidades (com notificação)
@bp.route('/api/estoque/transferir', methods=['POST'])
@login_required
def solicitar_transferencia():
    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        qtd = data.get('quantidade')
        unidade_origem_id = data.get('unidade_origem_id')
        unidade_destino_id = data.get('unidade_destino_id')
        
        # Novos campos para notificação
        notificar_responsavel_id = data.get('notificar_responsavel_id')
        enviar_whats = data.get('enviar_whats')
        
        if not all([estoque_id, qtd, unidade_origem_id, unidade_destino_id]):
             return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400
        
        # Define se aprova automaticamente baseado no cargo
        aprovacao_automatica = current_user.tipo in ['admin', 'gerente']

        solicitacao = EstoqueService.transferir_entre_unidades(
            estoque_id=estoque_id,
            unidade_origem_id=unidade_origem_id,
            unidade_destino_id=unidade_destino_id,
            quantidade=qtd,
            solicitante_id=current_user.id,
            observacao=data.get('observacao'),
            aprovacao_automatica=aprovacao_automatica
        )
        
        # [Novo] Enviar notificação WhatsApp se solicitado
        if enviar_whats and notificar_responsavel_id:
            responsavel = Usuario.query.get(notificar_responsavel_id)
            if responsavel and responsavel.telefone:
                # Busca objetos para montar mensagem
                item = Estoque.query.get(estoque_id)
                origem = Unidade.query.get(unidade_origem_id)
                destino = Unidade.query.get(unidade_destino_id)
                
                msg = (f"📦 *Solicitação de Transferência*\n\n"
                       f"Item: {item.nome}\n"
                       f"Qtd: {qtd} {item.unidade_medida}\n"
                       f"De: {origem.nome}\n"
                       f"Para: {destino.nome}\n\n"
                       f"Solicitante: {current_user.nome}\n"
                       f"Status: {solicitacao.status.upper()}")

                WhatsAppService.enviar_mensagem(responsavel.telefone, msg)
        
        msg = 'Transferência realizada com sucesso!' if solicitacao.status == 'concluida' else 'Solicitação criada'
        return jsonify({'success': True, 'msg': msg})

    except ValueError as e:
        return jsonify({'success': False, 'erro': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'erro': f"Erro interno: {str(e)}"}), 500

@bp.route('/api/equipamentos/filtro')
@login_required
def filtrar_equipamentos():
    """
    API para filtrar equipamentos por unidade e categoria via AJAX
    """
    unidade_id = request.args.get('unidade_id')
    categoria = request.args.get('categoria')
    
    query = Equipamento.query.filter_by(ativo=True)
    
    if unidade_id:
        query = query.filter_by(unidade_id=unidade_id)
        
    if categoria and categoria != 'todos':
        query = query.filter_by(categoria=categoria)
        
    equipamentos = query.order_by(Equipamento.nome).all()
    
    return jsonify([{
        'id': e.id,
        'nome': e.nome
    } for e in equipamentos])

@bp.route('/<int:id>/adicionar-tarefa-externa', methods=['POST'])
@login_required
def adicionar_tarefa_externa(id):
    os_obj = OrdemServico.query.get_or_404(id)
    
    terceirizado_id = request.form.get('terceirizado_id')
    descricao = request.form.get('descricao')
    prazo_str = request.form.get('prazo')
    valor_str = request.form.get('valor')
    enviar_whats = request.form.get('enviar_whatsapp') == 'on' # Captura o checkbox
    
    if not terceirizado_id or not descricao:
        flash('Preencha os campos obrigatórios.', 'danger')
        return redirect(url_for('os.detalhes', id=id))

    try:
        prazo_dt = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M')
        
        # Gera sufixo baseado na quantidade atual de chamados
        count = len(os_obj.chamados_externos) + 1
        num_chamado = f"EXT-{os_obj.numero_os}-{count}"

        novo_chamado = ChamadoExterno(
            numero_chamado=num_chamado,
            os_id=os_obj.id,
            terceirizado_id=int(terceirizado_id),
            titulo=f"Serviço Adicional OS {os_obj.numero_os}",
            descricao=descricao,
            prioridade=os_obj.prioridade,
            prazo_combinado=prazo_dt,
            criado_por=current_user.id,
            valor_orcado=valor_str if valor_str else None,
            status='aguardando'
        )
        
        db.session.add(novo_chamado)
        db.session.commit() # Commit aqui para ter o ID do chamado
        
        # --- LÓGICA DE ENVIO WHATSAPP ---
        if enviar_whats:
            terceirizado = Terceirizado.query.get(int(terceirizado_id))
            
            # Montagem da mensagem detalhada
            msg = (
                f"🔧 *Solicitação de Serviço - {os_obj.unidade.nome}*\n\n"
                f"Olá {terceirizado.nome}, precisamos de um serviço:\n\n"
                f"📄 *Chamado:* {num_chamado}\n"
                f"🔗 *Ref. OS:* {os_obj.numero_os}\n"
                f"📅 *Prazo:* {prazo_dt.strftime('%d/%m às %H:%M')}\n\n"
                f"📍 *Local:* {os_obj.unidade.nome}\n"
                f"🗺️ *Endereço:* {os_obj.unidade.endereco or 'Endereço não cadastrado'}\n\n"
                f"📝 *Descrição:* {descricao}\n\n"
                f"👤 *Solicitante:* {current_user.nome}\n"
                f"📞 *Contato:* {current_user.telefone or 'Não informado'}\n\n"
                f"Por favor, confirme o recebimento."
            )

            # Cria registro no histórico
            notif = HistoricoNotificacao(
                chamado_id=novo_chamado.id,
                tipo='criacao',
                destinatario=terceirizado.telefone,
                mensagem=msg,
                status_envio='pendente',
                direcao='outbound',
                prioridade=1
            )
            db.session.add(notif)
            db.session.commit()

            # Enviar WhatsApp diretamente
            try:
                from app.services.whatsapp_service import WhatsAppService

                ok, resp = WhatsAppService.enviar_mensagem(
                    telefone=terceirizado.telefone,
                    texto=msg,
                    prioridade=1
                )
                if ok:
                    notif.status_envio = 'enviado'
                    notif.enviado_em = datetime.now()
                else:
                    notif.status_envio = 'falhou'
                    logger.warning(f"WhatsApp falhou para {terceirizado.nome}: {resp}")

                # Enviar fotos via URL pública (mais confiável que base64)
                fotos_enviadas = 0
                if os_obj.anexos_list:
                    base_url = request.url_root.rstrip('/')
                    logger.info(f"[Fotos OS] {len(os_obj.anexos_list)} foto(s) para {terceirizado.nome}")
                    for anexo in os_obj.anexos_list:
                        url_foto = f"{base_url}/static/{anexo.caminho_arquivo}"
                        caption = f"Foto OS {os_obj.numero_os} - {anexo.tipo.replace('_', ' ')}"
                        ok_foto, resp_foto = WhatsAppService.enviar_imagem_url(
                            phone=terceirizado.telefone,
                            url_publica=url_foto,
                            caption=caption
                        )
                        if ok_foto:
                            fotos_enviadas += 1
                        else:
                            logger.warning(f"[Fotos OS] Falha {anexo.nome_arquivo}: {resp_foto}")
                else:
                    logger.info(f"[Fotos OS] OS {os_obj.id} sem fotos anexadas.")

                msg_flash = f'Tarefa criada e WhatsApp enviado ao prestador!'
                if fotos_enviadas > 0:
                    msg_flash += f' ({fotos_enviadas} foto(s) enviada(s))'
                elif not ok:
                    msg_flash = 'Tarefa criada, mas falha ao enviar WhatsApp.'
                flash(msg_flash, 'success' if ok else 'warning')
                db.session.commit()

                # Enviar email se prestador tiver email
                if terceirizado.email:
                    try:
                        EmailService.enviar_solicitacao_terceirizado(
                            novo_chamado, terceirizado, msg, cc=current_user.email
                        )
                    except Exception as email_err:
                        logger.error(f"Erro ao enviar email para {terceirizado.email}: {email_err}")

            except Exception as e:
                flash('Tarefa criada, mas erro ao enviar notificações.', 'warning')
                logger.error(f"Erro ao enviar notificações: {e}", exc_info=True)
        else:
            flash('Tarefa externa criada com sucesso (sem notificação).', 'success')
        
    except ValueError:
        flash('Formato de data inválido.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar tarefa: {str(e)}', 'danger')

    return redirect(url_for('os.detalhes', id=id))
    
@bp.route('/api/estoque/historico')
@login_required
def historico_estoque():
    """Retorna as últimas 30 movimentações de estoque."""
    movs = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).limit(30).all()
    
    return jsonify([{
        'data': m.data_movimentacao.strftime('%d/%m/%Y %H:%M'),
        'item': m.estoque.nome,
        'tipo': m.tipo_movimentacao.capitalize(),
        'qtd': float(m.quantidade),
        'unidade': m.unidade.nome if m.unidade else 'N/A',
        'usuario': m.usuario.nome if m.usuario else 'Sistema',
        'motivo': m.observacao or '-'
    } for m in movs])

@bp.route('/<int:id>/editar-os', methods=['POST'])
@login_required
def editar_os(id):
    os_obj = OrdemServico.query.get_or_404(id)
    
    if os_obj.status == 'concluida':
        flash('Não é possível editar uma OS concluída.', 'warning')
        return redirect(url_for('os.detalhes', id=id))
        
    try:
        prazo_str = request.form.get('prazo_conclusao')
        prioridade = request.form.get('prioridade')
        descricao = request.form.get('descricao_problema')
        
        if prazo_str:
            os_obj.prazo_conclusao = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M')
            
        if prioridade:
            os_obj.prioridade = prioridade
            
        if descricao:
            os_obj.descricao_problema = descricao
            
        db.session.commit()
        flash('Ordem de Serviço atualizada.', 'success')
        
    except ValueError:
        flash('Formato de data inválido.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar OS: {str(e)}', 'danger')
        
    return redirect(url_for('os.detalhes', id=id))

@bp.route('/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar_os_route(id):
    try:
        EstoqueService.cancelar_os(id, current_user.id)
        flash('Ordem de Serviço cancelada e estoque estornado.', 'success')
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar OS: {str(e)}', 'danger')
        
    return redirect(url_for('os.detalhes', id=id))


@bp.route('/<int:id>/feedback', methods=['POST'])
@login_required
def salvar_feedback(id):
    os_obj = OrdemServico.query.get_or_404(id)
    rating = request.json.get('rating')
    comentario = request.json.get('comentario')
    
    if not rating:
        return jsonify({'success': False, 'msg': 'Rating obrigat�rio'}), 400
        
    os_obj.feedback_rating = int(rating)
    if comentario:
        os_obj.feedback_comentario = comentario
        
    db.session.commit()
    return jsonify({'success': True, 'msg': 'Avalia��o salva com sucesso'})

# [NOVO] Buscar Prestadores por Palavra-Chave (Especialidade)
@bp.route('/buscar_prestadores', methods=['POST'])
@login_required
def buscar_prestadores():
    """Busca prestadores por palavra-chave na especialidade, nome ou empresa"""
    try:
        import json
        import logging
        logger = logging.getLogger(__name__)

        # Verificar se há dados JSON
        if not request.is_json:
            return jsonify({'success': False, 'erro': 'Content-Type deve ser application/json'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'erro': 'Dados JSON inválidos'}), 400

        palavra_chave = data.get('palavra_chave', '').strip().lower()
        unidade_id = current_user.unidade_padrao_id

        if not palavra_chave:
            return jsonify({'success': False, 'erro': 'Palavra-chave não informada'}), 400

        logger.info(f"Buscando prestadores com palavra-chave: {palavra_chave}")

        # Buscar prestadores ativos
        prestadores = Terceirizado.query.filter(
            Terceirizado.ativo == True
        ).all()

        resultados = []
        for p in prestadores:
            # Verificar se o prestador atende a unidade (global ou específica)
            if unidade_id:
                atende_unidade = p.abrangencia_global or (unidade_id in [u.id for u in p.unidades])
                if not atende_unidade:
                    continue

            # Buscar palavra-chave nas especialidades, nome e nome da empresa
            try:
                especialidades_list = json.loads(p.especialidades) if p.especialidades else []
            except (json.JSONDecodeError, TypeError):
                # Se não for JSON válido, tentar como string
                especialidades_list = [p.especialidades] if p.especialidades else []

            # Montar string de busca
            texto_busca = ' '.join([
                p.nome.lower() if p.nome else '',
                p.nome_empresa.lower() if p.nome_empresa else '',
                ' '.join(especialidades_list).lower()
            ])

            # Verificar se a palavra-chave está presente
            if palavra_chave in texto_busca:
                resultados.append({
                    'id': p.id,
                    'nome': p.nome,
                    'nome_empresa': p.nome_empresa,
                    'telefone': p.telefone,
                    'email': p.email,
                    'especialidades': especialidades_list,
                    'avaliacao_media': float(p.avaliacao_media or 0),
                    'tem_whatsapp': bool(p.telefone),
                    'tem_email': bool(p.email),
                    'orientacao_contato': p.observacoes if not p.telefone and not p.email else None
                })

        logger.info(f"Encontrados {len(resultados)} prestadores")

        return jsonify({
            'success': True,
            'prestadores': resultados,
            'total': len(resultados)
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao buscar prestadores: {str(e)}")
        return jsonify({'success': False, 'erro': str(e)}), 500

# [NOVO] Criar Chamados para Múltiplos Prestadores
@bp.route('/criar_chamados_multiplos', methods=['POST'])
@login_required
def criar_chamados_multiplos():
    """Cria chamado externo para múltiplos prestadores selecionados"""
    try:
        from datetime import timedelta

        prestador_ids = request.json.get('prestador_ids', [])
        os_id = request.json.get('os_id')
        titulo = request.json.get('titulo')
        descricao = request.json.get('descricao')
        prioridade = request.json.get('prioridade', 'media')
        prazo_dias = int(request.json.get('prazo_dias', 5))  # Default 5 dias

        if not prestador_ids or not titulo or not descricao:
            return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400

        prazo_combinado = datetime.now() + timedelta(days=prazo_dias)
        chamados_criados = []

        for prestador_id in prestador_ids:
            prestador = Terceirizado.query.get(prestador_id)
            if not prestador or not prestador.ativo:
                continue

            # Gerar número do chamado
            ultimo_chamado = ChamadoExterno.query.order_by(ChamadoExterno.id.desc()).first()
            numero = f"CH{(ultimo_chamado.id + 1):05d}" if ultimo_chamado else "CH00001"

            chamado = ChamadoExterno(
                numero_chamado=numero,
                os_id=os_id,
                terceirizado_id=prestador_id,
                titulo=titulo,
                descricao=descricao,
                prioridade=prioridade,
                prazo_combinado=prazo_combinado,
                criado_por=current_user.id,
                solicitante_id=current_user.id,
                status='aguardando'
            )

            db.session.add(chamado)
            db.session.flush()  # Para obter o ID

            # Enviar notificação via WhatsApp se tiver telefone
            if prestador.telefone:
                mensagem = f"""🔧 *NOVA SOLICITAÇÃO DE SERVIÇO*

Chamado: {numero}
Título: {titulo}

Descrição:
{descricao}

⏰ Prazo: {prazo_dias} dias
📅 Data Limite: {prazo_combinado.strftime('%d/%m/%Y')}

Por favor, envie seu orçamento até a data limite."""

                # Criar notificação no histórico
                notif = HistoricoNotificacao(
                    chamado_id=chamado.id,
                    tipo='criacao',
                    destinatario=prestador.telefone,
                    mensagem=mensagem,
                    status_envio='pendente',
                    direcao='outbound'
                )
                db.session.add(notif)
                db.session.flush()

                # Enviar WhatsApp diretamente
                try:
                    from app.services.whatsapp_service import WhatsAppService
                    import os as os_module

                    ok, resp = WhatsAppService.enviar_mensagem(
                        telefone=prestador.telefone,
                        texto=mensagem,
                        prioridade=1
                    )
                    if ok:
                        notif.status_envio = 'enviado'
                        notif.enviado_em = datetime.now()
                    else:
                        notif.status_envio = 'falhou'
                        logger.warning(f"WhatsApp falhou para {prestador.nome}: {resp}")

                    # Enviar fotos via URL pública (mais confiável que base64)
                    os_obj = OrdemServico.query.get(os_id)
                    if os_obj and os_obj.anexos_list:
                        base_url = request.url_root.rstrip('/')
                        logger.info(f"[Fotos OS] {len(os_obj.anexos_list)} foto(s) para {prestador.nome} via {base_url}")
                        for anexo in os_obj.anexos_list:
                            url_foto = f"{base_url}/static/{anexo.caminho_arquivo}"
                            caption = f"Foto OS {os_obj.numero_os} - {anexo.tipo.replace('_', ' ')}"
                            ok_foto, resp_foto = WhatsAppService.enviar_imagem_url(
                                phone=prestador.telefone,
                                url_publica=url_foto,
                                caption=caption
                            )
                            if not ok_foto:
                                logger.warning(f"[Fotos OS] Falha {anexo.nome_arquivo}: {resp_foto}")
                    else:
                        logger.info(f"[Fotos OS] OS {os_id} sem fotos anexadas.")

                except Exception as e:
                    notif.status_envio = 'falhou'
                    logger.error(f"Erro ao enviar WhatsApp para {prestador.nome}: {e}", exc_info=True)

            # Enviar email sempre que o prestador tiver email
            if prestador.email:
                try:
                    EmailService.enviar_solicitacao_terceirizado(
                        chamado, prestador, mensagem, cc=current_user.email
                    )
                    logger.info(f"Email enviado para {prestador.email}")
                except Exception as e:
                    logger.error(f"Erro ao enviar email para {prestador.email}: {e}")

            chamados_criados.append({
                'numero': numero,
                'prestador': prestador.nome,
                'canal': 'WhatsApp' if prestador.telefone else ('Email' if prestador.email else 'Contato Manual')
            })

        db.session.commit()

        return jsonify({
            'success': True,
            'mensagem': f'{len(chamados_criados)} chamados criados com sucesso',
            'chamados': chamados_criados
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'erro': str(e)}), 500


