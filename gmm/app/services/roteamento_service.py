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
            resultado_estado = EstadoService.processar_resposta_com_estado(estado, texto)
            if resultado_estado['sucesso']:
                return {'acao': 'responder', 'resposta': resultado_estado['resposta']}
            # If not processed successfully by state (e.g. invalid input), fall through or return help
            # For now, let's allow fallthrough to Commands if Input was not 'SIM'/'NAO'
        
        # 3. Parse Command
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

        # 6. Fallback (Forward to Manager)
        return {
            'acao': 'encaminhar',
            'destino': 'gerente',
            'mensagem': f"Mensagem de {terceirizado.nome}: {texto}"
        }
    
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

        # Se não reconheceu o ID, retorna menu padrão
        return {
            'acao': 'responder',
            'resposta': "Opção não reconhecida. Digite #AJUDA para ver o menu."
        }

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
