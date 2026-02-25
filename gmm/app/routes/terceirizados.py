from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models.terceirizados_models import Terceirizado, ChamadoExterno, HistoricoNotificacao
from app.models.estoque_models import OrdemServico
from app.tasks import enviar_whatsapp_task
from app.services.whatsapp_service import WhatsAppService

bp = Blueprint('terceirizados', __name__, url_prefix='/terceirizados')

@bp.route('/chamados', methods=['GET'])
@login_required
def listar_chamados():
    # Filtros opcionais (ex: ?filtro=atrasados)
    filtro = request.args.get('filtro', 'todos')
    
    query = ChamadoExterno.query.outerjoin(OrdemServico).filter(
        (ChamadoExterno.os_id == None) | (OrdemServico.status != 'concluida')
    ).order_by(ChamadoExterno.prazo_combinado.asc())
    
    if filtro == 'atrasados':
        query = query.filter(
            ChamadoExterno.prazo_combinado < datetime.utcnow(),
            ChamadoExterno.status != 'concluido'
        )
    
    chamados = query.all()
    
    # Carrega a lista de prestadores para preencher o <select> do Modal
    lista_terceirizados = Terceirizado.query.filter_by(ativo=True).order_by(Terceirizado.nome).all()
    
    return render_template('chamados.html', 
                         chamados=chamados, 
                         terceirizados=lista_terceirizados,
                         hoje=datetime.utcnow())

@bp.route('/chamados/criar', methods=['POST'])
@login_required
def criar_chamado():
    try:
        # Validação básica
        prazo_str = request.form.get('prazo')
        terceirizado_id = request.form.get('terceirizado_id')
        enviar_whats = request.form.get('enviar_whatsapp') == 'on' # Checkbox do formulário
        
        if not prazo_str or not terceirizado_id:
            raise ValueError("Preencha todos os campos obrigatórios.")

        terceirizado = Terceirizado.query.get(terceirizado_id)
        if not terceirizado:
            raise ValueError("Prestador não encontrado.")

        prazo = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M')
        
        # Gera número do chamado (Ex: CH-2024-17012345)
        num_chamado = f"CH-{datetime.now().year}-{int(datetime.now().timestamp())}"
        
        # Cria o Chamado
        novo_chamado = ChamadoExterno(
            numero_chamado=num_chamado,
            terceirizado_id=terceirizado.id,
            os_id=request.form.get('os_id') or None, # Opcional: vincular a uma OS interna
            titulo=request.form.get('titulo'),
            descricao=request.form.get('descricao'),
            prioridade=request.form.get('prioridade'),
            prazo_combinado=prazo,
            criado_por=current_user.id,
            status='aguardando'
        )
        db.session.add(novo_chamado)
        db.session.commit()
        
        # Lógica de Envio de WhatsApp
        if enviar_whats:
            detalhes_os = ""
            if novo_chamado.os_id:
                os_origem = OrdemServico.query.get(novo_chamado.os_id)
                if os_origem:
                    equipamento = os_origem.equipamento_rel.nome if os_origem.equipamento_rel else 'Geral'
                    detalhes_os = (
                        f"\n📋 *Dados da OS #{os_origem.numero_os}*\n"
                        f"Local: {os_origem.unidade.nome}\n"
                        f"Endereço: {os_origem.unidade.endereco or 'Não informado'}\n"
                        f"Equipamento: {equipamento}\n"
                    )

            msg = (f"🔧 *Solicitação de Serviço GMM*\n\n"
                   f"Chamado: {novo_chamado.numero_chamado}\n"
                   f"Título: {novo_chamado.titulo}\n"
                   f"Prazo: {prazo.strftime('%d/%m %H:%M')}\n"
                   f"{detalhes_os}\n"
                   f"📝 *Descrição:*\n{novo_chamado.descricao}")
            
            # Registra no Histórico
            notif = HistoricoNotificacao(
                chamado_id=novo_chamado.id,
                tipo='criacao',
                destinatario=terceirizado.telefone,
                mensagem=msg,
                status_envio='pendente',
                direcao='outbound'
            )
            db.session.add(notif)
            db.session.commit()

            # Envia via WhatsAppService (com Circuit Breaker e Rate Limiter)
            success, response = WhatsAppService.enviar_mensagem(
                telefone=terceirizado.telefone,
                texto=msg,
                prioridade=1,  # Prioridade normal
                notificacao_id=notif.id
            )

            if success:
                if response.get('status') == 'enfileirado':
                    flash('Chamado criado. Mensagem enfileirada (limite de taxa atingido).', 'info')
                else:
                    flash('Chamado criado e notificação enviada.', 'success')
            else:
                if response.get('code') == 'CIRCUIT_OPEN':
                    flash('Chamado criado. Mensagem será enviada quando API estabilizar.', 'warning')
                else:
                    flash(f'Chamado criado, mas falha no envio: {response.get("error", "Erro desconhecido")}', 'warning')
            
            # [NOVO] Adiciona notificação por email se o terceirizado tiver email cadastrado
            if terceirizado.email:
                try:
                    from app.services.email_service import EmailService
                    EmailService.enviar_solicitacao_terceirizado(
                        novo_chamado, 
                        terceirizado, 
                        msg, 
                        cc=current_user.email
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Erro ao enviar email para terceirizado: {e}")
        else:
            flash('Chamado criado com sucesso.', 'success')
        
    except ValueError as ve:
        db.session.rollback()
        flash(str(ve), 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro interno ao criar chamado: {str(e)}', 'danger')
        
    return redirect(url_for('terceirizados.listar_chamados'))

@bp.route('/chamados/<int:id>', methods=['GET'])
@login_required
def detalhes_chamado(id):
    """Exibe detalhes e timeline de comunicação do chamado"""
    chamado = ChamadoExterno.query.get_or_404(id)
    return render_template('chamado_detalhe.html', chamado=chamado)


@bp.route('/chamados/<int:id>/mensagens', methods=['GET'])
@login_required
def api_mensagens_chamado(id):
    """Retorna todas as mensagens do chamado (por chamado_id + telefone do terceirizado)"""
    from sqlalchemy import or_
    chamado = ChamadoExterno.query.get_or_404(id)
    telefone = chamado.terceirizado.telefone

    try:
        telefone_norm = WhatsAppService.normalizar_telefone(telefone)
    except Exception:
        telefone_norm = telefone
    telefone_sem55 = telefone_norm[2:] if telefone_norm.startswith('55') and len(telefone_norm) > 11 else telefone_norm

    mensagens = HistoricoNotificacao.query.filter(
        or_(
            HistoricoNotificacao.chamado_id == id,
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
        direcao = msg.direcao or ('outbound' if msg.destinatario in (telefone, telefone_norm, telefone_sem55) else 'inbound')
        resultado.append({
            'id': msg.id,
            'direcao': direcao,
            'mensagem': msg.mensagem or '',
            'tipo_conteudo': msg.tipo_conteudo or 'text',
            'status': msg.status_envio,
            'hora': msg.criado_em.strftime('%H:%M') if msg.criado_em else '',
        })
    return jsonify(resultado)

@bp.route('/chamados/<int:id>/cobrar', methods=['POST'])
@login_required
def cobrar_terceirizado(id):
    """
    Botão de Cobrança: Envia mensagem padrão perguntando sobre a conclusão.
    """
    chamado = ChamadoExterno.query.get_or_404(id)
    
    data = request.get_json() or {}
    mensagem_custom = data.get('mensagem_personalizada')
    
    if mensagem_custom:
        msg = mensagem_custom
    else:
        msg = (f"⏰ *Prazo Vencido*\n\n"
               f"Chamado: {chamado.numero_chamado}\n"
               f"Título: {chamado.titulo}\n"
               f"Previsão de conclusão?")
    
    notif = HistoricoNotificacao(
        chamado_id=chamado.id,
        tipo='cobranca',
        destinatario=chamado.terceirizado.telefone,
        mensagem=msg,
        status_envio='pendente',
        direcao='outbound'
    )
    db.session.add(notif)
    db.session.commit()

    try:
        # Envia via WhatsAppService com prioridade alta (cobrança é urgente)
        success, response = WhatsAppService.enviar_mensagem(
            telefone=chamado.terceirizado.telefone,
            texto=msg,
            prioridade=2,  # Prioridade alta - ignora rate limit
            notificacao_id=notif.id
        )

        if success:
            return jsonify({'success': True, 'msg': 'Cobrança enviada com sucesso!'})
        else:
            if response.get('code') == 'CIRCUIT_OPEN':
                return jsonify({'success': False, 'msg': 'Sistema temporariamente indisponível. Tente novamente em alguns minutos.'}), 503
            else:
                return jsonify({'success': False, 'msg': f'Erro ao enviar: {response.get("error", "Erro desconhecido")}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'msg': f'Erro ao enviar: {str(e)}'}), 500

@bp.route('/chamados/<int:id>/responder', methods=['POST'])
@login_required
def responder_manual(id):
    """
    Permite enviar mensagem manual no chat do chamado.
    """
    chamado = ChamadoExterno.query.get_or_404(id)
    mensagem = request.form.get('mensagem')

    if not mensagem:
        return jsonify({'success': False, 'msg': 'Mensagem vazia.'}), 400

    try:
        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='manual_outbound',
            remetente=current_user.nome,
            destinatario=chamado.terceirizado.telefone,
            mensagem=mensagem,
            status_envio='pendente',
            direcao='outbound'
        )
        db.session.add(notif)
        db.session.commit()

        # Envia via WhatsAppService
        success, response = WhatsAppService.enviar_mensagem(
            telefone=chamado.terceirizado.telefone,
            texto=mensagem,
            prioridade=1,  # Prioridade normal
            notificacao_id=notif.id
        )

        if success:
            return jsonify({
                'success': True,
                'msg': 'Mensagem enviada!',
                'data': datetime.utcnow().strftime('%H:%M'),
                'texto': mensagem
            })
        else:
            if response.get('code') == 'CIRCUIT_OPEN':
                return jsonify({
                    'success': False,
                    'msg': 'Sistema temporariamente indisponível. A mensagem será enviada automaticamente quando o sistema estabilizar.'
                }), 503
            elif response.get('status') == 'enfileirado':
                return jsonify({
                    'success': True,
                    'msg': 'Mensagem enfileirada (limite de taxa). Será enviada em breve.',
                    'data': datetime.utcnow().strftime('%H:%M'),
                    'texto': mensagem
                })
            else:
                return jsonify({
                    'success': False,
                    'msg': f'Erro ao enviar: {response.get("error", "Erro desconhecido")}'
                }), 500
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


# ==================== NOVA CENTRAL DE MENSAGENS (ESTILO WHATSAPP) ====================

@bp.route('/central-mensagens')
@login_required
def central_mensagens():
    """Redireciona para o chat unificado"""
    from flask import redirect, url_for
    return redirect(url_for('admin_whatsapp.listar_conversas'))


@bp.route('/api/terceirizados', methods=['GET'])
@login_required
def api_listar_terceirizados():
    """
    Retorna lista de terceirizados ativos para o select do modal.
    Usado pela Central de Mensagens.
    """
    terceirizados = Terceirizado.query.filter_by(ativo=True).order_by(Terceirizado.nome).all()

    return jsonify([{
        'id': t.id,
        'nome': t.nome,
        'empresa': t.nome_empresa,
        'telefone': t.telefone
    } for t in terceirizados])


@bp.route('/api/conversas', methods=['GET'])
@login_required
def api_listar_conversas():
    """
    Retorna lista de chamados com resumo da última mensagem para a sidebar.
    Usado pela Central de Mensagens para exibir conversas ativas.
    """
    # Busca chamados ordenados pela data de criação (mais recentes primeiro)
    chamados = ChamadoExterno.query.order_by(ChamadoExterno.criado_em.desc()).all()

    lista = []
    for c in chamados:
        # Pega a última notificação para mostrar preview
        ultima_msg = HistoricoNotificacao.query.filter_by(chamado_id=c.id)\
            .order_by(HistoricoNotificacao.criado_em.desc()).first()

        # Verifica se há mensagens não lidas (inbound que ainda não foram visualizadas)
        # Simplificação: considera inbound dos últimos 5 minutos como "novo"
        from datetime import timedelta
        tem_nao_lida = False
        if ultima_msg and ultima_msg.direcao == 'inbound':
            cinco_min_atras = datetime.utcnow() - timedelta(minutes=5)
            tem_nao_lida = ultima_msg.criado_em > cinco_min_atras

        lista.append({
            'id': c.id,
            'numero': c.numero_chamado,
            'titulo': c.titulo,
            'prestador': c.terceirizado.nome,
            'telefone': c.terceirizado.telefone,
            'status_chamado': c.status,
            'prioridade': c.prioridade,
            'ultima_msg': ultima_msg.mensagem[:60] + '...' if ultima_msg and len(ultima_msg.mensagem) > 60 else (ultima_msg.mensagem if ultima_msg else 'Sem mensagens'),
            'data_msg': ultima_msg.criado_em.strftime('%H:%M') if ultima_msg else '',
            'data_completa': ultima_msg.criado_em.strftime('%d/%m/%Y %H:%M') if ultima_msg else '',
            'tem_msg_nao_lida': tem_nao_lida,
            'direcao_ultima': ultima_msg.direcao if ultima_msg else None
        })

    return jsonify(lista)


@bp.route('/gerenciar', methods=['GET'])
@login_required
def listar_prestadores():
    # Apenas admin/gerente devem acessar
    if current_user.tipo not in ['admin', 'gerente']:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('ponto.index'))

    # Busca todos os terceirizados
    prestadores = Terceirizado.query.order_by(Terceirizado.nome).all()
    
    return render_template('terceirizados/listar_prestadores.html', 
                         prestadores=prestadores)

@bp.route('/api/conversas/<int:id>/mensagens', methods=['GET'])
@login_required
def api_obter_mensagens(id):
    """
    Retorna histórico completo de mensagens de um chamado específico.
    Usado pela Central de Mensagens para carregar o chat.
    """
    # Verifica se o chamado existe
    chamado = ChamadoExterno.query.get_or_404(id)

    mensagens = HistoricoNotificacao.query.filter_by(chamado_id=id)\
        .order_by(HistoricoNotificacao.criado_em.asc()).all()

    resultado = []
    for m in mensagens:
        # Formata a data de forma amigável
        data_hora = m.criado_em.strftime('%d/%m/%Y %H:%M')
        hora_apenas = m.criado_em.strftime('%H:%M')

        # Determina o remetente para mensagens inbound
        remetente_display = None
        if m.direcao == 'inbound':
            remetente_display = chamado.terceirizado.nome
        elif m.remetente:
            remetente_display = m.remetente
        else:
            remetente_display = 'Sistema GMM'

        resultado.append({
            'id': m.id,
            'direcao': m.direcao,  # 'inbound' ou 'outbound'
            'texto': m.mensagem,
            'status': m.status_envio,  # pendente, enviado, entregue, lido, falhou
            'hora': hora_apenas,
            'data': data_hora,
            'remetente': remetente_display,
            'tipo': m.tipo,  # criacao, cobranca, manual_outbound, resposta_inbound
            'tipo_conteudo': m.tipo_conteudo or 'text',  # text, audio, image, document
            'url_midia': m.url_midia_local,
            'caption': m.caption,
            'mensagem_transcrita': m.mensagem_transcrita
        })

    return jsonify(resultado)


@bp.route('/api/chamados/<int:id>/finalizar', methods=['POST'])
@login_required
def api_finalizar_chamado(id):
    """
    Marca um chamado como concluído.
    Usado pela Central de Mensagens.
    """
    try:
        chamado = ChamadoExterno.query.get_or_404(id)

        # Atualiza status
        chamado.status = 'concluido'
        chamado.data_conclusao = datetime.utcnow()
        db.session.commit()

        # Opcional: Envia mensagem de agradecimento
        msg_finalizacao = (
            f"✅ *Chamado Finalizado*\n\n"
            f"Chamado: {chamado.numero_chamado}\n"
            f"Título: {chamado.titulo}\n\n"
            f"Obrigado pelo atendimento! O chamado foi marcado como concluído."
        )

        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='finalizacao',
            destinatario=chamado.terceirizado.telefone,
            mensagem=msg_finalizacao,
            status_envio='pendente',
            direcao='outbound'
        )
        db.session.add(notif)
        db.session.commit()

        # Envia via WhatsAppService
        success, response = WhatsAppService.enviar_mensagem(
            telefone=chamado.terceirizado.telefone,
            texto=msg_finalizacao,
            prioridade=1,
            notificacao_id=notif.id
        )

        if success:
            return jsonify({
                'success': True,
                'msg': 'Chamado finalizado com sucesso!'
            })
        else:
            # Mesmo com erro de envio, o chamado foi finalizado
            return jsonify({
                'success': True,
                'msg': 'Chamado finalizado. Mensagem de agradecimento será enviada automaticamente.'
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'msg': f'Erro ao finalizar chamado: {str(e)}'
        }), 500


@bp.route('/api/chamados/<int:id>/info', methods=['GET'])
@login_required
def api_info_chamado(id):
    """
    Retorna informações detalhadas do chamado para exibição rápida.
    """
    chamado = ChamadoExterno.query.get_or_404(id)

    # Contadores
    total_msgs = HistoricoNotificacao.query.filter_by(chamado_id=id).count()
    msgs_enviadas = HistoricoNotificacao.query.filter_by(
        chamado_id=id, direcao='outbound'
    ).count()
    msgs_recebidas = HistoricoNotificacao.query.filter_by(
        chamado_id=id, direcao='inbound'
    ).count()

    return jsonify({
        'id': chamado.id,
        'numero': chamado.numero_chamado,
        'titulo': chamado.titulo,
        'descricao': chamado.descricao,
        'status': chamado.status,
        'prioridade': chamado.prioridade,
        'prestador': {
            'nome': chamado.terceirizado.nome,
            'telefone': chamado.terceirizado.telefone,
            'empresa': chamado.terceirizado.empresa
        },
        'criado_em': chamado.criado_em.strftime('%d/%m/%Y %H:%M'),
        'prazo': chamado.prazo_combinado.strftime('%d/%m/%Y %H:%M') if chamado.prazo_combinado else None,
        'data_conclusao': chamado.data_conclusao.strftime('%d/%m/%Y %H:%M') if chamado.data_conclusao else None,
        'estatisticas': {
            'total_mensagens': total_msgs,
            'enviadas': msgs_enviadas,
            'recebidas': msgs_recebidas
        }
    })


# ==================== MULTIMÍDIA (ARQUIVOS E ÁUDIO) ====================

@bp.route('/chamados/<int:id>/enviar-arquivo', methods=['POST'])
@login_required
def enviar_arquivo(id):
    """
    Recebe upload de arquivo (imagem, PDF, documento) e envia via WhatsApp.
    """
    import os
    from werkzeug.utils import secure_filename

    chamado = ChamadoExterno.query.get_or_404(id)
    arquivo = request.files.get('arquivo')
    legenda = request.form.get('legenda', '')

    if not arquivo:
        return jsonify({'success': False, 'msg': 'Nenhum arquivo enviado.'}), 400

    # Valida tipo de arquivo
    EXTENSOES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}
    extensao = arquivo.filename.rsplit('.', 1)[1].lower() if '.' in arquivo.filename else ''

    if extensao not in EXTENSOES_PERMITIDAS:
        return jsonify({'success': False, 'msg': f'Tipo de arquivo não permitido: .{extensao}'}), 400

    # Valida tamanho (máximo 16MB - limite WhatsApp)
    arquivo.seek(0, os.SEEK_END)
    tamanho = arquivo.tell()
    arquivo.seek(0)

    if tamanho > 16 * 1024 * 1024:  # 16MB
        return jsonify({'success': False, 'msg': 'Arquivo muito grande. Máximo: 16MB'}), 400

    try:
        # Cria pasta para armazenar mídias se não existir
        from flask import current_app
        pasta_midia = os.path.join(current_app.root_path, 'static', 'uploads', 'chamados')
        os.makedirs(pasta_midia, exist_ok=True)

        # Gera nome único para o arquivo
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        nome_seguro = secure_filename(arquivo.filename)
        nome_arquivo = f"chamado_{chamado.id}_{timestamp}_{nome_seguro}"
        caminho_arquivo = os.path.join(pasta_midia, nome_arquivo)

        # Salva arquivo
        arquivo.save(caminho_arquivo)

        # Determina tipo de mídia
        tipo_midia = 'document'
        if extensao in ['png', 'jpg', 'jpeg', 'gif']:
            tipo_midia = 'image'
        elif extensao == 'pdf':
            tipo_midia = 'document'

        # Cria URL relativa para acesso
        url_relativa = f'uploads/chamados/{nome_arquivo}'

        # Cria registro de notificação
        mensagem_texto = legenda if legenda else f'📎 Arquivo: {arquivo.filename}'

        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='manual_outbound',
            remetente=current_user.nome,
            destinatario=chamado.terceirizado.telefone,
            mensagem=mensagem_texto,
            status_envio='pendente',
            direcao='outbound',
            tipo_conteudo=tipo_midia,
            url_midia_local=url_relativa,
            caption=legenda
        )
        db.session.add(notif)
        db.session.commit()

        # Envia via WhatsAppService
        success, response = WhatsAppService.enviar_mensagem(
            telefone=chamado.terceirizado.telefone,
            texto=mensagem_texto,
            prioridade=1,
            notificacao_id=notif.id,
            arquivo_path=caminho_arquivo,
            tipo_midia=tipo_midia,
            caption=legenda
        )

        if success:
            return jsonify({
                'success': True,
                'msg': 'Arquivo enviado com sucesso!',
                'data': datetime.utcnow().strftime('%H:%M'),
                'arquivo': nome_arquivo,
                'tipo': tipo_midia
            })
        else:
            # Arquivo foi salvo mas WhatsApp falhou
            if response.get('code') == 'CIRCUIT_OPEN':
                return jsonify({
                    'success': True,
                    'msg': 'Arquivo salvo. Será enviado quando o sistema estabilizar.',
                    'data': datetime.utcnow().strftime('%H:%M')
                })
            else:
                return jsonify({
                    'success': True,
                    'msg': 'Arquivo salvo. Erro ao enviar via WhatsApp (será reenviado).',
                    'data': datetime.utcnow().strftime('%H:%M')
                })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Erro ao processar arquivo: {str(e)}'}), 500


@bp.route('/chamados/<int:id>/enviar-audio', methods=['POST'])
@login_required
def enviar_audio(id):
    """
    Recebe gravação de áudio do navegador e envia via WhatsApp.
    Converte de WebM para formato compatível com WhatsApp (OGG).
    """
    import os
    from werkzeug.utils import secure_filename

    chamado = ChamadoExterno.query.get_or_404(id)
    audio = request.files.get('audio')

    if not audio:
        return jsonify({'success': False, 'msg': 'Nenhum áudio enviado.'}), 400

    try:
        # Cria pasta para armazenar áudios
        from flask import current_app
        pasta_audio = os.path.join(current_app.root_path, 'static', 'uploads', 'audios')
        os.makedirs(pasta_audio, exist_ok=True)

        # Gera nome único
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        nome_arquivo_webm = f"audio_{chamado.id}_{timestamp}.webm"
        caminho_webm = os.path.join(pasta_audio, nome_arquivo_webm)

        # Salva arquivo WebM original
        audio.save(caminho_webm)

        # Tenta converter para OGG (formato WhatsApp)
        # Nota: Requer ffmpeg instalado no servidor
        nome_arquivo_ogg = f"audio_{chamado.id}_{timestamp}.ogg"
        caminho_ogg = os.path.join(pasta_audio, nome_arquivo_ogg)

        # Conversão usando ffmpeg (se disponível)
        import subprocess
        try:
            subprocess.run([
                'ffmpeg', '-i', caminho_webm,
                '-c:a', 'libopus',
                '-b:a', '64k',
                caminho_ogg
            ], check=True, capture_output=True)

            # Se conversão OK, usa OGG
            caminho_final = caminho_ogg
            nome_final = nome_arquivo_ogg

            # Remove WebM
            os.remove(caminho_webm)

        except (subprocess.CalledProcessError, FileNotFoundError):
            # ffmpeg não disponível ou erro na conversão
            # Usa WebM mesmo (alguns clientes WhatsApp suportam)
            caminho_final = caminho_webm
            nome_final = nome_arquivo_webm

        # URL relativa
        url_relativa = f'uploads/audios/{nome_final}'

        # Cria registro
        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='manual_outbound',
            remetente=current_user.nome,
            destinatario=chamado.terceirizado.telefone,
            mensagem='🎤 Áudio gravado',
            status_envio='pendente',
            direcao='outbound',
            tipo_conteudo='audio',
            url_midia_local=url_relativa
        )
        db.session.add(notif)
        db.session.commit()

        # Envia via WhatsAppService
        success, response = WhatsAppService.enviar_mensagem(
            telefone=chamado.terceirizado.telefone,
            texto='🎤 Áudio',
            prioridade=1,
            notificacao_id=notif.id,
            arquivo_path=caminho_final,
            tipo_midia='audio'
        )

        if success:
            return jsonify({
                'success': True,
                'msg': 'Áudio enviado com sucesso!',
                'data': datetime.utcnow().strftime('%H:%M'),
                'arquivo': nome_final
            })
        else:
            return jsonify({
                'success': True,
                'msg': 'Áudio salvo. Será enviado em breve.',
                'data': datetime.utcnow().strftime('%H:%M')
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Erro ao processar áudio: {str(e)}'}), 500