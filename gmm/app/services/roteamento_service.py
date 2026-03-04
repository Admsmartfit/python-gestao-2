import re
import json
import logging
from datetime import datetime, timedelta
from app.models.terceirizados_models import Terceirizado, ChamadoExterno
from app.models.whatsapp_models import EstadoConversa, RegrasAutomacao, ConfiguracaoWhatsApp
from app.services.comando_parser import ComandoParser
from app.services.comando_executores import ComandoExecutores
from app.services.estado_service import EstadoService

logger = logging.getLogger(__name__)


class RoteamentoService:
    """
    Decides how to process an incoming message.
    Flow: User Check -> Active State -> Command -> Auto Rule -> Fallback

    PRD v2.0: Agora reconhece tanto Terceirizados quanto Usuarios internos.
    Implementa respostas automáticas bidirecionais.
    """

    # ==================== MÉTODO PRINCIPAL ====================

    @staticmethod
    def processar(remetente: str, texto: str) -> dict:
        """
        Main routing logic.
        Returns a dict with 'acao', 'resposta', etc.

        PRD v2.0: Expandido para reconhecer usuarios internos.
        """
        from app.models.models import Usuario

        # 1. Identify Sender - PRD v2.0: Busca em Terceirizado E Usuario
        # Usa LIKE nos últimos 8 dígitos para ignorar formatação (com/sem 55, com máscara, etc.)
        termo_busca = remetente[-8:]
        terceirizado = Terceirizado.query.filter(
            Terceirizado.telefone.like(f'%{termo_busca}'),
            Terceirizado.ativo == True
        ).first()
        usuario = None
        if not terceirizado:
            usuario = Usuario.query.filter(
                Usuario.telefone.like(f'%{termo_busca}'),
                Usuario.ativo == True
            ).first()

        if not terceirizado and not usuario:
            # Telefone não cadastrado — verificando regras de automação
            logger.info(f"Telefone não cadastrado: {remetente} — percorrendo regras")
            
            # Busca regras ativas que se aplicam a desconhecidos
            regras = RegrasAutomacao.query.filter_by(ativo=True, para_desconhecidos=True).order_by(
                RegrasAutomacao.prioridade.desc()
            ).all()

            for r in regras:
                if RoteamentoService._match_regra(r, texto):
                    logger.info(f"Regra '{r.palavra_chave}' disparada para não-cadastrado {remetente}")
                    RoteamentoService._notificar_usuario_regra(r, remetente, texto)
                    
                    if r.acao == 'executar_funcao' and r.funcao_sistema:
                        return RoteamentoService._executar_funcao_sistema(r.funcao_sistema, None, remetente=remetente)
                    
                    if r.resposta_texto:
                        return {'acao': 'enviar_mensagem', 'telefone': remetente, 'mensagem': r.resposta_texto}
                    
                    return {'acao': 'ignorar'}

            return {'acao': 'ignorar'}

        # 2. Determina tipo de usuário e delega para handler específico
        if terceirizado:
            return RoteamentoService._processar_terceirizado(terceirizado, texto, remetente)
        elif usuario:
            return RoteamentoService._processar_usuario(usuario, texto, remetente)

    # ==================== PROCESSAMENTO POR TIPO DE USUÁRIO ====================

    @staticmethod
    def _processar_terceirizado(terceirizado, texto: str, remetente: str) -> dict:
        """
        Processa mensagens de terceirizados/fornecedores externos.
        Mantém compatibilidade com fluxo existente.
        """
        from app.services.whatsapp_service import WhatsAppService

        # 1. Check Active Conversation State
        estado = EstadoConversa.query.filter_by(telefone=remetente).order_by(
            EstadoConversa.updated_at.desc()
        ).first()

        # Determine if state is still valid (e.g., < 24h)
        if estado and (datetime.utcnow() - estado.updated_at).total_seconds() < 86400:
            ctx = estado.get_contexto()

            # PRD: Processar confirmação de OS
            if ctx.get('fluxo') == 'confirmar_os_nlp':
                resposta = RoteamentoService._processar_confirmacao_os_nlp(terceirizado, texto)
                return {'acao': 'responder', 'resposta': resposta}

            # PRD: Processar confirmação de chamado externo
            if estado.estado_atual == 'aguardando_confirmacao_os':
                return RoteamentoService._processar_confirmacao_chamado(terceirizado, texto, estado)

            # PRD: Processar conclusão de OS (foto/comentário)
            if estado.estado_atual == 'conclusao_aguardando_foto':
                return RoteamentoService._processar_conclusao_foto(terceirizado, texto, estado)

            if estado.estado_atual == 'conclusao_aguardando_comentario':
                return RoteamentoService._processar_conclusao_comentario(terceirizado, texto, estado)

            # PRD: Processar solicitação de peça
            if ctx.get('fluxo') == 'solicitar_peca':
                return RoteamentoService._processar_solicitacao_peca(terceirizado, texto, estado)

            # PRD: Processar agendamento
            if estado.estado_atual == 'agendamento_data':
                return RoteamentoService._processar_agendamento(terceirizado, texto, estado)

            # PRD: Processar avaliação
            if estado.estado_atual == 'aguardando_avaliacao':
                return RoteamentoService._processar_avaliacao(terceirizado, texto, estado)

            # Fluxo padrão de estado
            resultado_estado = EstadoService.processar_resposta_com_estado(estado, texto)
            if resultado_estado['sucesso']:
                return {'acao': 'responder', 'resposta': resultado_estado['resposta']}

        # 2. Parse comandos estruturados
        comando = ComandoParser.parse(texto)
        if comando:
            cmd_key = comando['comando']
            if cmd_key == 'COMPRA':
                res = ComandoExecutores.executar_compra(comando['params'], terceirizado)
            elif cmd_key == 'STATUS':
                res = ComandoExecutores.executar_status(terceirizado)
            elif cmd_key == 'STATUS_UPDATE':
                res = ComandoExecutores.executar_status_update(comando['params'], terceirizado)
            elif cmd_key == 'AJUDA':
                res = ComandoExecutores.executar_ajuda()
            elif cmd_key == 'CONFIRMAR_SEPARACAO':
                res = ComandoExecutores.executar_confirmar_separacao(comando['params'], terceirizado)
            else:
                res = {'sucesso': False, 'resposta': 'Comando desconhecido.'}

            return {'acao': 'responder', 'resposta': res['resposta']}

        # 5. Automation Rules
        regra = RegrasAutomacao.query.filter(
            RegrasAutomacao.ativo == True
        ).order_by(RegrasAutomacao.prioridade.desc()).all()

        for r in regra:
            if RoteamentoService._match_regra(r, texto):
                # Notifica usuário específico se configurado
                RoteamentoService._notificar_usuario_regra(r, remetente, texto, entidade=terceirizado)
                # PRD: Se ação é executar_funcao, executa a função
                if r.acao == 'executar_funcao' and r.funcao_sistema:
                    return RoteamentoService._executar_funcao_sistema(r.funcao_sistema, terceirizado)
                return {
                    'acao': r.acao,
                    'resposta': r.resposta_texto,
                    'encaminhar_para': r.encaminhar_para_perfil,
                    'funcao': r.funcao_sistema
                }

        # 6. NLP Analysis (Advanced Extraction)
        try:
            from app.services.nlp_service import NLPService
            entidades = NLPService.extrair_entidades(texto)
            if entidades and entidades.get('equipamento'):
                res_texto = f"Entendi que há um problema com: *{entidades['equipamento']}*.\n"
                res_texto += f"Local: {entidades['local'] or 'Não especificado'}\n"
                res_texto += f"Urgência: {entidades['urgencia'].upper()}\n\n"
                res_texto += "Deseja que eu abra uma Ordem de Serviço agora? (Responda SIM ou NÃO)"

                from app.extensions import db
                estado = EstadoConversa(
                    telefone=remetente,
                    estado_atual='confirmar_os_nlp',
                    usuario_tipo='terceirizado',
                    usuario_id=terceirizado.id
                )
                estado.set_contexto({
                    'fluxo': 'confirmar_os_nlp',
                    'dados': entidades
                })
                db.session.add(estado)
                db.session.commit()

                return {'acao': 'responder', 'resposta': res_texto}
        except Exception as e:
            logger.warning(f"NLP analysis failed: {e}")

        # 7. Fallback - Menu interativo para terceirizados
        return RoteamentoService._exibir_menu_terceirizado(terceirizado)

    @staticmethod
    def _processar_usuario(usuario, texto: str, remetente: str) -> dict:
        """
        PRD v2.0: Processa mensagens de usuários internos (admin, tecnico, comum).
        """
        from app.extensions import db

        # 1. Verifica estado ativo
        estado = EstadoConversa.query.filter_by(telefone=remetente).order_by(
            EstadoConversa.updated_at.desc()
        ).first()

        if estado and (datetime.utcnow() - estado.updated_at).total_seconds() < 86400:
            ctx = estado.get_contexto()

            # Processar avaliação do solicitante
            if estado.estado_atual == 'aguardando_avaliacao_solicitante':
                return RoteamentoService._processar_avaliacao_solicitante(usuario, texto, estado)

            # Processar resposta numérica do menu
            if ctx.get('fluxo') == 'menu_usuario':
                return RoteamentoService._processar_opcao_menu_usuario(usuario, texto, estado)

        # 2. Parse comandos administrativos
        texto_up = texto.upper().strip()

        # 3. Comandos específicos por tipo
        if usuario.tipo == 'admin':
            if texto_up.startswith('#ADMIN'):
                return RoteamentoService._processar_comando_admin(usuario, texto)

        # 4. Automation Rules
        regra = RegrasAutomacao.query.filter(
            RegrasAutomacao.ativo == True
        ).order_by(RegrasAutomacao.prioridade.desc()).all()

        for r in regra:
            if RoteamentoService._match_regra(r, texto):
                RoteamentoService._notificar_usuario_regra(r, remetente, texto, entidade=usuario)
                if r.acao == 'executar_funcao' and r.funcao_sistema:
                    return RoteamentoService._executar_funcao_sistema(r.funcao_sistema, usuario, is_usuario=True)
                return {
                    'acao': r.acao,
                    'resposta': r.resposta_texto,
                    'encaminhar_para': r.encaminhar_para_perfil,
                    'funcao': r.funcao_sistema
                }

        # 5. Fallback - Menu por tipo de usuário
        return RoteamentoService._exibir_menu_usuario(usuario)

    # ==================== MENUS POR TIPO DE USUÁRIO ====================

    @staticmethod
    def _exibir_menu_usuario(usuario) -> dict:
        """PRD v2.0: Menu diferenciado por tipo de usuário."""
        from app.extensions import db

        # Limpa estados antigos
        EstadoConversa.query.filter_by(telefone=usuario.telefone).delete()

        if usuario.tipo == 'admin':
            mensagem = f"""📊 *Menu Administrativo*

Olá {usuario.nome}!

1️⃣ Status do Sistema
2️⃣ Aprovar Pedidos Pendentes
3️⃣ Ver Chamados em Aberto
4️⃣ Relatório de SLA
5️⃣ Ver Terceirizados Ativos

Digite o número da opção desejada."""

        elif usuario.tipo == 'tecnico':
            mensagem = f"""🔧 *Menu Técnico*

Olá {usuario.nome}!

1️⃣ Minhas OS Abertas
2️⃣ Solicitar Peça
3️⃣ Consultar Estoque
4️⃣ Reportar Problema

Digite o número da opção desejada."""

        else:  # comum
            mensagem = f"""👤 *Sistema GMM*

Olá {usuario.nome}!

1️⃣ Abrir Chamado
2️⃣ Consultar Meus Chamados
3️⃣ Falar com Suporte

Digite o número da opção desejada."""

        # Cria estado para processar resposta numérica
        estado = EstadoConversa(
            telefone=usuario.telefone,
            estado_atual='menu_usuario',
            usuario_tipo=f'usuario_{usuario.tipo}',
            usuario_id=usuario.id
        )
        estado.set_contexto({
            'fluxo': 'menu_usuario',
            'tipo': usuario.tipo
        })
        db.session.add(estado)
        db.session.commit()

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _processar_opcao_menu_usuario(usuario, texto: str, estado) -> dict:
        """PRD v2.0: Processa opção numérica do menu de usuário."""
        from app.extensions import db
        from app.models.estoque_models import OrdemServico

        ctx = estado.get_contexto()
        tipo = ctx.get('tipo', usuario.tipo)

        try:
            opcao = int(texto.strip())
        except ValueError:
            return {'acao': 'responder', 'resposta': "⚠️ Por favor, digite apenas o número da opção."}

        # Limpa estado após processar
        db.session.delete(estado)
        db.session.commit()

        # Menu Admin
        if tipo == 'admin':
            if opcao == 1:
                return RoteamentoService._status_sistema(usuario)
            elif opcao == 2:
                return RoteamentoService._listar_pedidos_pendentes(usuario)
            elif opcao == 3:
                return RoteamentoService._listar_chamados_abertos(usuario)
            elif opcao == 4:
                return RoteamentoService._relatorio_sla(usuario)
            elif opcao == 5:
                return RoteamentoService._listar_terceirizados_ativos(usuario)

        # Menu Técnico
        elif tipo == 'tecnico':
            if opcao == 1:
                return RoteamentoService._listar_minhas_os_usuario(usuario)
            elif opcao == 2:
                return RoteamentoService._iniciar_fluxo_solicitacao_peca_usuario(usuario)
            elif opcao == 3:
                return RoteamentoService._consultar_estoque_usuario(usuario)
            elif opcao == 4:
                return RoteamentoService._reportar_problema(usuario)

        # Menu Comum
        else:
            if opcao == 1:
                return RoteamentoService._iniciar_abertura_chamado(usuario)
            elif opcao == 2:
                return RoteamentoService._consultar_meus_chamados(usuario)
            elif opcao == 3:
                return RoteamentoService._falar_com_suporte(usuario)

        return {'acao': 'responder', 'resposta': "⚠️ Opção inválida. Digite MENU para ver as opções."}

    @staticmethod
    def _exibir_menu_terceirizado(terceirizado) -> dict:
        """PRD v2.0: Menu contextual para terceirizados baseado em especialidades."""
        from app.services.whatsapp_service import WhatsAppService

        # Parse especialidades
        try:
            especialidades = json.loads(terceirizado.especialidades) if terceirizado.especialidades else []
        except:
            especialidades = []

        sections = [
            {
                "title": "Minhas Atividades",
                "rows": [
                    {"id": "minhas_os", "title": "📋 Meus Chamados", "description": "Ver chamados atribuídos"},
                    {"id": "os_disponiveis", "title": "🆕 Novos Chamados", "description": "Ver chamados disponíveis"}
                ]
            }
        ]

        # Adiciona seção de materiais se trabalha com manutenção
        if any(esp in especialidades for esp in ['Manutenção Elétrica', 'Manutenção Mecânica', 'Hidráulica', 'Geral']):
            sections.append({
                "title": "Materiais",
                "rows": [
                    {"id": "solicitar_peca", "title": "📦 Solicitar Peça", "description": "Pedir material para serviço"},
                    {"id": "consultar_estoque", "title": "📊 Ver Estoque", "description": "Consultar disponibilidade"}
                ]
            })
        else:
            # Fallback para todos
            sections.append({
                "title": "Materiais e Peças",
                "rows": [
                    {"id": "consultar_estoque", "title": "📊 Consultar Estoque", "description": "Verificar disponibilidade de itens"},
                    {"id": "solicitar_peca", "title": "📦 Solicitar Peça", "description": "Pedir item para manutenção"}
                ]
            })

        esp_texto = ', '.join(especialidades) if especialidades else 'Geral'

        WhatsAppService.send_list_message(
            phone=terceirizado.telefone,
            header="🤖 ASSISTENTE GMM",
            body=f"Olá {terceirizado.nome}!\n\n🔧 Especialidades: {esp_texto}\n\nComo posso ajudar você hoje?",
            button_text="Ver Opções",
            sections=sections
        )
        return {'acao': 'aguardar_interacao'}

    @staticmethod
    def _exibir_ajuda_usuario(usuario) -> dict:
        """Exibe mensagem de ajuda para usuários."""
        mensagem = """❓ *COMANDOS DISPONÍVEIS*

*Para Todos:*
• MENU - Ver menu de opções
• AJUDA - Ver esta mensagem

*Para Técnicos:*
• #STATUS - Ver seus chamados
• #ESTOQUE [código] - Consultar estoque

*Para Administradores:*
• #ADMIN STATUS - Status do sistema
• #ADMIN PENDENTES - Pedidos pendentes

Digite *MENU* para voltar ao menu principal."""

        return {'acao': 'responder', 'resposta': mensagem}

    # ==================== FUNÇÕES ADMIN ====================

    @staticmethod
    def _status_sistema(usuario) -> dict:
        """Status geral do sistema para admins."""
        from app.models.estoque_models import OrdemServico
        from app.models.terceirizados_models import ChamadoExterno

        os_abertas = OrdemServico.query.filter(
            OrdemServico.status.in_(['aberta', 'em_andamento'])
        ).count()

        chamados_pendentes = ChamadoExterno.query.filter(
            ChamadoExterno.status.in_(['aguardando', 'aceito'])
        ).count()

        terceirizados_ativos = Terceirizado.query.filter_by(ativo=True).count()

        mensagem = f"""📊 *STATUS DO SISTEMA*

📋 OSs Abertas: {os_abertas}
🔧 Chamados Pendentes: {chamados_pendentes}
👥 Terceirizados Ativos: {terceirizados_ativos}

_Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}_

Digite MENU para voltar."""

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _listar_pedidos_pendentes(usuario) -> dict:
        """Lista pedidos aguardando aprovação."""
        from app.models.estoque_models import PedidoCompra

        pedidos = PedidoCompra.query.filter_by(
            status='aguardando_aprovacao'
        ).order_by(PedidoCompra.created_at.desc()).limit(10).all()

        if not pedidos:
            return {'acao': 'responder', 'resposta': "✅ Não há pedidos pendentes de aprovação."}

        mensagem = f"📋 *PEDIDOS PENDENTES* ({len(pedidos)})\n\n"
        for p in pedidos:
            mensagem += f"#{p.id} - {p.estoque.nome if p.estoque else 'N/A'}\n"
            mensagem += f"   Qtd: {p.quantidade}\n"
            mensagem += f"   Solicitante: {p.solicitante.nome if p.solicitante else 'N/A'}\n\n"

        mensagem += "_Para aprovar, acesse o sistema web._"
        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _listar_chamados_abertos(usuario) -> dict:
        """Lista chamados externos abertos."""
        chamados = ChamadoExterno.query.filter(
            ChamadoExterno.status.in_(['aguardando', 'aceito', 'em_andamento'])
        ).order_by(ChamadoExterno.criado_em.desc()).limit(10).all()

        if not chamados:
            return {'acao': 'responder', 'resposta': "✅ Não há chamados abertos no momento."}

        mensagem = f"📋 *CHAMADOS ABERTOS* ({len(chamados)})\n\n"
        for ch in chamados:
            status_emoji = {'aguardando': '🟡', 'aceito': '🟢', 'em_andamento': '⚙️'}.get(ch.status, '⚪')
            mensagem += f"{status_emoji} #{ch.numero_chamado}\n"
            mensagem += f"   {ch.titulo[:30]}...\n"
            mensagem += f"   Terceirizado: {ch.terceirizado.nome if ch.terceirizado else 'N/A'}\n\n"

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _relatorio_sla(usuario) -> dict:
        """Relatório básico de SLA."""
        from app.models.estoque_models import OrdemServico

        total = OrdemServico.query.filter(
            OrdemServico.status == 'concluida'
        ).count()

        # OSs concluídas dentro do prazo
        dentro_prazo = OrdemServico.query.filter(
            OrdemServico.status == 'concluida',
            OrdemServico.data_conclusao <= OrdemServico.prazo_conclusao
        ).count()

        taxa = (dentro_prazo / total * 100) if total > 0 else 0

        mensagem = f"""📊 *RELATÓRIO DE SLA*

✅ Total Concluídas: {total}
⏰ Dentro do Prazo: {dentro_prazo}
📈 Taxa de Cumprimento: {taxa:.1f}%

_Período: Últimos 30 dias_

Digite MENU para voltar."""

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _listar_terceirizados_ativos(usuario) -> dict:
        """Lista terceirizados ativos."""
        terceirizados = Terceirizado.query.filter_by(ativo=True).limit(10).all()

        if not terceirizados:
            return {'acao': 'responder', 'resposta': "Nenhum terceirizado ativo encontrado."}

        mensagem = "👥 *TERCEIRIZADOS ATIVOS*\n\n"
        for t in terceirizados:
            avaliacao = f"⭐ {t.avaliacao_media}" if t.avaliacao_media else "Sem avaliação"
            mensagem += f"• {t.nome}\n"
            mensagem += f"  📞 {t.telefone}\n"
            mensagem += f"  {avaliacao}\n\n"

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _processar_comando_admin(usuario, texto: str) -> dict:
        """Processa comandos administrativos."""
        partes = texto.upper().split()
        if len(partes) < 2:
            return {'acao': 'responder', 'resposta': "⚠️ Comando incompleto. Use: #ADMIN [STATUS|PENDENTES]"}

        subcomando = partes[1]
        if subcomando == 'STATUS':
            return RoteamentoService._status_sistema(usuario)
        elif subcomando == 'PENDENTES':
            return RoteamentoService._listar_pedidos_pendentes(usuario)
        else:
            return {'acao': 'responder', 'resposta': "⚠️ Subcomando desconhecido. Use: #ADMIN STATUS ou #ADMIN PENDENTES"}

    # ==================== FUNÇÕES TÉCNICO/USUÁRIO ====================

    @staticmethod
    def _listar_minhas_os_usuario(usuario) -> dict:
        """Lista OSs do usuário técnico."""
        from app.models.estoque_models import OrdemServico

        oss = OrdemServico.query.filter_by(
            tecnico_id=usuario.id
        ).filter(
            OrdemServico.status.in_(['aberta', 'em_andamento', 'pausada'])
        ).order_by(OrdemServico.data_abertura.desc()).limit(10).all()

        if not oss:
            return {'acao': 'responder', 'resposta': "📋 Você não tem OSs abertas no momento."}

        mensagem = f"📋 *SUAS OSs ABERTAS* ({len(oss)})\n\n"
        for os in oss:
            status_emoji = {'aberta': '🆕', 'em_andamento': '⚙️', 'pausada': '⏸️'}.get(os.status, '❓')
            mensagem += f"{status_emoji} *#{os.numero_os}*\n"
            mensagem += f"   {os.titulo}\n"
            mensagem += f"   Prioridade: {os.prioridade.upper()}\n\n"

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _iniciar_fluxo_solicitacao_peca_usuario(usuario) -> dict:
        """Inicia fluxo de solicitação de peça para usuário."""
        return {'acao': 'responder', 'resposta': "📦 *Solicitação de Peça*\n\nPara solicitar uma peça, envie:\n\n#COMPRA [código] [quantidade]\n\n_Exemplo: #COMPRA ROL001 5_"}

    @staticmethod
    def _consultar_estoque_usuario(usuario) -> dict:
        """Consulta estoque para usuário."""
        return {'acao': 'responder', 'resposta': "📊 *Consulta de Estoque*\n\nPara consultar uma peça, envie:\n\n#ESTOQUE [código]\n\n_Exemplo: #ESTOQUE ROL001_"}

    @staticmethod
    def _reportar_problema(usuario) -> dict:
        """Inicia fluxo de reporte de problema."""
        return {'acao': 'responder', 'resposta': "🔧 *Reportar Problema*\n\nDescreva o problema encontrado e envie.\n\nOu acesse o sistema web para abrir uma OS completa."}

    @staticmethod
    def _iniciar_abertura_chamado(usuario) -> dict:
        """Inicia abertura de chamado para usuário comum."""
        return {'acao': 'responder', 'resposta': "📋 *Abrir Chamado*\n\nPara abrir um chamado, acesse o sistema web ou descreva brevemente o problema aqui.\n\nUm técnico entrará em contato."}

    @staticmethod
    def _consultar_meus_chamados(usuario) -> dict:
        """Consulta chamados do usuário."""
        chamados = ChamadoExterno.query.filter_by(
            criado_por=usuario.id
        ).order_by(ChamadoExterno.criado_em.desc()).limit(5).all()

        if not chamados:
            return {'acao': 'responder', 'resposta': "📋 Você não tem chamados registrados."}

        mensagem = "📋 *SEUS CHAMADOS*\n\n"
        for ch in chamados:
            status_emoji = {'aguardando': '🟡', 'aceito': '🟢', 'concluido': '✅', 'recusado': '❌'}.get(ch.status, '⚪')
            mensagem += f"{status_emoji} #{ch.numero_chamado}\n"
            mensagem += f"   {ch.titulo[:30]}\n"
            mensagem += f"   Status: {ch.status.replace('_', ' ').title()}\n\n"

        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _falar_com_suporte(usuario) -> dict:
        """Encaminha para suporte."""
        return {'acao': 'responder', 'resposta': "📞 *Suporte*\n\nSua mensagem será encaminhada para o suporte.\n\nDescreva seu problema ou dúvida que entraremos em contato."}

    # ==================== CONFIRMAÇÃO DE CHAMADO (PRD Tarefa 2.1) ====================

    @staticmethod
    def _processar_confirmacao_chamado(terceirizado, texto: str, estado) -> dict:
        """PRD: Processa confirmação de OS por terceirizado."""
        from app.extensions import db

        ctx = estado.get_contexto()
        chamado_id = ctx.get('chamado_id')
        chamado = ChamadoExterno.query.get(chamado_id)

        if not chamado:
            db.session.delete(estado)
            db.session.commit()
            return {'acao': 'responder', 'resposta': "❌ Chamado não encontrado."}

        texto_lower = texto.lower().strip()

        # Aceite
        if texto_lower in ['sim', 's', 'aceito', 'ok', 'confirmo']:
            chamado.status = 'aceito'
            chamado.data_inicio = datetime.utcnow()
            db.session.delete(estado)
            db.session.commit()

            # NOTIFICA SOLICITANTE
            RoteamentoService._notificar_solicitante_os_aceita(chamado)

            resposta = f"""✅ *CHAMADO ACEITO*

Obrigado por confirmar, {terceirizado.nome}!

📋 Chamado #{chamado.numero_chamado} registrado como ACEITO.
⏰ Prazo de conclusão: {chamado.prazo_combinado.strftime('%d/%m/%Y às %H:%M') if chamado.prazo_combinado else 'N/A'}

Para atualizar o status, envie:
*#STATUS ANDAMENTO* - Quando iniciar
*#STATUS CONCLUIDO* - Ao finalizar
"""
            return {'acao': 'responder', 'resposta': resposta}

        # Recusa
        elif texto_lower in ['nao', 'não', 'n', 'recuso', 'não posso']:
            chamado.status = 'recusado'
            db.session.delete(estado)
            db.session.commit()

            # NOTIFICA SOLICITANTE
            RoteamentoService._notificar_solicitante_os_recusada(chamado, terceirizado)

            resposta = f"""❌ *CHAMADO RECUSADO*

Entendido. O chamado #{chamado.numero_chamado} foi marcado como RECUSADO.

O solicitante será notificado e outro prestador será acionado.

Obrigado!
"""
            return {'acao': 'responder', 'resposta': resposta}

        # Não entendeu
        else:
            return {'acao': 'responder', 'resposta': "⚠️ Não entendi. Responda *SIM* para aceitar ou *NÃO* para recusar o chamado."}

    # ==================== SOLICITAÇÃO DE PEÇA (PRD Tarefa 2.3) ====================

    @staticmethod
    def _iniciar_fluxo_solicitacao_peca(terceirizado) -> dict:
        """PRD: Inicia fluxo para solicitar peça com validação de chamado ativo."""
        from app.extensions import db

        # Verifica se tem chamado ativo
        chamado_ativo = ChamadoExterno.query.filter_by(
            terceirizado_id=terceirizado.id
        ).filter(
            ChamadoExterno.status.in_(['aceito', 'em_andamento'])
        ).first()

        if not chamado_ativo:
            return {
                'acao': 'responder',
                'resposta': "⚠️ Você precisa ter um chamado ativo para solicitar peças.\n\nPrimeiro aceite um chamado ou inicie o atendimento."
            }

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            chamado_id=chamado_ativo.id,
            estado_atual='solicitacao_peca_codigo',
            usuario_tipo='terceirizado',
            usuario_id=terceirizado.id
        )
        estado.set_contexto({
            'fluxo': 'solicitar_peca',
            'etapa': 'aguardando_codigo',
            'chamado_id': chamado_ativo.id
        })
        db.session.add(estado)
        db.session.commit()

        mensagem = f"""📦 *SOLICITAÇÃO DE PEÇA*

📋 Chamado: #{chamado_ativo.numero_chamado}

Informe o código ou nome da peça necessária:

_Exemplo: ROL001 ou Rolamento 6205_
"""
        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _processar_solicitacao_peca(terceirizado, texto: str, estado) -> dict:
        """PRD: Processa etapas do fluxo de solicitação de peça."""
        from app.models.estoque_models import Estoque, PedidoCompra
        from app.extensions import db

        ctx = estado.get_contexto()
        etapa = ctx.get('etapa')

        # Etapa 1: Código informado
        if etapa == 'aguardando_codigo':
            item = Estoque.query.filter(
                db.or_(
                    Estoque.codigo.ilike(f'%{texto}%'),
                    Estoque.nome.ilike(f'%{texto}%')
                )
            ).first()

            if not item:
                return {
                    'acao': 'responder',
                    'resposta': f"❌ Item '{texto}' não encontrado no estoque.\n\nTente outro código ou nome."
                }

            ctx['item_id'] = item.id
            ctx['item_nome'] = item.nome
            ctx['etapa'] = 'aguardando_quantidade'
            estado.set_contexto(ctx)
            estado.estado_atual = 'solicitacao_peca_quantidade'
            db.session.commit()

            return {
                'acao': 'responder',
                'resposta': f"""✅ Item encontrado: *{item.nome}*

📊 Estoque disponível: {item.quantidade_atual} {item.unidade_medida}

Informe a quantidade necessária:
"""
            }

        # Etapa 2: Quantidade informada
        elif etapa == 'aguardando_quantidade':
            try:
                quantidade = int(texto)
            except ValueError:
                return {'acao': 'responder', 'resposta': "⚠️ Por favor, informe um número válido."}

            item = Estoque.query.get(ctx['item_id'])

            if quantidade > item.quantidade_atual:
                return {
                    'acao': 'responder',
                    'resposta': f"""⚠️ *QUANTIDADE INSUFICIENTE*

Solicitado: {quantidade} {item.unidade_medida}
Disponível: {item.quantidade_atual} {item.unidade_medida}

Para criar pedido de compra, use:
#COMPRA {item.codigo} {quantidade}
"""
                }

            # Cria pedido de separação
            chamado = ChamadoExterno.query.get(ctx['chamado_id'])

            pedido = PedidoCompra(
                estoque_id=item.id,
                quantidade=quantidade,
                solicitante_id=chamado.criado_por if chamado else None,
                status='aguardando_separacao',
                justificativa=f'Solicitado por {terceirizado.nome} via WhatsApp - Chamado #{chamado.numero_chamado if chamado else "N/A"}'
            )
            db.session.add(pedido)
            db.session.delete(estado)
            db.session.commit()

            # NOTIFICA RESPONSÁVEL PELO ESTOQUE
            RoteamentoService._notificar_estoque_separacao(pedido, terceirizado)

            return {
                'acao': 'responder',
                'resposta': f"""✅ *SOLICITAÇÃO REGISTRADA*

📦 Item: {item.nome}
📊 Quantidade: {quantidade} {item.unidade_medida}
📋 Pedido: #{pedido.id}

O setor de estoque foi notificado e separará o material em breve.

Você receberá confirmação quando estiver disponível para retirada.
"""
            }

        return {'acao': 'responder', 'resposta': "⚠️ Erro no fluxo. Digite MENU para recomeçar."}

    # ==================== CONCLUSÃO DE OS (PRD Tarefa 2.4) ====================

    @staticmethod
    def _iniciar_fluxo_conclusao(terceirizado, chamado):
        """PRD: Inicia fluxo de conclusão solicitando foto."""
        from app.extensions import db
        from app.services.whatsapp_service import WhatsAppService

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            chamado_id=chamado.id,
            estado_atual='conclusao_aguardando_foto',
            usuario_tipo='terceirizado',
            usuario_id=terceirizado.id
        )
        estado.set_contexto({
            'fluxo': 'conclusao_os',
            'etapa': 'aguardando_foto',
            'chamado_id': chamado.id
        })
        db.session.add(estado)
        db.session.commit()

        mensagem = f"""📸 *CONCLUSÃO DE OS*

Para finalizar o chamado #{chamado.numero_chamado}, por favor envie:

1️⃣ Foto do serviço concluído (obrigatório)
2️⃣ Comentário final (opcional)

_Aguardando foto..._
"""

        WhatsAppService.enviar_mensagem(
            telefone=terceirizado.telefone,
            texto=mensagem,
            prioridade=1
        )

    @staticmethod
    def _processar_conclusao_foto(terceirizado, texto: str, estado) -> dict:
        """PRD: Processa recebimento de foto de conclusão (ou pula se não tiver)."""
        from app.extensions import db

        ctx = estado.get_contexto()

        # Se usuário digitou PULAR, vai para comentário
        if texto.upper() == 'PULAR':
            ctx['etapa'] = 'aguardando_comentario'
            ctx['foto_path'] = None
            estado.set_contexto(ctx)
            estado.estado_atual = 'conclusao_aguardando_comentario'
            db.session.commit()

            return {
                'acao': 'responder',
                'resposta': "📝 Ok, sem foto.\n\nAgora envie um comentário final sobre o serviço realizado (ou digite PULAR):"
            }

        # Assume que foto foi recebida via webhook separado
        # Aqui processamos como texto de confirmação
        ctx['etapa'] = 'aguardando_comentario'
        estado.set_contexto(ctx)
        estado.estado_atual = 'conclusao_aguardando_comentario'
        db.session.commit()

        return {
            'acao': 'responder',
            'resposta': "✅ *Recebido!*\n\nAgora envie um comentário final sobre o serviço realizado (ou digite PULAR):"
        }

    @staticmethod
    def _processar_conclusao_comentario(terceirizado, texto: str, estado) -> dict:
        """PRD: Processa comentário final e conclui chamado."""
        from app.extensions import db

        ctx = estado.get_contexto()
        chamado_id = ctx.get('chamado_id')
        chamado = ChamadoExterno.query.get(chamado_id)

        if not chamado:
            db.session.delete(estado)
            db.session.commit()
            return {'acao': 'responder', 'resposta': "❌ Chamado não encontrado."}

        # Atualiza chamado
        if texto.upper() != 'PULAR':
            chamado.feedback = texto

        chamado.status = 'concluido'
        chamado.data_conclusao = datetime.utcnow()

        db.session.delete(estado)
        db.session.commit()

        # NOTIFICA SOLICITANTE
        RoteamentoService._notificar_solicitante_os_concluida(chamado, ctx.get('foto_path'))

        # Solicita avaliação
        return RoteamentoService._solicitar_avaliacao(terceirizado, chamado)

    @staticmethod
    def _solicitar_avaliacao(terceirizado, chamado) -> dict:
        """PRD: Solicita avaliação do atendimento."""
        from app.extensions import db

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            chamado_id=chamado.id,
            estado_atual='aguardando_avaliacao',
            usuario_tipo='terceirizado',
            usuario_id=terceirizado.id
        )
        estado.set_contexto({
            'fluxo': 'avaliacao',
            'chamado_id': chamado.id
        })
        db.session.add(estado)
        db.session.commit()

        mensagem = f"""⭐ *AVALIAÇÃO DO ATENDIMENTO*

Como você avalia o suporte recebido para o chamado #{chamado.numero_chamado}?

Envie uma nota de 1 a 5:
⭐ 1 - Muito Ruim
⭐⭐ 2 - Ruim
⭐⭐⭐ 3 - Regular
⭐⭐⭐⭐ 4 - Bom
⭐⭐⭐⭐⭐ 5 - Excelente

Digite apenas o número (1 a 5):
"""
        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _processar_avaliacao(terceirizado, texto: str, estado) -> dict:
        """PRD: Processa avaliação do terceirizado."""
        from app.extensions import db

        ctx = estado.get_contexto()
        chamado_id = ctx.get('chamado_id')
        chamado = ChamadoExterno.query.get(chamado_id)

        try:
            nota = int(texto.strip())
            if nota < 1 or nota > 5:
                raise ValueError
        except ValueError:
            return {'acao': 'responder', 'resposta': "⚠️ Por favor, envie uma nota de 1 a 5."}

        if chamado:
            chamado.avaliacao = nota

        db.session.delete(estado)
        db.session.commit()

        estrelas = '⭐' * nota
        return {
            'acao': 'responder',
            'resposta': f"""{estrelas} *AVALIAÇÃO REGISTRADA*

Obrigado por avaliar!

Sua nota: {nota}/5

Sua opinião nos ajuda a melhorar nossos serviços.
"""
        }

    @staticmethod
    def _processar_avaliacao_solicitante(usuario, texto: str, estado) -> dict:
        """PRD: Processa avaliação do solicitante."""
        from app.extensions import db

        ctx = estado.get_contexto()
        chamado_id = ctx.get('chamado_id')
        chamado = ChamadoExterno.query.get(chamado_id)

        try:
            nota = int(texto.strip())
            if nota < 1 or nota > 5:
                raise ValueError
        except ValueError:
            return {'acao': 'responder', 'resposta': "⚠️ Por favor, envie uma nota de 1 a 5."}

        if chamado:
            chamado.avaliacao = nota

            # Atualiza média do terceirizado
            if chamado.terceirizado:
                terceirizado = chamado.terceirizado
                chamados_avaliados = ChamadoExterno.query.filter_by(
                    terceirizado_id=terceirizado.id
                ).filter(ChamadoExterno.avaliacao.isnot(None)).all()

                if chamados_avaliados:
                    media = sum(c.avaliacao for c in chamados_avaliados) / len(chamados_avaliados)
                    terceirizado.avaliacao_media = round(media, 2)

        db.session.delete(estado)
        db.session.commit()

        estrelas = '⭐' * nota
        return {
            'acao': 'responder',
            'resposta': f"""{estrelas} *AVALIAÇÃO REGISTRADA*

Obrigado por avaliar!

Sua nota: {nota}/5

Sua opinião nos ajuda a melhorar nossos serviços.
"""
        }

    # ==================== AGENDAMENTO (PRD Tarefa 3.3) ====================

    @staticmethod
    def _iniciar_agendamento_visita(terceirizado, chamado_id) -> dict:
        """PRD: Inicia fluxo de agendamento de visita."""
        from app.extensions import db

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            chamado_id=chamado_id,
            estado_atual='agendamento_data',
            usuario_tipo='terceirizado',
            usuario_id=terceirizado.id
        )
        estado.set_contexto({
            'fluxo': 'agendamento',
            'chamado_id': chamado_id,
            'etapa': 'aguardando_data'
        })
        db.session.add(estado)
        db.session.commit()

        mensagem = """📅 *AGENDAMENTO DE VISITA*

Informe a data e hora prevista para a visita:

Formato: DD/MM/AAAA HH:MM

_Exemplo: 15/01/2026 14:30_
"""
        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _processar_agendamento(terceirizado, texto: str, estado) -> dict:
        """PRD: Processa data de agendamento."""
        from app.extensions import db

        ctx = estado.get_contexto()
        chamado_id = ctx.get('chamado_id')

        try:
            data_visita = datetime.strptime(texto.strip(), '%d/%m/%Y %H:%M')
        except ValueError:
            return {
                'acao': 'responder',
                'resposta': "⚠️ Formato inválido. Use: DD/MM/AAAA HH:MM\n\n_Exemplo: 15/01/2026 14:30_"
            }

        if data_visita < datetime.now():
            return {'acao': 'responder', 'resposta': "⚠️ A data deve ser futura."}

        chamado = ChamadoExterno.query.get(chamado_id)
        if chamado:
            chamado.data_inicio = data_visita
            chamado.status = 'agendado'

        db.session.delete(estado)
        db.session.commit()

        # NOTIFICA SOLICITANTE
        RoteamentoService._notificar_solicitante_agendamento(chamado, data_visita)

        return {
            'acao': 'responder',
            'resposta': f"""✅ *VISITA AGENDADA*

📅 Data: {data_visita.strftime('%d/%m/%Y às %H:%M')}
📋 Chamado: #{chamado.numero_chamado if chamado else 'N/A'}

O solicitante foi notificado.

Você receberá um lembrete 1 dia antes.
"""
        }

    # ==================== NOTIFICAÇÕES BIDIRECIONAIS (PRD Etapa 4) ====================

    @staticmethod
    def _notificar_solicitante_os_aceita(chamado):
        """PRD 4.1: Notifica solicitante que terceirizado aceitou OS."""
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario

        solicitante = Usuario.query.get(chamado.criado_por)
        if not solicitante or not solicitante.telefone:
            logger.warning(f"Solicitante do chamado {chamado.id} não tem telefone cadastrado")
            return

        terceirizado = chamado.terceirizado

        mensagem = f"""✅ *CHAMADO ACEITO*

📋 Chamado #{chamado.numero_chamado} foi aceito!

👤 Prestador: {terceirizado.nome}
🏢 Empresa: {terceirizado.nome_empresa or 'N/A'}
📞 Telefone: {terceirizado.telefone}
⭐ Avaliação: {terceirizado.avaliacao_media or 'Sem avaliação'}

📝 Título: {chamado.titulo}
⏰ Aceito em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

Você receberá atualizações sobre o andamento.
"""

        WhatsAppService.enviar_mensagem(
            telefone=solicitante.telefone,
            texto=mensagem,
            prioridade=1
        )

    @staticmethod
    def _notificar_solicitante_os_recusada(chamado, terceirizado):
        """PRD 4.1: Notifica solicitante que terceirizado recusou OS."""
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario

        solicitante = Usuario.query.get(chamado.criado_por)
        if not solicitante or not solicitante.telefone:
            return

        mensagem = f"""❌ *CHAMADO RECUSADO*

📋 Chamado #{chamado.numero_chamado}

O prestador {terceirizado.nome} recusou o atendimento.

🔄 Providências:
- Outro prestador será acionado automaticamente
- Você receberá notificação quando alguém aceitar

⏰ Aguarde contato em breve.
"""

        WhatsAppService.enviar_mensagem(
            telefone=solicitante.telefone,
            texto=mensagem,
            prioridade=1
        )

        # Re-notifica outros terceirizados
        try:
            from app.tasks.whatsapp_tasks import notificar_terceirizados_os_disponivel
            notificar_terceirizados_os_disponivel.delay(chamado.id)
        except Exception as e:
            logger.warning(f"Falha ao re-notificar terceirizados: {e}")

    @staticmethod
    def _notificar_solicitante_atualizacao(chamado, novo_status):
        """PRD 4.2: Notifica solicitante sobre mudança de status."""
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario

        solicitante = Usuario.query.get(chamado.criado_por)
        if not solicitante or not solicitante.telefone:
            return

        status_emoji = {
            'em_andamento': '⚙️',
            'pausado': '⏸️',
            'concluido': '✅',
            'cancelado': '❌'
        }

        status_texto = {
            'em_andamento': 'EM ANDAMENTO',
            'pausado': 'PAUSADO',
            'concluido': 'CONCLUÍDO',
            'cancelado': 'CANCELADO'
        }

        emoji = status_emoji.get(novo_status, '🔄')
        texto_status = status_texto.get(novo_status, novo_status.upper())

        mensagem = f"""{emoji} *STATUS ATUALIZADO*

📋 Chamado: #{chamado.numero_chamado}
🔄 Novo Status: *{texto_status}*
👤 Prestador: {chamado.terceirizado.nome if chamado.terceirizado else 'N/A'}

📝 {chamado.titulo}
"""

        if novo_status == 'em_andamento':
            mensagem += "\n\n⚙️ O prestador iniciou o atendimento."
        elif novo_status == 'pausado':
            mensagem += "\n\n⏸️ O atendimento foi temporariamente pausado."
        elif novo_status == 'concluido':
            mensagem += "\n\n✅ Serviço concluído!"

        WhatsAppService.enviar_mensagem(
            telefone=solicitante.telefone,
            texto=mensagem,
            prioridade=1
        )

    @staticmethod
    def _notificar_estoque_separacao(pedido, terceirizado):
        """PRD 4.3: Notifica responsável pelo estoque sobre solicitação de separação."""
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario

        responsaveis = Usuario.query.filter(
            Usuario.tipo.in_(['admin', 'estoque']),
            Usuario.ativo == True,
            Usuario.telefone.isnot(None)
        ).all()

        if not responsaveis:
            logger.warning("Nenhum responsável de estoque com telefone cadastrado")
            return

        item = pedido.estoque

        mensagem = f"""📦 *SOLICITAÇÃO DE SEPARAÇÃO*

📋 Pedido: #{pedido.id}
👤 Solicitante: {terceirizado.nome}
📞 Telefone: {terceirizado.telefone}

📦 *Item Solicitado:*
Código: {item.codigo if item else 'N/A'}
Nome: {item.nome if item else 'N/A'}
Quantidade: {pedido.quantidade} {item.unidade_medida if item else ''}

📊 Estoque Atual: {item.quantidade_atual if item else 'N/A'}

⚠️ Por favor, separe o material para retirada.

Para confirmar separação, responda:
*#SEPARADO {pedido.id}*
"""

        for responsavel in responsaveis:
            WhatsAppService.enviar_mensagem(
                telefone=responsavel.telefone,
                texto=mensagem,
                prioridade=1
            )

    @staticmethod
    def _notificar_solicitante_os_concluida(chamado, foto_path=None):
        """PRD 4.4: Notifica solicitante da conclusão com foto anexa."""
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario
        from app.extensions import db

        solicitante = Usuario.query.get(chamado.criado_por)
        if not solicitante or not solicitante.telefone:
            return

        mensagem = f"""✅ *CHAMADO CONCLUÍDO*

📋 #{chamado.numero_chamado}
📝 {chamado.titulo}

👤 Prestador: {chamado.terceirizado.nome if chamado.terceirizado else 'N/A'}
📅 Concluído em: {chamado.data_conclusao.strftime('%d/%m/%Y às %H:%M') if chamado.data_conclusao else 'Agora'}

💬 *Comentário Final:*
{chamado.feedback or 'Sem comentário.'}

⭐ *Avalie o atendimento:*
Para avaliar, responda com nota de 1 a 5.
"""

        WhatsAppService.enviar_mensagem(
            telefone=solicitante.telefone,
            texto=mensagem,
            prioridade=1
        )

        # Cria estado para aguardar avaliação
        estado = EstadoConversa(
            telefone=solicitante.telefone,
            chamado_id=chamado.id,
            estado_atual='aguardando_avaliacao_solicitante',
            usuario_tipo=f'usuario_{solicitante.tipo}',
            usuario_id=solicitante.id
        )
        estado.set_contexto({
            'fluxo': 'avaliacao_solicitante',
            'chamado_id': chamado.id
        })
        db.session.add(estado)
        db.session.commit()

    @staticmethod
    def _notificar_solicitante_agendamento(chamado, data_visita):
        """PRD 4.5: Notifica solicitante sobre agendamento de visita."""
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario

        if not chamado:
            return

        solicitante = Usuario.query.get(chamado.criado_por)
        if not solicitante or not solicitante.telefone:
            return

        mensagem = f"""📅 *VISITA AGENDADA*

📋 Chamado: #{chamado.numero_chamado}
👤 Prestador: {chamado.terceirizado.nome if chamado.terceirizado else 'N/A'}
📞 Contato: {chamado.terceirizado.telefone if chamado.terceirizado else 'N/A'}

📅 *Data e Hora:*
{data_visita.strftime('%d/%m/%Y às %H:%M')}

⚠️ Certifique-se de que haverá alguém no local para receber o prestador.

Você receberá um lembrete 1 dia antes.
"""

        WhatsAppService.enviar_mensagem(
            telefone=solicitante.telefone,
            texto=mensagem,
            prioridade=1
        )

    # ==================== FUNÇÕES AUXILIARES ====================

    @staticmethod
    def _match_regra(regra: RegrasAutomacao, texto: str) -> bool:
        """Checks if text matches the rule pattern."""
        if not regra.palavra_chave:
            return False

        if regra.tipo_correspondencia in ('exata', 'exato'):   # aceita ambas as grafias
            return texto.strip().upper() == regra.palavra_chave.upper()

        elif regra.tipo_correspondencia == 'contem':
            return regra.palavra_chave.upper() in texto.upper()

        elif regra.tipo_correspondencia == 'regex':
            try:
                return re.search(regra.palavra_chave, texto, re.IGNORECASE) is not None
            except:
                return False

        return False

    @staticmethod
    def _notificar_usuario_regra(regra, remetente: str, texto: str, entidade=None):
        """
        Se a regra tem notificar_usuario_id configurado, envia notificação para
        o usuário interno especificado informando que a regra disparou.
        """
        if not regra.notificar_usuario_id:
            return
        try:
            from app.models.models import Usuario
            from app.services.whatsapp_service import WhatsAppService

            usuario_notif = Usuario.query.get(regra.notificar_usuario_id)
            if not usuario_notif or not usuario_notif.telefone:
                logger.warning(f"Usuário {regra.notificar_usuario_id} não tem telefone — não notificado")
                return

            nome_remetente = getattr(entidade, 'nome', remetente) if entidade else remetente

            msg = (
                f"🔔 *Alerta de Automação WhatsApp*\n\n"
                f"Gatilho: *{regra.palavra_chave}*\n"
                f"Remetente: {nome_remetente} ({remetente})\n\n"
                f"Mensagem recebida:\n_{texto[:300]}_"
            )
            WhatsAppService.enviar_mensagem(
                telefone=usuario_notif.telefone,
                texto=msg,
                prioridade=1
            )
            logger.info(f"Notificação de regra enviada para {usuario_notif.nome} ({usuario_notif.telefone})")
        except Exception as e:
            logger.warning(f"Erro ao notificar usuário da regra: {e}")

    @staticmethod
    def _executar_funcao_sistema(funcao_nome: str, entidade, is_usuario=False, remetente=None) -> dict:
        """Executa função do sistema por nome."""
        # Se não há entidade (usuário/terceirizado desconhecido), algumas funções não podem ser executadas
        if not entidade and funcao_nome not in ['exibir_menu_principal', 'exibir_ajuda', 'falar_com_suporte']:
            return {'acao': 'responder', 'resposta': "⚠️ Para acessar esta função, seu número precisa estar cadastrado no sistema."}

        # Menu Principal
        if funcao_nome == 'exibir_menu_principal':
            if is_usuario:
                return RoteamentoService._exibir_menu_usuario(entidade)
            elif entidade: # Terceirizado
                return RoteamentoService._exibir_menu_terceirizado(entidade)
            else: # Desconhecido
                return {'acao': 'responder', 'resposta': "👋 Olá! Bem-vindo ao GMM.\n\nSeu número não está cadastrado, por isso não posso exibir o menu completo.\n\nEntre em contato com o suporte se precisar de ajuda."}

        # Funções Administrativas
        elif funcao_nome == 'status_sistema':
            return RoteamentoService._status_sistema(entidade)
        elif funcao_nome == 'listar_pedidos_pendentes':
            return RoteamentoService._listar_pedidos_pendentes(entidade)
        elif funcao_nome == 'listar_chamados_abertos':
            return RoteamentoService._listar_chamados_abertos(entidade)
        elif funcao_nome == 'relatorio_sla':
            return RoteamentoService._relatorio_sla(entidade)
        elif funcao_nome == 'listar_terceirizados_ativos':
            return RoteamentoService._listar_terceirizados_ativos(entidade)

        # Funções de Técnico/Usuário
        elif funcao_nome == 'listar_minhas_os':
            if is_usuario:
                return RoteamentoService._listar_minhas_os_usuario(entidade)
            else:
                return RoteamentoService._listar_minhas_os(entidade)
        elif funcao_nome == 'iniciar_solicitacao_peca':
            if is_usuario:
                return RoteamentoService._iniciar_fluxo_solicitacao_peca_usuario(entidade)
            else:
                return RoteamentoService._iniciar_fluxo_solicitacao_peca(entidade)
        elif funcao_nome == 'consultar_estoque':
            if is_usuario:
                return RoteamentoService._consultar_estoque_usuario(entidade)
            else:
                return RoteamentoService._consultar_estoque(entidade)
        elif funcao_nome == 'reportar_problema':
            return RoteamentoService._reportar_problema(entidade)

        # Funções de Usuário Comum
        elif funcao_nome == 'abrir_chamado':
            return RoteamentoService._iniciar_abertura_chamado(entidade)
        elif funcao_nome == 'consultar_meus_chamados':
            return RoteamentoService._consultar_meus_chamados(entidade)
        elif funcao_nome == 'falar_com_suporte':
            return RoteamentoService._falar_com_suporte(entidade)

        # Ajuda
        elif funcao_nome == 'exibir_ajuda':
            if is_usuario:
                return RoteamentoService._exibir_ajuda_usuario(entidade)
            else:
                return {'acao': 'responder', 'resposta': "❓ Digite MENU para ver as opções disponíveis."}

        return {'acao': 'responder', 'resposta': f"Função '{funcao_nome}' não implementada."}

    # ==================== MÉTODOS LEGADOS (COMPATIBILIDADE) ====================

    @staticmethod
    def _exibir_menu_inicial(terceirizado):
        """Mantém compatibilidade - redireciona para novo menu."""
        return RoteamentoService._exibir_menu_terceirizado(terceirizado)

    @staticmethod
    def processar_resposta_interativa(notificacao):
        """Processa resposta de mensagens interativas (list messages ou buttons)."""
        from app.models.models import Usuario

        resposta_id = notificacao.mensagem
        telefone = notificacao.remetente

        # Identifica terceirizado ou usuário
        terceirizado = Terceirizado.query.filter_by(telefone=telefone).first()
        usuario = Usuario.query.filter_by(telefone=telefone, ativo=True).first()

        if not terceirizado and not usuario:
            return {'acao': 'ignorar', 'motivo': 'Remetente não cadastrado'}

        entidade = terceirizado if terceirizado else usuario
        is_usuario = usuario is not None and terceirizado is None

        # Roteamento baseado no ID da resposta
        if resposta_id == 'minhas_os':
            if is_usuario:
                return RoteamentoService._listar_minhas_os_usuario(entidade)
            return RoteamentoService._listar_minhas_os(entidade)

        elif resposta_id == 'os_disponiveis':
            return RoteamentoService._listar_os_disponiveis(entidade)

        elif resposta_id == 'abrir_os':
            return RoteamentoService._iniciar_fluxo_abrir_os(entidade)

        elif resposta_id == 'solicitar_peca':
            if is_usuario:
                return RoteamentoService._iniciar_fluxo_solicitacao_peca_usuario(entidade)
            return RoteamentoService._iniciar_fluxo_solicitacao_peca(entidade)

        elif resposta_id == 'consultar_estoque':
            if is_usuario:
                return RoteamentoService._consultar_estoque_usuario(entidade)
            return RoteamentoService._consultar_estoque(entidade)

        elif resposta_id.startswith('aprovar_'):
            pedido_id = int(resposta_id.split('_')[1])
            return RoteamentoService._aprovar_pedido(pedido_id, entidade)

        elif resposta_id.startswith('rejeitar_'):
            pedido_id = int(resposta_id.split('_')[1])
            return RoteamentoService._rejeitar_pedido(pedido_id, entidade)

        elif resposta_id.startswith('aceitar_os_'):
            os_id = int(resposta_id.split('_')[2])
            return RoteamentoService._aceitar_os(os_id, entidade)

        elif resposta_id.startswith('abrir_os_'):
            equip_id = int(resposta_id.split('_')[2])
            return RoteamentoService._abrir_os_equipamento(entidade, equip_id)

        elif resposta_id.startswith('historico_'):
            equip_id = int(resposta_id.split('_')[1])
            return RoteamentoService._exibir_historico_equipamento(entidade, equip_id)

        elif resposta_id.startswith('dados_tecnicos_'):
            equip_id = int(resposta_id.split('_')[2])
            return RoteamentoService._exibir_dados_tecnicos(entidade, equip_id)

        elif resposta_id == 'voltar_menu':
            from app.extensions import db
            EstadoConversa.query.filter_by(telefone=telefone).delete()
            db.session.commit()
            if is_usuario:
                return RoteamentoService._exibir_menu_usuario(entidade)
            return RoteamentoService._exibir_menu_terceirizado(entidade)

        # Se não reconheceu o ID, retorna menu padrão
        if is_usuario:
            return RoteamentoService._exibir_menu_usuario(entidade)
        return RoteamentoService._exibir_menu_terceirizado(entidade)

    @staticmethod
    def _listar_minhas_os(terceirizado):
        """Lista OSs abertas do técnico/terceirizado."""
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
    def _listar_os_disponiveis(terceirizado):
        """Lista OSs disponíveis para o terceirizado."""
        from app.models.estoque_models import OrdemServico

        oss = OrdemServico.query.filter(
            OrdemServico.status == 'aberta',
            OrdemServico.tecnico_id.is_(None)
        ).order_by(OrdemServico.prioridade.desc()).limit(5).all()

        if not oss:
            return {'acao': 'responder', 'resposta': "📋 Não há OSs disponíveis no momento."}

        mensagem = "📋 *OSs DISPONÍVEIS*\n\n"
        for os in oss:
            mensagem += f"🆕 *#{os.numero_os}*\n"
            mensagem += f"   {os.titulo}\n"
            mensagem += f"   Prioridade: {os.prioridade.upper()}\n\n"

        mensagem += "_Para aceitar, acesse o sistema ou responda com o número da OS._"
        return {'acao': 'responder', 'resposta': mensagem}

    @staticmethod
    def _iniciar_fluxo_abrir_os(terceirizado):
        """Inicia fluxo conversacional para abrir OS."""
        from app.extensions import db

        estado = EstadoConversa(
            telefone=terceirizado.telefone,
            estado_atual='abrir_os_aguardando_equipamento',
            usuario_tipo='terceirizado',
            usuario_id=terceirizado.id
        )
        estado.set_contexto({'fluxo': 'abrir_os', 'etapa': 'aguardando_equipamento'})
        db.session.add(estado)
        db.session.commit()

        mensagem = "🛠️ *Abertura de OS*\n\nQual equipamento apresenta o problema?\n\n_Digite o nome ou código do equipamento_"
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
        from app.models.models import Usuario

        pedido = PedidoCompra.query.get(pedido_id)
        if not pedido:
            telefone = aprovador.telefone
            return {'acao': 'enviar_mensagem', 'telefone': telefone, 'mensagem': "❌ Pedido não encontrado."}

        if pedido.status != 'aguardando_aprovacao':
            telefone = aprovador.telefone
            return {'acao': 'enviar_mensagem', 'telefone': telefone, 'mensagem': f"⚠️ Pedido #{pedido_id} já foi processado."}

        aprovador_usuario = Usuario.query.filter_by(telefone=aprovador.telefone).first()

        pedido.status = 'aprovado'
        pedido.aprovador_id = aprovador_usuario.id if aprovador_usuario else None
        db.session.commit()

        # Notifica solicitante
        if pedido.solicitante and pedido.solicitante.telefone:
            notificacao = f"✅ *PEDIDO #{pedido.id} APROVADO*\n\nSeu pedido foi aprovado!"
            WhatsAppService.enviar_mensagem(telefone=pedido.solicitante.telefone, texto=notificacao, prioridade=1)

        return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': f"✅ Pedido #{pedido.id} aprovado!"}

    @staticmethod
    def _rejeitar_pedido(pedido_id, aprovador):
        """Rejeita pedido de compra e notifica solicitante."""
        from app.models.estoque_models import PedidoCompra
        from app.extensions import db
        from app.services.whatsapp_service import WhatsAppService
        from app.models.models import Usuario

        pedido = PedidoCompra.query.get(pedido_id)
        if not pedido:
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': "❌ Pedido não encontrado."}

        if pedido.status != 'aguardando_aprovacao':
            return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': f"⚠️ Pedido #{pedido_id} já foi processado."}

        aprovador_usuario = Usuario.query.filter_by(telefone=aprovador.telefone).first()

        pedido.status = 'rejeitado'
        pedido.aprovador_id = aprovador_usuario.id if aprovador_usuario else None
        db.session.commit()

        # Notifica solicitante
        if pedido.solicitante and pedido.solicitante.telefone:
            notificacao = f"❌ *PEDIDO #{pedido.id} REJEITADO*\n\nSeu pedido foi rejeitado."
            WhatsAppService.enviar_mensagem(telefone=pedido.solicitante.telefone, texto=notificacao, prioridade=1)

        return {'acao': 'enviar_mensagem', 'telefone': aprovador.telefone, 'mensagem': f"❌ Pedido #{pedido.id} rejeitado."}

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

    @staticmethod
    def _processar_confirmacao_os_nlp(terceirizado, texto):
        """Processa confirmação de criação de OS por voz."""
        from app.models.estoque_models import Equipamento, OrdemServico
        from app.models.models import Unidade, Usuario
        from app.extensions import db

        estado = EstadoConversa.query.filter_by(
            telefone=terceirizado.telefone
        ).filter(EstadoConversa.contexto.like('%confirmar_os_nlp%')).order_by(EstadoConversa.updated_at.desc()).first()

        if not estado:
            return "Não há solicitação de OS pendente."

        contexto = estado.get_contexto()
        dados = contexto.get('dados', {})

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
        equipamento = None
        if dados.get('equipamento'):
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
            usuario = Usuario.query.filter_by(telefone=terceirizado.telefone).first()
            if usuario:
                unidade_id = usuario.unidade_padrao_id

        # Criar OS
        numero_os = f"OS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        nova_os = OrdemServico(
            numero_os=numero_os,
            equipamento_id=equipamento.id if equipamento else None,
            unidade_id=unidade_id,
            tecnico_id=terceirizado.id,
            tipo_manutencao='corretiva',
            titulo=f"Problema em {dados.get('equipamento', 'equipamento não identificado')}",
            descricao_problema=dados.get('resumo', 'Criado por reconhecimento de voz'),
            prioridade=dados.get('urgencia', 'media'),
            origem_criacao='whatsapp_bot',
            status='aberta'
        )

        try:
            from app.services.os_service import OSService
            nova_os.prazo_conclusao = OSService.calcular_sla(nova_os.prioridade)
            nova_os.data_prevista = nova_os.prazo_conclusao
        except:
            pass

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

        EstadoService.criar_ou_atualizar_estado(
            telefone=terceirizado.telefone,
            contexto={
                'fluxo': 'contexto_equipamento',
                'equipamento_id': equip_id,
                'equipamento_nome': equipamento.nome
            }
        )

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
*Unidade:* {equipamento.unidade.nome if equipamento.unidade else 'N/A'}
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
        msg = f"📝 *Criar OS para {equipamento.nome if equipamento else 'Equipamento'}*\n\nDescreva o problema encontrado:"
        return {'acao': 'responder', 'resposta': msg}

    @staticmethod
    def _exibir_historico_equipamento(terceirizado, equipamento_id):
        """Exibe últimas 5 OSs do equipamento."""
        from app.models.estoque_models import Equipamento, OrdemServico

        equipamento = Equipamento.query.get(equipamento_id)
        oss = OrdemServico.query.filter_by(equipamento_id=equipamento_id).order_by(OrdemServico.data_abertura.desc()).limit(5).all()

        if not oss:
            msg = f"📋 *Histórico: {equipamento.nome if equipamento else 'Equipamento'}*\n\nNenhuma OS registrada."
        else:
            msg = f"📋 *Histórico: {equipamento.nome if equipamento else 'Equipamento'}*\n\nÚltimas OSs:\n\n"
            for os in oss:
                emoji = {'aberta': '🔴', 'em_andamento': '🟡', 'concluida': '🟢'}.get(os.status, '⚪')
                msg += f"{emoji} *{os.numero_os}*\n   {os.titulo}\n   Data: {os.data_abertura.strftime('%d/%m/%Y')}\n\n"

        return {'acao': 'responder', 'resposta': msg}

    @staticmethod
    def _exibir_dados_tecnicos(terceirizado, equipamento_id):
        """Exibe informações técnicas do equipamento."""
        from app.models.estoque_models import Equipamento

        equip = Equipamento.query.get(equipamento_id)
        if not equip:
            return {'acao': 'responder', 'resposta': "❌ Equipamento não encontrado."}

        msg = f"""⚙️ *Dados Técnicos*

*Nome:* {equip.nome}
*Código:* {equip.codigo or 'N/A'}
*Unidade:* {equip.unidade.nome if equip.unidade else 'N/A'}
*Status:* {equip.status.upper() if equip.status else 'N/A'}
*Data Aquisição:* {equip.data_aquisicao.strftime('%d/%m/%Y') if equip.data_aquisicao else 'N/A'}
*Custo:* R$ {equip.custo_aquisicao or 0:.2f}

*Descrição:*
{equip.descricao or 'Sem descrição.'}"""
        return {'acao': 'responder', 'resposta': msg}
