import csv
import io
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, jsonify, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.models.models import Unidade, Usuario
from app.models.estoque_models import Equipamento, Fornecedor, CatalogoFornecedor, Estoque, OrdemServico, PedidoCompra, EstoqueSaldo, MovimentacaoEstoque, SolicitacaoTransferencia
from datetime import datetime
from app.models.terceirizados_models import Terceirizado
from app.services.estoque_service import EstoqueService
from app.extensions import db
from sqlalchemy import func

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.before_request
def restrict_to_admin():
    """
    Middleware de segurança.
    Bloqueia acesso a não-admins, EXCETO para a API de busca de fornecedores
    que é usada pelos técnicos na tela de OS.
    """
    # Exceções (Rotas permitidas para não-admins)
    # 1. API usada por técnicos na OS
    if request.endpoint == 'admin.buscar_fornecedores_peca':
        return
        
    # 2. Compradores podem acessar painel de compras e APIs
    if current_user.is_authenticated and current_user.tipo == 'comprador':
        if request.endpoint in ['admin.compras_painel', 'admin.aprovar_pedido', 'admin.rejeitar_pedido', 'admin.receber_pedido''admin.transferencias_painel','admin.aprovar_transferencia','admin.rejeitar_transferencia']:
            return

    # 3. Gerentes podem acessar painel de transferências e relatórios
    if current_user.is_authenticated and current_user.tipo == 'gerente':
        allowed_endpoints = [
            'admin.transferencias_painel', 
            'admin.aprovar_transferencia', 
            'admin.rejeitar_transferencia',
            'admin.relatorio_movimentacoes',
            'admin.exportar_movimentacoes_csv'


        ]
        if request.endpoint in allowed_endpoints:
            return

    if not current_user.is_authenticated or current_user.tipo not in ['admin']:
        abort(403)

@bp.route('/configuracoes', methods=['GET'])
@login_required
def dashboard():
    # Captura a aba ativa para manter a navegação fluida
    active_tab = request.args.get('tab', 'tecnicos')
    
    # Carregamento de dados para todas as abas
    unidades = Unidade.query.all()
    # Carrega TODOS os usuários ordenados por nome
    funcionarios = Usuario.query.order_by(Usuario.nome).all()
    equipamentos = Equipamento.query.all()
    fornecedores = Fornecedor.query.all()
    estoque_itens = Estoque.query.all()
    # [Novo] Carrega prestadores de serviço
    terceirizados = Terceirizado.query.order_by(Terceirizado.nome).all()

    os_concluidas = OrdemServico.query.filter(
        OrdemServico.status == 'concluida',
        OrdemServico.tipo_manutencao == 'corretiva',
        OrdemServico.data_conclusao != None
    ).all()
    
    total_horas = 0
    qtd_os = len(os_concluidas)
    
    for os_obj in os_concluidas:
        diff = os_obj.data_conclusao - os_obj.data_abertura
        total_horas += diff.total_seconds() / 3600
        
    mttr = round(total_horas / qtd_os, 1) if qtd_os > 0 else 0
    
    return render_template('admin_config.html', 
                         unidades=unidades, 
                         funcionarios=funcionarios, 
                         equipamentos=equipamentos,
                         fornecedores=fornecedores,
                         estoque_itens=estoque_itens,
                         terceirizados=terceirizados,
                         kpi_mttr=mttr,
                         kpi_os_concluidas=qtd_os,
                         active_tab=active_tab)

# ==============================================================================
# GESTÃO DE USUÁRIOS (FUNCIONÁRIOS)
# ==============================================================================

@bp.route('/usuario/novo', methods=['POST'])
@login_required
def novo_usuario():
    username = request.form.get('username')
    email = request.form.get('email')
    
    # Validação de duplicidade (Username ou Email)
    if Usuario.query.filter((Usuario.username == username) | (Usuario.email == email)).first():
        flash('Erro: Nome de usuário ou Email já estão em uso.', 'danger')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))
        
    novo_user = Usuario(
        nome=request.form.get('nome'), 
        username=username,
        email=email,
        telefone=request.form.get('telefone'),
        # Gera o hash seguro da senha
        senha_hash=generate_password_hash(request.form.get('senha')),
        tipo=request.form.get('tipo'), # tecnico, prestador, gerente, admin
        unidade_padrao_id=request.form.get('unidade_id') or None
    )
    
    db.session.add(novo_user)
    db.session.commit()
    flash('Funcionário cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='tecnicos'))

@bp.route('/usuario/editar', methods=['POST'])
@login_required
def editar_tecnico(): # Mantive o nome da função para compatibilidade, mas serve para todos
    user_id = request.form.get('user_id')
    user = Usuario.query.get(user_id)
    
    if user:
        user.nome = request.form.get('nome')
        user.email = request.form.get('email')
        user.unidade_padrao_id = request.form.get('unidade_id') or None
        
        # Só altera a senha se o campo foi preenchido
        nova_senha = request.form.get('senha')
        if nova_senha:
            user.set_senha(nova_senha)
            
        db.session.commit()
        flash('Dados do usuário atualizados.', 'success')
    return redirect(url_for('admin.dashboard', tab='tecnicos'))

@bp.route('/usuario/excluir/<int:id>')
@login_required
def excluir_tecnico(id):
    from app.models.estoque_models import OrdemServico

    # Parâmetro para forçar exclusão (com confirmação)
    force = request.args.get('force', 'false') == 'true'

    user = Usuario.query.get(id)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))

    # Impede que o admin exclua a si mesmo acidentalmente
    if user.id == current_user.id:
        flash('Você não pode excluir seu próprio usuário.', 'danger')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))

    # Busca TODOS os relacionamentos associados
    ordens = OrdemServico.query.filter_by(tecnico_id=user.id).all()
    registros = RegistroPonto.query.filter_by(usuario_id=user.id).all()

    # Verifica se há dados associados
    if (ordens or registros) and not force:
        # Monta mensagem detalhada com lista de dados
        ordens_abertas = [o for o in ordens if o.status in ['aberta', 'em_andamento']]
        ordens_fechadas = [o for o in ordens if o.status not in ['aberta', 'em_andamento']]

        msg_parts = [f'<strong>Usuário: {user.nome}</strong><br>']

        if ordens:
            msg_parts.append(f'<strong>Total de OS associadas: {len(ordens)}</strong><br>')
        if registros:
            msg_parts.append(f'<strong>Total de Registros de Ponto: {len(registros)}</strong><br>')
        msg_parts.append('<br>')

        if ordens_abertas:
            msg_parts.append(f'<strong class="text-danger">⚠️ {len(ordens_abertas)} OS Aberta(s):</strong><ul class="mb-2">')
            for o in ordens_abertas[:5]:
                msg_parts.append(f'<li>OS #{o.numero_os} - {o.status.upper()} - {o.descricao_problema[:50]}...</li>')
            if len(ordens_abertas) > 5:
                msg_parts.append(f'<li>... e mais {len(ordens_abertas) - 5} OS abertas</li>')
            msg_parts.append('</ul>')
            msg_parts.append('<p class="text-danger mb-3">❌ Não é possível excluir enquanto houver OS abertas. Finalize-as primeiro.</p>')

            flash(''.join(msg_parts), 'danger')
            return redirect(url_for('admin.dashboard', tab='tecnicos'))

        # Se chegou aqui, só tem dados fechados (OS fechadas e/ou registros de ponto)
        total_dados = len(ordens_fechadas) + len(registros)

        if ordens_fechadas:
            msg_parts.append(f'<strong class="text-warning">📋 {len(ordens_fechadas)} OS Fechada(s):</strong><ul class="mb-2">')
            for o in ordens_fechadas[:3]:
                msg_parts.append(f'<li>OS #{o.numero_os} - {o.status.upper()} - {o.descricao_problema[:50]}...</li>')
            if len(ordens_fechadas) > 3:
                msg_parts.append(f'<li>... e mais {len(ordens_fechadas) - 3} OS fechadas</li>')
            msg_parts.append('</ul>')

        if registros:
            msg_parts.append(f'<strong class="text-info">🕐 {len(registros)} Registro(s) de Ponto:</strong><ul class="mb-2">')
            for r in registros[:3]:
                data_str = r.data_hora_entrada.strftime('%d/%m/%Y %H:%M')
                msg_parts.append(f'<li>{data_str} - {r.unidade.nome if r.unidade else "N/A"}</li>')
            if len(registros) > 3:
                msg_parts.append(f'<li>... e mais {len(registros) - 3} registros</li>')
            msg_parts.append('</ul>')

        msg_parts.append(f'<p class="mb-2"><strong>⚠️ ATENÇÃO:</strong> Ao excluir este usuário, TODOS os {total_dados} registro(s) associados serão excluídos permanentemente!</p>')
        msg_parts.append(f'<a href="{url_for("admin.excluir_tecnico", id=user.id, force="true")}" class="btn btn-danger btn-sm" onclick="return confirm(\'CONFIRMAÇÃO FINAL:\\n\\nVocê tem certeza que deseja EXCLUIR PERMANENTEMENTE:\\n- Usuário: {user.nome}\\n- {len(ordens_fechadas)} OS\\n- {len(registros)} Registros de Ponto\\n\\nEsta ação NÃO PODE ser desfeita!\')"><i class="bi bi-trash-fill me-1"></i>Confirmar Exclusão Permanente</a> ')
        msg_parts.append(f'<a href="{url_for("admin.toggle_usuario_status", id=user.id)}" class="btn btn-warning btn-sm"><i class="bi bi-pause-circle me-1"></i>Desativar ao Invés (Recomendado)</a>')

        flash(''.join(msg_parts), 'warning')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))

    # Se chegou aqui com force=true ou sem dados, pode excluir
    if force:
        # Exclui todos os dados associados primeiro
        for o in ordens:
            db.session.delete(o)
        for r in registros:
            db.session.delete(r)

    db.session.delete(user)
    db.session.commit()

    msg_sucesso = f'Usuário {user.nome} removido com sucesso'
    if force and (ordens or registros):
        msg_sucesso += f' junto com {len(ordens)} OS e {len(registros)} registros de ponto.'
    else:
        msg_sucesso += '.'

    flash(msg_sucesso, 'success')
    return redirect(url_for('admin.dashboard', tab='tecnicos'))

@bp.route('/usuario/toggle-status/<int:id>')
@login_required
def toggle_usuario_status(id):
    """Ativa ou desativa um usuário"""
    user = Usuario.query.get(id)

    if user.id == current_user.id:
        flash('Você não pode desativar seu próprio usuário.', 'danger')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))

    if user:
        user.ativo = not user.ativo
        db.session.commit()
        status = 'ativado' if user.ativo else 'desativado'
        flash(f'Usuário {status} com sucesso.', 'success')

    return redirect(url_for('admin.dashboard', tab='tecnicos'))

# ==============================================================================
# GESTÃO DE EQUIPAMENTOS
# ==============================================================================

@bp.route('/equipamento/novo', methods=['POST'])
@login_required
def novo_equipamento():
    novo_eq = Equipamento(
        nome=request.form.get('nome'),
        categoria=request.form.get('categoria'),
        unidade_id=request.form.get('unidade_id')
    )
    db.session.add(novo_eq)
    db.session.commit()
    flash('Equipamento cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='equipamentos'))

# ==============================================================================
# GESTÃO DE UNIDADES
# ==============================================================================

@bp.route('/unidade/nova', methods=['POST'])
@login_required
def nova_unidade():
    nova_un = Unidade(
        nome=request.form.get('nome'),
        endereco=request.form.get('endereco'),
        faixa_ip_permitida=request.form.get('faixa_ip'),
        razao_social=request.form.get('razao_social'),
        cnpj=request.form.get('cnpj'),
        telefone=request.form.get('telefone')
    )
    db.session.add(nova_un)
    db.session.commit()
    flash('Unidade criada com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='unidades'))

# ==============================================================================
# GESTÃO DE FORNECEDORES E ESTOQUE
# ==============================================================================

@bp.route('/fornecedor/novo', methods=['POST'])
@login_required
def novo_fornecedor():
    # Tratamento seguro para float
    try:
        prazo = float(request.form.get('prazo_inicial', 7))
    except ValueError:
        prazo = 7.0

    novo_forn = Fornecedor(
        nome=request.form.get('nome'),
        email=request.form.get('email'),
        telefone=request.form.get('telefone'),
        endereco=request.form.get('endereco'),
        prazo_medio_entrega_dias=prazo
    )
    db.session.add(novo_forn)
    db.session.commit()
    flash('Fornecedor cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='fornecedores'))

@bp.route('/estoque/novo', methods=['POST'])
@login_required
def novo_item_estoque():
    """Cadastra uma nova peça no sistema."""
    codigo = request.form.get('codigo')
    
    if Estoque.query.filter_by(codigo=codigo).first():
        flash(f'Erro: O código {codigo} já existe.', 'danger')
        return redirect(url_for('admin.dashboard', tab='fornecedores'))

    nova_peca = Estoque(
        codigo=codigo,
        nome=request.form.get('nome'),
        unidade_medida=request.form.get('unidade_medida'),
        quantidade_atual=0, 
        quantidade_minima=5
    )
    
    db.session.add(nova_peca)
    db.session.commit()
    flash('Nova peça cadastrada no sistema!', 'success')
    return redirect(url_for('admin.dashboard', tab='fornecedores'))

@bp.route('/fornecedor/vincular-peca', methods=['POST'])
@login_required
def vincular_peca_fornecedor():
    """Vincula Peça ao Fornecedor com Preço e Prazo."""
    fornecedor_id = request.form.get('fornecedor_id')
    estoque_id = request.form.get('estoque_id')
    
    # TRATAMENTO DE ERROS: Evita crash se campos vierem vazios
    try:
        preco_str = request.form.get('preco', '')
        # Substitui vírgula por ponto e converte. Se vazio, vira 0.0
        preco = float(preco_str.replace(',', '.')) if preco_str else 0.0
    except ValueError:
        preco = 0.0

    try:
        prazo_str = request.form.get('prazo', '')
        prazo = int(prazo_str) if prazo_str else 0
    except ValueError:
        prazo = 0

    # Verifica se já existe o vínculo para atualizar
    existe = CatalogoFornecedor.query.filter_by(fornecedor_id=fornecedor_id, estoque_id=estoque_id).first()
    
    if existe:
        preco_antigo = existe.preco_atual if existe.preco_atual else 0.0
        
        existe.preco_atual = preco
        existe.prazo_estimado_dias = prazo
        
        msg = f'Vínculo atualizado: Preço de R$ {preco_antigo:.2f} para R$ {preco:.2f}'
    else:
        vinculo = CatalogoFornecedor(
            fornecedor_id=fornecedor_id,
            estoque_id=estoque_id,
            preco_atual=preco,
            prazo_estimado_dias=prazo
        )
        db.session.add(vinculo)
        msg = 'Peça vinculada ao fornecedor!'
        
    db.session.commit()
    flash(msg, 'success')
    return redirect(url_for('admin.dashboard', tab='fornecedores'))

# ==============================================================================
# GESTÃO DE PRESTADORES (TERCEIRIZADOS)
# ==============================================================================

@bp.route('/terceirizado/novo', methods=['POST'])
@login_required
def novo_terceirizado():
    # Captura a lista de IDs selecionados
    unidades_ids = request.form.getlist('unidades') 
    
    novo_terc = Terceirizado(
        nome=request.form.get('nome'),
        nome_empresa=request.form.get('nome_empresa'),
        cnpj=request.form.get('cnpj'),
        telefone=request.form.get('telefone'),
        email=request.form.get('email'),
        especialidades=request.form.get('especialidades'),
        ativo=True
    )

    # Lógica de Abrangência
    if 'global' in unidades_ids or not unidades_ids:
        # Se selecionou "Global" ou não selecionou nada (assume global por padrão ou erro, dependendo da regra)
        novo_terc.abrangencia_global = True
    else:
        novo_terc.abrangencia_global = False
        # Adiciona as unidades selecionadas
        for uid in unidades_ids:
            unidade = Unidade.query.get(int(uid))
            if unidade:
                novo_terc.unidades.append(unidade)
    
    db.session.add(novo_terc)
    db.session.commit()
    flash('Prestador de Serviço cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='terceirizados'))
    
@bp.route('/terceirizado/excluir/<int:id>')
@login_required
def excluir_terceirizado(id):
    prestador = Terceirizado.query.get_or_404(id)
    # Exclusão lógica ou física? Como usuário pediu "Remover", vou deletar.
    # Mas se tiver vínculos, pode dar erro de FK. Melhor desativar ou try/catch
    try:
        db.session.delete(prestador)
        db.session.commit()
        flash('Prestador removido.', 'success')
    except:
        db.session.rollback()
        prestador.ativo = False
        db.session.commit()
        flash('Prestador desativado (possui histórico).', 'warning')
        
    return redirect(url_for('admin.dashboard', tab='terceirizados'))

# ==============================================================================
# APIs (JSON)
# ==============================================================================

@bp.route('/api/fornecedores/buscar-por-peca/<int:peca_id>')
@login_required
def buscar_fornecedores_peca(peca_id):
    """
    Retorna lista de fornecedores para uma peça específica,
    ordenada pelo menor prazo médio de entrega.
    """
    itens = CatalogoFornecedor.query.filter_by(estoque_id=peca_id).all()
    
    resultado = []
    for item in itens:
        resultado.append({
            'fornecedor_id': item.fornecedor.id,
            'nome': item.fornecedor.nome,
            'prazo_medio_geral': round(item.fornecedor.prazo_medio_entrega_dias, 1),
            'preco': float(item.preco_atual) if item.preco_atual else 0.0,
            'historico_entregas': item.fornecedor.total_pedidos_entregues
        })
    
    resultado.sort(key=lambda x: x['prazo_medio_geral'])
    
    return jsonify(resultado)

@bp.route('/api/fornecedores/<int:id>/pecas')
@login_required
def buscar_pecas_fornecedor(id):
    """
    Retorna lista de peças que um fornecedor específico fornece.
    """
    itens = CatalogoFornecedor.query.filter_by(fornecedor_id=id).all()
    resultado = []
    
    for item in itens:
        resultado.append({
            'codigo': item.peca.codigo,
            'nome': item.peca.nome,
            'preco': float(item.preco_atual) if item.preco_atual else 0.0,
            'prazo': item.prazo_estimado_dias
        })
    
    return jsonify(resultado)
@bp.route('/compras', methods=['GET'])
@login_required
def compras_painel():
    # Carrega pedidos pendentes
    pendentes = PedidoCompra.query.filter_by(status='pendente').order_by(PedidoCompra.data_solicitacao.desc()).all()
    
    # Carrega pedidos aprovados/em andamento
    aprovados = PedidoCompra.query.filter(PedidoCompra.status.in_(['aprovado', 'encomendado'])).all()
    
    # Histórico (concluidos ou cancelados)
    historico = PedidoCompra.query.filter(PedidoCompra.status.in_(['entregue', 'cancelado'])).order_by(PedidoCompra.data_solicitacao.desc()).limit(20).all()
    
    # Dados para modais (fornecedores e unidades)
    fornecedores = Fornecedor.query.all()
    unidades = Unidade.query.all()
    
    return render_template('compras.html', 
                         pendentes=pendentes, 
                         aprovados=aprovados, 
                         historico=historico, 
                         fornecedores=fornecedores,
                         unidades=unidades,
                         today=datetime.utcnow().date())
@bp.route('/api/compras/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar_pedido(id):
    if current_user.tipo not in ['admin', 'comprador']:
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403
        
    pedido = PedidoCompra.query.get_or_404(id)
    
    if pedido.status != 'pendente':
        return jsonify({'success': False, 'erro': 'Apenas pedidos pendentes podem ser aprovados.'}), 400
        
    data = request.get_json()
    fornecedor_id = data.get('fornecedor_id')
    data_chegada_str = data.get('data_chegada')
    
    if not fornecedor_id:
        return jsonify({'success': False, 'erro': 'Fornecedor é obrigatório para aprovação.'}), 400
        
    fornecedor = Fornecedor.query.get(fornecedor_id)
    if not fornecedor:
        return jsonify({'success': False, 'erro': 'Fornecedor não encontrado.'}), 404
    
    pedido.status = 'aprovado'
    pedido.fornecedor_id = fornecedor_id
    pedido.aprovador_id = current_user.id
    
    # Data de Chegada Estimada
    if data_chegada_str:
        try:
            pedido.data_chegada = datetime.strptime(data_chegada_str, '%Y-%m-%d')
            if pedido.data_chegada.date() < datetime.utcnow().date():
                 return jsonify({'success': False, 'erro': 'A data de chegada deve ser futura.'}), 400
        except ValueError:
             return jsonify({'success': False, 'erro': 'Formato de data inválido.'}), 400
        
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/compras/<int:id>/rejeitar', methods=['POST'])
@login_required
def rejeitar_pedido(id):
    if current_user.tipo not in ['admin', 'comprador']:
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    pedido = PedidoCompra.query.get_or_404(id)
    pedido.status = 'cancelado'
    pedido.aprovador_id = current_user.id
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/compras/<int:id>/receber', methods=['POST'])
@login_required
def receber_pedido(id):
    if current_user.tipo not in ['admin', 'comprador']:
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    pedido = PedidoCompra.query.get_or_404(id)
    if pedido.status == 'entregue':
        return jsonify({'success': False, 'erro': 'Este pedido já foi recebido.'}), 400
    
    if pedido.status != 'aprovado':
         return jsonify({'success': False, 'erro': 'Apenas pedidos aprovados podem ser recebidos.'}), 400

    data = request.get_json() or {}
    unidade_id = data.get('unidade_destino_id') or current_user.unidade_padrao_id
    
    if not unidade_id:
        return jsonify({'success': False, 'erro': 'Unidade de destino não informada.'}), 400

    try:
        # 1. Atualiza Status e Datas
        agora = datetime.utcnow()
        # Calcula dias reais entre solicitação e recebimento
        dias_real = (agora - pedido.data_solicitacao).days
        if dias_real < 0: dias_real = 0 # Segurança caso relógio mude
        
        pedido.status = 'entregue'
        pedido.data_chegada = agora # Data Real da Chegada
        pedido.recebedor_id = current_user.id
        
        # 2. Atualiza Saldo Global (Estoque)
        estoque = Estoque.query.get(pedido.estoque_id)
        estoque.quantidade_atual += pedido.quantidade
        
        # 3. Atualiza Saldo por Unidade (EstoqueSaldo)
        saldo_unidade = EstoqueSaldo.query.filter_by(
            estoque_id=pedido.estoque_id, 
            unidade_id=unidade_id
        ).first()
        
        if not saldo_unidade:
            saldo_unidade = EstoqueSaldo(
                estoque_id=pedido.estoque_id,
                unidade_id=unidade_id,
                quantidade=pedido.quantidade
            )
            db.session.add(saldo_unidade)
        else:
            saldo_unidade.quantidade += pedido.quantidade
            
        # 4. Registra Movimentação (entrada)
        mov = MovimentacaoEstoque(
            estoque_id=pedido.estoque_id,
            usuario_id=current_user.id,
            unidade_id=unidade_id,
            tipo_movimentacao='entrada',
            quantidade=pedido.quantidade,
            observacao=f"Recebimento Pedido #{pedido.id}",
            data_movimentacao=agora
        )
        db.session.add(mov)
        
        # 5. Atualiza Métricas do Fornecedor (Média Ponderada)
        forn = pedido.fornecedor
        if forn:
            total_envios = forn.total_pedidos_entregues or 0
            prazo_atual = forn.prazo_medio_entrega_dias or 0
            
            # RN028: Prazo médio é média ponderada
            nova_media = (prazo_atual * total_envios + dias_real) / (total_envios + 1)
            
            forn.prazo_medio_entrega_dias = round(nova_media, 1)
            forn.total_pedidos_entregues += 1
            
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'erro': str(e)}), 500

@bp.route('/transferencias', methods=['GET'])
@login_required
def transferencias_painel():
    if current_user.tipo not in ['admin', 'gerente', 'comprador']:
        abort(403)
        
    pendentes = SolicitacaoTransferencia.query.filter_by(status='pendente').order_by(SolicitacaoTransferencia.data_solicitacao.desc()).all()
    historico = SolicitacaoTransferencia.query.filter(SolicitacaoTransferencia.status != 'pendente').order_by(SolicitacaoTransferencia.data_solicitacao.desc()).limit(20).all()
 
    return render_template('admin/transferencias.html', 
                         pendentes=pendentes, 
                         historico=historico)

@bp.route('/api/transferencias/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar_transferencia(id):
    if current_user.tipo not in ['admin', 'gerente', 'comprador']:
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403
        
    try:
        EstoqueService.aprovar_solicitacao_transferencia(id, current_user.id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'success': False, 'erro': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'erro': f"Erro interno: {str(e)}"}), 500

@bp.route('/relatorios/movimentacoes', methods=['GET'])
@login_required
def relatorio_movimentacoes():
    if current_user.tipo not in ['admin', 'gerente']:
        abort(403)

    # Filtros
    unidade_id = request.args.get('unidade_id', type=int)
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')

    query = MovimentacaoEstoque.query.join(Estoque)

    if unidade_id:
        query = query.filter(MovimentacaoEstoque.unidade_id == unidade_id)
    if data_inicio:
        query = query.filter(MovimentacaoEstoque.data_movimentacao >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        # Adiciona 23:59:59 para pegar o dia inteiro
        fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(MovimentacaoEstoque.data_movimentacao <= fim)
    if tipo:
        query = query.filter(MovimentacaoEstoque.tipo_movimentacao == tipo)

    movimentacoes = query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).all()
    unidades = Unidade.query.filter_by(ativa=True).all()

    return render_template('admin/relatorio_movimentacoes.html', 
                         movimentacoes=movimentacoes, 
                         unidades=unidades,
                         filters=request.args)

@bp.route('/relatorios/movimentacoes/exportar', methods=['GET'])
@login_required
def exportar_movimentacoes_csv():
    if current_user.tipo not in ['admin', 'gerente']:
        abort(403)

    unidade_id = request.args.get('unidade_id', type=int)
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')

    query = MovimentacaoEstoque.query.join(Estoque)

    if unidade_id:
        query = query.filter(MovimentacaoEstoque.unidade_id == unidade_id)
    if data_inicio:
        query = query.filter(MovimentacaoEstoque.data_movimentacao >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(MovimentacaoEstoque.data_movimentacao <= fim)
    if tipo:
        query = query.filter(MovimentacaoEstoque.tipo_movimentacao == tipo)

    movimentacoes = query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Data', 'Item', 'Tipo', 'Preço Unit.', 'Quantidade', 'Unidade', 'Usuário', 'Observação'])
    
    for m in movimentacoes:
        writer.writerow([
            m.data_movimentacao.strftime('%d/%m/%Y %H:%M'),
            m.estoque.nome,
            m.tipo_movimentacao.capitalize(),
            f"{m.estoque.preco_unitario or 0:.2f}",
            f"{m.quantidade:g}",
            m.unidade.nome if m.unidade else '-',
            m.usuario.nome,
            m.observacao or '-'
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=movimentacoes_{datetime.now().strftime('%Y%m%d')}.csv"}
    )