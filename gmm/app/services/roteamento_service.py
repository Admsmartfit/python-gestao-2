import re
from datetime import datetime
from app.models.terceirizados_models import Terceirizado
from app.models.whatsapp_models import EstadoConversa, RegrasAutomacao
from app.services.comando_parser import ComandoParser
from app.services.comando_executores import ComandoExecutores
from app.services.estado_service import EstadoService

class RoteamentoService:
    """
    Decides how to process an incoming message.
    Flow: User Check -> Active State -> Command -> Auto Rule -> Fallback
    """
    
    @staticmethod
    def processar(remetente: str, texto: str) -> dict:
        """
        Main routing logic.
        Returns a dict with 'acao', 'resposta', etc.
        """
        from app.models.whatsapp_models import EstadoConversa
        from app.services.whatsapp_service import WhatsAppService

        # 1. Identify Sender
        terceirizado = Terceirizado.query.filter_by(telefone=remetente).first()
        if not terceirizado:
            # Could implement Stranger flow here
            return {
                'acao': 'ignorar',
                'motivo': 'Remetente não cadastrado'
            }
        
        # 2. Check Active Conversation State
        # Assuming activity window of 24h managed by 'updated_at' check
        # We find latest state
        estado = EstadoConversa.query.filter_by(telefone=remetente).order_by(EstadoConversa.updated_at.desc()).first()
        
        # Determine if state is still valid (e.g., < 24h)
        if estado and (datetime.utcnow() - estado.updated_at).total_seconds() < 86400: # 24h
            # Verificar se usuário está respondendo confirmação de OS via NLP
            import json
            ctx = json.loads(estado.contexto) if isinstance(estado.contexto, str) else estado.contexto
            if ctx.get('fluxo') == 'confirmar_os_nlp':
                resposta = RoteamentoService._processar_confirmacao_os_nlp(terceirizado, texto)
                return {'acao': 'responder', 'resposta': resposta}

            resultado_estado = EstadoService.processar_resposta_com_estado(estado, texto)
            if resultado_estado['sucesso']:
                return {'acao': 'responder', 'resposta': resultado_estado['resposta']}
        
        # 3. Parse Command
        if texto.upper().startswith('EQUIP:'):
            return RoteamentoService._processar_comando_equip(terceirizado, texto)

        # US-012: Gatilhos informais
        texto_up = texto.upper()
        if "ESTOQUE POSITIVO" in texto_up or "ABUNDANTE" in texto_up:
            return RoteamentoService._consultar_estoque(terceirizado)
        
        if "PRECISO DE" in texto_up or "SOLICITAR" in texto_up:
            return RoteamentoService._iniciar_fluxo_solicitacao_peca(terceirizado)

        comando = ComandoParser.parse(texto)
        if comando:
            cmd_key = comando['comando']
            if cmd_key == 'COMPRA':
                res = ComandoExecutores.executar_compra(comando['params'], terceirizado)
            elif cmd_key == 'STATUS':
                res = ComandoExecutores.executar_status(terceirizado)
            elif cmd_key == 'AJUDA':
                res = ComandoExecutores.executar_ajuda()
            else:
                res = {'sucesso': False, 'resposta': 'Comando desconhecido.'}
            
            return {'acao': 'responder', 'resposta': res['resposta']}
        
        # 4. Automation Rules
        regra = RegrasAutomacao.query.filter(
            RegrasAutomacao.ativo == True
        ).order_by(RegrasAutomacao.prioridade.desc()).all()
        
        for r in regra:
            if RoteamentoService._match_regra(r, texto):
                return {
                    'acao': r.acao, # responder, executar_funcao, encaminhar
                    'resposta': r.resposta_texto,
                    'encaminhar_para': r.encaminhar_para_perfil, # if acao=encaminhar
                    'funcao': r.funcao_sistema # if acao=executar_funcao
                }
        
        # 5. NLP Analysis (Advanced Extraction)
        from app.services.nlp_service import NLPService
        entidades = NLPService.extrair_entidades(texto)
        if entidades and entidades.get('equipamento'):
             # Se Extraiu equipamento, sugere abertura de OS ou encaminha com contexto
             res_texto = f"Entendi que há um problema com: *{entidades['equipamento']}*.\n"
             res_texto += f"Local: {entidades['local'] or 'Não especificado'}\n"
             res_texto += f"Urgência: {entidades['urgencia'].upper()}\n\n"
             res_texto += "Deseja que eu abra uma Ordem de Serviço agora? (Responda SIM ou NÃO)"
             
             # Salva contexto para confirmação posterior (conforme Spec 4.2.3)
             from app.models.whatsapp_models import EstadoConversa
             from app.extensions import db
             import json
             
             estado = EstadoConversa(
                 telefone=remetente,
                 contexto=json.dumps({
                     'fluxo': 'confirmar_os_nlp',
                     'dados': entidades
                 }),
                 ultimo_comando='nlp_extraction'
             )
             db.session.add(estado)
             db.session.commit()
             
             return {'acao': 'responder', 'resposta': res_texto}

        # 6. Fallback (Interactive Menu instead of simple forward)
        return RoteamentoService._exibir_menu_inicial(terceirizado)
    
    @staticmethod
    def _match_regra(regra: RegrasAutomacao, texto: str) -> bool:
        """Checks if text matches the rule pattern."""
        if not regra.palavra_chave:
            return False
            
        if regra.tipo_correspondencia == 'exata':
            return texto.strip().upper() == regra.palavra_chave.upper()
        
        elif regra.tipo_correspondencia == 'contem':
            return regra.palavra_chave.upper() in texto.upper()
        
        elif regra.tipo_correspondencia == 'regex':
            try:
                return re.search(regra.palavra_chave, texto, re.IGNORECASE) is not None
            except:
                return False

        return False

    # ==================== MÉTODOS V3.1 - RESPOSTAS INTERATIVAS ====================

    @staticmethod
    def processar_resposta_interativa(notificacao):
        """
        Processa resposta de mensagens interativas (list messages ou buttons).

        Args:
            notificacao: HistoricoNotificacao com tipo_conteudo='interactive'

        Returns:
            dict: Resultado do processamento com 'acao' e 'resposta'
        """
        # Extrai ID da resposta (ex: "minhas_os", "aprovar_123", "solicitar_peca")
        resposta_id = notificacao.mensagem  # Vem do webhook
        telefone = notificacao.remetente

        # Identifica terceirizado
        terceirizado = Terceirizado.query.filter_by(telefone=telefone).first()
        if not terceirizado:
            return {'acao': 'ignorar', 'motivo': 'Remetente não cadastrado'}

        # Roteamento baseado no ID da resposta
        if resposta_id == 'minhas_os':
            return RoteamentoService._listar_minhas_os(terceirizado)

        elif resposta_id == 'abrir_os':
            return RoteamentoService._iniciar_fluxo_abrir_os(terceirizado)

        elif resposta_id == 'solicitar_peca':
            return RoteamentoService._iniciar_fluxo_solicitacao_peca(terceirizado)

        elif resposta_id == 'consultar_estoque':
            return RoteamentoService._consultar_estoque(terceirizado)

        elif resposta_id.startswith('aprovar_'):
            pedido_id = int(resposta_id.split('_')[1])
            return RoteamentoService._aprovar_pedido(pedido_id, terceirizado)

        elif resposta_id.startswith('rejeitar_'):
            pedido_id = int(resposta_id.split('_')[1])
            return RoteamentoService._rejeitar_pedido(pedido_id, terceirizado)

        elif resposta_id.startswith('aceitar_os_'):
            os_id = int(resposta_id.split('_')[2])
            return RoteamentoService._aceitar_os(os_id, terceirizado)

        elif resposta_id.startswith('abrir_os_'):
            equip_id = int(resposta_id.split('_')[2])
            return RoteamentoService._abrir_os_equipamento(terceirizado, equip_id)

        elif resposta_id.startswith('historico_'):
            equip_id = int(resposta_id.split('_')[1])
            return RoteamentoService._exibir_historico_equipamento(terceirizado, equip_id)

        elif resposta_id.startswith('dados_tecnicos_'):
            equip_id = int(resposta_id.split('_')[2])
            return RoteamentoService._exibir_dados_tecnicos(terceirizado, equip_id)

        elif resposta_id == 'voltar_menu':
            from app.extensions import db
            EstadoConversa.query.filter_by(telefone=terceirizado.telefone).delete()
            db.session.commit()
            return {'acao': 'responder', 'resposta': "Contexto limpo. Como posso ajudar?"}

        # Se não reconheceu o ID, retorna menu padrão
        return RoteamentoService._exibir_menu_inicial(terceirizado)

    @staticmethod
    def _exibir_menu_inicial(terceirizado):
        """US-015: Menu interativo principal."""
        from app.services.whatsapp_service import WhatsAppService
        
        sections = [
            {
                "title": "Minhas Atividades",
                "rows": [
                    {"id": "minhas_os", "title": "📋 Ver Minhas OSs", "description": "Listar chamados sob sua responsabilidade"},
                    {"id": "abrir_os", "title": "🆕 Abrir Chamado", "description": "Registrar novo problema"}
                ]
            },
            {
                "title": "Materiais e Peças",
                "rows": [
                    {"id": "consultar_estoque", "title": "📊 Consultar Estoque", "description": "Verificar disponibilidade de itens"},
                    {"id": "solicitar_peca", "title": "📦 Solicitar Peça", "description": "Pedir item para manutenção"}
                ]
            }
        ]

        WhatsAppService.send_list_message(
            phone=terceirizado.telefone,
            header="🤖 ASSISTENTE GMM",
            body=f"Olá {terceirizado.nome}! Como posso ajudar você hoje?",
            button_text="Ver Opções",
            sections=sections
        )
        return {'acao': 'aguardar_interacao'}

    @staticmethod
    def _listar_minhas_os(terceirizado):
        """Lista OSs abertas do técnico."""
        from app.models.estoque_models import OrdemServico

        oss = OrdemServico.query.filter_by(
            tecnico_id=terceirizado.id
        ).filter(
            OrdemServico.status.in_(['aberta', 'em_andamento', 'pausada'])
        ).order_by(OrdemServico.data_abertura.desc()).limit(10).all()

        if not oss:
            mensagem = "Você não tem OSs abertas no momento."
        else:
            mensagem = f"📋 Você tem {len(oss)} OS(s) abertas:\n\n"
            for os in oss:
                status_emoji = {
                    'aberta': '🆕',
                    'em_andamento': '⚙️',
                    'pausada': '⏸️'
                }.get(os.status, '❓')

                mensagem += f"{status_emoji} *#{os.numero_os}*\n"
                mensagem += f"   {os.titulo}\n"
                mensagem += f"   Prioridade: {os.prioridade.upper()}\n"
                mensagem += f"   Status: {os.status.replace('_', ' ').title()}\n\n"

        return {'acao': 'enviar_mensagem', 'telefone': terceirizado.telefone, 'mensagem': mensagem}

    @staticmethod
    def _iniciar_fluxo_abrir_os(terceirizado):
        """Inicia fluxo conversacional para abrir OS."""
        # Criar estado de conversa
        from app.extensions import db

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            contexto='{"fluxo": "abrir_os", "etapa": "aguardando_equipamento"}',
            ultimo_comando='abrir_os'
        )
        db.session.add(estado)
        db.session.commit()

        mensagem = "🛠️ *Abertura de OS*\n\nQual equipamento apresenta o problema?\n\n_Digite o nome ou código do equipamento_"
        return {'acao': 'enviar_mensagem', 'telefone': terceirizado.telefone, 'mensagem': mensagem}

    @staticmethod
    def _iniciar_fluxo_solicitacao_peca(terceirizado):
        """Inicia fluxo para solicitar peça."""
        from app.extensions import db

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            contexto='{"fluxo": "solicitar_peca", "etapa": "aguardando_codigo"}',
            ultimo_comando='solicitar_peca'
        )
        db.session.add(estado)
        db.session.commit()

        mensagem = "📦 *Solicitação de Peça*\n\nInforme o código da peça que precisa.\n\n_Exemplo: ROL001_"
        return {'acao': 'enviar_mensagem', 'telefone': terceirizado.telefone, 'mensagem': mensagem}

    @staticmethod
    def _consultar_estoque(terceirizado):
        """Consulta status de estoque (implementação básica)."""
        mensagem = "📊 *Consulta de Estoque*\n\nPara consultar uma peça específica, envie:\n\n#ESTOQUE <código>\n\n_Exemplo: #ESTOQUE ROL001_"
        return {'acao': 'enviar_mensagem', 'telefone': terceirizado.telefone, 'mensagem': mensagem}

    @staticmethod
    def _aprovar_pedido(pedido_id, aprovador):
        """Aprova pedido de compra e notifica solicitante."""
        from app.models.estoque_models import PedidoCompra
        from app.extensions import db
        from app.services.whatsapp_service import WhatsAppService

        pedido = PedidoCompra.query.get(pedido_id)
        if not pedido:
            mensagem = "❌ Pedido não encontrado."
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

        if pedido.status != 'aguardando_aprovacao':
            mensagem = f"⚠️ Pedido #{pedido_id} já foi processado.\n\nStatus atual: {pedido.status.replace('_', ' ').title()}"
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

        # Check if token is still valid (if using token-based approval)
        if pedido.token_expira_em and pedido.token_expira_em < datetime.utcnow():
            mensagem = f"❌ O prazo para aprovação do pedido #{pedido_id} expirou."
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

        # Update pedido status
        from app.models.models import Usuario
        aprovador_usuario = Usuario.query.filter_by(telefone=aprovador.telefone).first()

        pedido.status = 'aprovado'
        pedido.aprovador_id = aprovador_usuario.id if aprovador_usuario else None
        db.session.commit()

        # Notify requester (if we can find them)
        if pedido.solicitante and pedido.solicitante.telefone:
            notificacao_solicitante = f"""✅ *PEDIDO APROVADO*

Seu pedido #{pedido.id} foi aprovado!

*Item:* {pedido.peca.nome}
*Quantidade:* {pedido.quantidade} {pedido.peca.unidade_medida}
*Aprovado por:* {aprovador.nome if hasattr(aprovador, 'nome') else 'Gestor'}

O item será comprado em breve."""

            WhatsAppService.enviar_mensagem(
                telefone=pedido.solicitante.telefone,
                texto=notificacao_solicitante,
                prioridade=1
            )

        mensagem = f"""✅ *PEDIDO #{pedido.id} APROVADO*

*Item:* {pedido.peca.nome}
*Quantidade:* {pedido.quantidade}
*Solicitante:* {pedido.solicitante.nome if pedido.solicitante else 'N/A'}

O solicitante foi notificado."""

        return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

    @staticmethod
    def _rejeitar_pedido(pedido_id, aprovador):
        """Rejeita pedido de compra e notifica solicitante."""
        from app.models.estoque_models import PedidoCompra
        from app.extensions import db
        from app.services.whatsapp_service import WhatsAppService

        pedido = PedidoCompra.query.get(pedido_id)
        if not pedido:
            mensagem = "❌ Pedido não encontrado."
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

        if pedido.status != 'aguardando_aprovacao':
            mensagem = f"⚠️ Pedido #{pedido_id} já foi processado.\n\nStatus atual: {pedido.status.replace('_', ' ').title()}"
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

        # Update pedido status
        from app.models.models import Usuario
        aprovador_usuario = Usuario.query.filter_by(telefone=aprovador.telefone).first()

        pedido.status = 'rejeitado'
        pedido.aprovador_id = aprovador_usuario.id if aprovador_usuario else None
        db.session.commit()

        # Notify requester
        if pedido.solicitante and pedido.solicitante.telefone:
            notificacao_solicitante = f"""❌ *PEDIDO REJEITADO*

Seu pedido #{pedido.id} foi rejeitado.

*Item:* {pedido.peca.nome}
*Quantidade:* {pedido.quantidade} {pedido.peca.unidade_medida}

Entre em contato com o gestor para mais informações."""

            WhatsAppService.enviar_mensagem(
                telefone=pedido.solicitante.telefone,
                texto=notificacao_solicitante,
                prioridade=1
            )

        mensagem = f"""❌ *PEDIDO #{pedido.id} REJEITADO*

*Item:* {pedido.peca.nome}
*Quantidade:* {pedido.quantidade}
*Solicitante:* {pedido.solicitante.nome if pedido.solicitante else 'N/A'}

O solicitante foi notificado."""

        return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': mensagem}

    @staticmethod
    def _aceitar_os(os_id, terceirizado):
        """Aceita atribuição de OS."""
        from app.models.estoque_models import OrdemServico
        from app.extensions import db

        os = OrdemServico.query.get(os_id)
        if not os:
            mensagem = "❌ OS não encontrada."
        elif os.tecnico_id and os.tecnico_id != terceirizado.id:
            mensagem = "❌ Esta OS já foi atribuída a outro técnico."
        else:
            os.tecnico_id = terceirizado.id
            os.status = 'em_andamento'
            os.data_inicio = datetime.utcnow()
            db.session.commit()

            mensagem = f"✅ *OS #{os.numero_os} aceita!*\n\n"
            mensagem += f"📋 {os.titulo}\n"
            mensagem += f"📍 Unidade: {os.unidade.nome if os.unidade else 'N/A'}\n"
            mensagem += f"⏰ Prioridade: {os.prioridade.upper()}\n\n"
            mensagem += "_Status atualizado para: Em Andamento_"

        return {'acao': 'enviar_mensagem', 'telefone': terceirizado.telefone, 'mensagem': mensagem}

    # ==================== MÉTODOS GAPS - SPRINT 1 ====================

    @staticmethod
    def _processar_confirmacao_os_nlp(terceirizado, texto):
        """Processa confirmação de criação de OS por voz."""
        from app.models.whatsapp_models import EstadoConversa
        from app.models.estoque_models import Equipamento, OrdemServico
        from app.models.models import Unidade
        from app.extensions import db
        import json

        estado = EstadoConversa.query.filter_by(
            telefone=terceirizado.telefone
        ).filter(EstadoConversa.contexto.like('%confirmar_os_nlp%')).order_by(EstadoConversa.updated_at.desc()).first()

        if not estado:
            return "Não há solicitação de OS pendente."

        contexto = json.loads(estado.contexto)
        dados = contexto['dados']

        texto_lower = texto.lower().strip()
        confirmacoes = ['sim', 's', 'yes', 'confirmar', 'ok']
        cancelamentos = ['nao', 'não', 'n', 'no', 'cancelar']

        if texto_lower in cancelamentos:
            db.session.delete(estado)
            db.session.commit()
            return "❌ Solicitação de OS cancelada."

        if texto_lower not in confirmacoes:
            return "Por favor, responda SIM para confirmar ou NÃO para cancelar."

        # Equipamento
        equipamento = Equipamento.query.filter(
            Equipamento.nome.ilike(f"%{dados['equipamento']}%"),
            Equipamento.ativo == True
        ).first()

        # Unidade
        unidade_id = None
        if dados.get('local'):
            unidade = Unidade.query.filter(Unidade.nome.ilike(f"%{dados['local']}%")).first()
            if unidade:
                unidade_id = unidade.id
        
        if not unidade_id:
            # Fallback: usar unidade_padrao do usuario (terceirizado pode ser Usuario)
            from app.models.models import Usuario
            usuario = Usuario.query.filter_by(telefone=terceirizado.telefone).first()
            if usuario:
                unidade_id = usuario.unidade_padrao_id

        # Criar OS
        numero_os = f"OS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        nova_os = OrdemServico(
            numero_os=numero_os,
            equipamento_id=equipamento.id if equipamento else None,
            unidade_id=unidade_id,
            tecnico_id=terceirizado.id, # Assumindo que terceirizado.id é o que vai em tecnico_id
            tipo_manutencao='corretiva', # Default para voz
            titulo=f"Problema em {dados.get('equipamento', 'equipamento não identificado')}",
            descricao_problema=dados.get('resumo', 'Criado por reconhecimento de voz'),
            prioridade=dados.get('urgencia', 'media'),
            origem_criacao='whatsapp_bot',
            status='aberta'
        )
        
        # US-005: Calcular SLA
        from app.services.os_service import OSService
        nova_os.prazo_conclusao = OSService.calcular_sla(nova_os.prioridade)
        nova_os.data_prevista = nova_os.prazo_conclusao

        db.session.add(nova_os)
        db.session.delete(estado)
        db.session.commit()

        return f"""✅ *OS CRIADA COM SUCESSO*

*Número:* {nova_os.numero_os}
*Equipamento:* {equipamento.nome if equipamento else 'Não encontrado'}
*Local:* {dados.get('local', 'Não especificado')}
*Prioridade:* {nova_os.prioridade.upper()}

Você pode acompanhar o andamento pelo sistema."""

    @staticmethod
    def _processar_comando_equip(terceirizado, texto):
        """Processa comando EQUIP:{id} de QR Code."""
        from app.models.estoque_models import Equipamento
        from app.services.whatsapp_service import WhatsAppService
        try:
            equip_id = int(texto.split(':')[1].strip())
        except (IndexError, ValueError):
            return {'acao': 'responder', 'resposta': "❌ Formato inválido. Use: EQUIP:ID"}

        equipamento = Equipamento.query.filter_by(id=equip_id, ativo=True).first()
        if not equipamento:
            return {'acao': 'responder', 'resposta': f"❌ Equipamento #{equip_id} não encontrado ou inativo."}

        # Salvar estado
        EstadoService.criar_ou_atualizar_estado(
            telefone=terceirizado.telefone,
            contexto={
                'fluxo': 'contexto_equipamento',
                'equipamento_id': equip_id,
                'equipamento_nome': equipamento.nome
            }
        )

        # Menu Interativo
        sections = [
            {
                "title": "Ordens de Serviço",
                "rows": [
                    {"id": f"abrir_os_{equip_id}", "title": "🆕 Abrir Chamado", "description": f"Criar OS para {equipamento.nome}"},
                    {"id": f"historico_{equip_id}", "title": "📋 Ver Histórico", "description": "Últimas OSs deste equipamento"}
                ]
            },
            {
                "title": "Informações",
                "rows": [
                    {"id": f"dados_tecnicos_{equip_id}", "title": "⚙️ Dados Técnicos", "description": "Informações do equipamento"},
                    {"id": "voltar_menu", "title": "↩️ Voltar ao Menu", "description": "Limpar contexto"}
                ]
            }
        ]

        WhatsAppService.send_list_message(
            phone=terceirizado.telefone,
            header=f"📟 {equipamento.nome}",
            body=f"""*Código:* {equipamento.codigo or 'N/A'}
*Unidade:* {equipamento.unidade.nome}
*Status:* {'🟢 Operacional' if equipamento.status == 'operacional' else '🔴 Manutenção'}

Escolha uma opção:""",
            sections=sections,
            button_text="Ações"
        )
        return {'acao': 'aguardar_interacao'}

    @staticmethod
    def _abrir_os_equipamento(terceirizado, equipamento_id):
        """Inicia fluxo de abertura de OS para equipamento específico."""
        from app.models.estoque_models import Equipamento
        equipamento = Equipamento.query.get(equipamento_id)
        EstadoService.criar_ou_atualizar_estado(
            telefone=terceirizado.telefone,
            contexto={'fluxo': 'abrir_os', 'etapa': 'aguardando_descricao', 'equipamento_id': equipamento_id}
        )
        msg = f"📝 *Criar OS para {equipamento.nome}*\n\nDescreva o problema encontrado:"
        return {'acao': 'responder', 'resposta': msg}

    @staticmethod
    def _exibir_historico_equipamento(terceirizado, equipamento_id):
        """Exibe últimas 5 OSs do equipamento."""
        from app.models.estoque_models import Equipamento, OrdemServico
        equipamento = Equipamento.query.get(equipamento_id)
        oss = OrdemServico.query.filter_by(equipamento_id=equipamento_id).order_by(OrdemServico.data_abertura.desc()).limit(5).all()

        if not oss:
            msg = f"📋 *Histórico: {equipamento.nome}*\n\nNenhuma OS registrada."
        else:
            msg = f"📋 *Histórico: {equipamento.nome}*\n\nÚltimas OSs:\n\n"
            for os in oss:
                emoji = {'aberta': '🔴', 'em_andamento': '🟡', 'concluida': '🟢'}.get(os.status, '⚪')
                msg += f"{emoji} *{os.numero_os}*\n   {os.titulo}\n   Data: {os.data_abertura.strftime('%d/%m/%Y')}\n\n"
        
        return {'acao': 'responder', 'resposta': msg}

    @staticmethod
    def _exibir_dados_tecnicos(terceirizado, equipamento_id):
        """Exibe informações técnicas do equipamento."""
        from app.models.estoque_models import Equipamento
        equip = Equipamento.query.get(equipamento_id)
        msg = f"""⚙️ *Dados Técnicos*

*Nome:* {equip.nome}
*Código:* {equip.codigo or 'N/A'}
*Unidade:* {equip.unidade.nome}
*Status:* {equip.status.upper()}
*Data Aquisição:* {equip.data_aquisicao.strftime('%d/%m/%Y') if equip.data_aquisicao else 'N/A'}
*Custo:* R$ {equip.custo_aquisicao or 0:.2f}

*Descrição:*
{equip.descricao or 'Sem descrição.'}"""
        return {'acao': 'responder', 'resposta': msg}
