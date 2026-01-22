from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.estoque_models import Estoque
from app.models.terceirizados_models import Terceirizado, ChamadoExterno

class ComandoExecutores:
    """
    Executes business logic for WhatsApp commands.
    """

    @staticmethod
    def executar_compra(params: dict, solicitante: Terceirizado) -> dict:
        """
        Creates a purchase request with manager approval flow.
        Generates secure token and sends approval buttons via WhatsApp.
        """
        try:
            import secrets
            from datetime import timedelta
            from app.models.estoque_models import PedidoCompra
            from app.models.models import Usuario
            from app.services.whatsapp_service import WhatsAppService

            item_codigo = params['item']
            quantidade = int(params['quantidade'])

            # 1. Find Item
            item = Estoque.query.filter_by(codigo=item_codigo).first()
            if not item:
                return {
                    'sucesso': False,
                    'resposta': f"❌ Item {item_codigo} não encontrado no catálogo."
                }

            # 2. Validate quantity
            if quantidade <= 0 or quantidade > 9999:
                return {
                    'sucesso': False,
                    'resposta': "❌ Quantidade inválida. Use um valor entre 1 e 9999."
                }

            # 3. Get requester's usuario_id from terceirizado
            solicitante_usuario_id = getattr(solicitante, 'usuario_id', None)

            # 4. Generate approval token (valid for 48h)
            token = secrets.token_urlsafe(32)
            token_expira = datetime.utcnow() + timedelta(hours=48)

            # 5. Create Purchase Order
            pedido = PedidoCompra(
                estoque_id=item.id,
                quantidade=quantidade,
                status='aguardando_aprovacao',
                solicitante_id=solicitante_usuario_id,
                token_aprovacao=token,
                token_expira_em=token_expira,
                justificativa=f"Solicitado por {solicitante.nome} via WhatsApp"
            )
            db.session.add(pedido)
            db.session.commit()

            # 6. Find manager to notify (tipo='admin' or gestor)
            gestor = Usuario.query.filter_by(tipo='admin', ativo=True).first()

            if not gestor or not gestor.telefone:
                return {
                    'sucesso': True,
                    'resposta': f"✅ Pedido #{pedido.id} criado!\n\n*Item:* {item.nome}\n*Qtd:* {quantidade}\n\n⏳ Aguardando aprovação do gestor."
                }

            # 7. Build approval message with buttons
            mensagem = f"""📦 *NOVA SOLICITAÇÃO DE COMPRA*

*Pedido:* #{pedido.id}
*Solicitante:* {solicitante.nome}
*Item:* {item.nome} ({item.codigo})
*Quantidade:* {quantidade} {item.unidade_medida}
*Valor Estimado:* R$ {float(item.valor_unitario or 0) * quantidade:.2f}

Clique para decidir:"""

            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": f"aprovar_{pedido.id}",
                        "title": "✅ Aprovar"
                    }
                },
                {
                    "type": "reply",
                    "reply": {
                        "id": f"rejeitar_{pedido.id}",
                        "title": "❌ Rejeitar"
                    }
                }
            ]

            sucesso, _ = WhatsAppService.send_buttons_message(
                phone=gestor.telefone,
                body=mensagem,
                buttons=buttons
            )

            if not sucesso:
                current_app.logger.warning(f"Failed to send approval buttons for pedido {pedido.id}")

            return {
                'sucesso': True,
                'resposta': f"✅ Pedido #{pedido.id} criado com sucesso!\n\n*Item:* {item.nome}\n*Qtd:* {quantidade}\n\n⏳ Aguardando aprovação do gestor.\n\nVocê será notificado em breve."
            }

        except KeyError as e:
            current_app.logger.error(f"Missing parameter in purchase: {e}")
            return {
                'sucesso': False,
                'resposta': "❌ Comando incompleto. Use: #COMPRA [código] [quantidade]"
            }
        except Exception as e:
            current_app.logger.error(f"Error executing purchase: {e}", exc_info=True)
            db.session.rollback()
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao processar pedido. Tente novamente."
            }

    @staticmethod
    def executar_peca(params: dict, solicitante: Terceirizado, ordem_servico_id: int = None) -> dict:
        """
        Creates a part request for an OS.
        """
        try:
            from app.models.estoque_models import SolicitacaoPeca, OrdemServico
            from app.models.models import Usuario
            from app.services.whatsapp_service import WhatsAppService

            item_codigo = params['item']
            quantidade = int(params['quantidade'])

            # Find Item
            item = Estoque.query.filter_by(codigo=item_codigo).first()
            if not item:
                return {
                    'sucesso': False,
                    'resposta': f"❌ Item {item_codigo} não encontrado no estoque."
                }

            # Validate quantity
            if quantidade <= 0 or quantidade > 999:
                return {
                    'sucesso': False,
                    'resposta': "❌ Quantidade inválida. Use um valor entre 1 e 999."
                }

            # Check stock availability
            if item.quantidade < quantidade:
                return {
                    'sucesso': False,
                    'resposta': f"⚠️ Estoque insuficiente.\n\n*Item:* {item.nome}\n*Disponível:* {item.quantidade}\n*Solicitado:* {quantidade}"
                }

            # Find active OS for this terceirizado
            os = None
            if ordem_servico_id:
                os = OrdemServico.query.get(ordem_servico_id)
            else:
                # Try to find active OS
                chamado = ChamadoExterno.query.filter_by(
                    terceirizado_id=solicitante.id,
                    status='em_andamento'
                ).first()
                if chamado:
                    os = OrdemServico.query.filter_by(chamado_externo_id=chamado.id).first()

            if not os:
                return {
                    'sucesso': False,
                    'resposta': "❌ Nenhuma OS ativa encontrada.\n\nVocê precisa ter uma OS em andamento para solicitar peças."
                }

            # Create part request
            solicitacao = SolicitacaoPeca(
                ordem_servico_id=os.id,
                estoque_id=item.id,
                quantidade=quantidade,
                status='aguardando_separacao',
                solicitante_id=solicitante.id
            )
            db.session.add(solicitacao)
            db.session.commit()

            # Notify stock team
            comprador = Usuario.query.filter_by(tipo='admin', ativo=True).first()
            if comprador and comprador.telefone:
                mensagem = f"""📦 *Nova Solicitação de Peça*

*OS:* #{os.id}
*Solicitante:* {solicitante.nome}
*Item:* {item.nome} ({item.codigo})
*Quantidade:* {quantidade}

Após separar, responda *#SEPARADO {item.codigo}*"""

                WhatsAppService.send_message(comprador.telefone, mensagem)

            return {
                'sucesso': True,
                'resposta': f"✅ Peça solicitada!\n\n*OS:* #{os.id}\n*Item:* {item.nome}\n*Qtd:* {quantidade}\n\n⏳ Aguardando separação pelo estoque."
            }

        except Exception as e:
            current_app.logger.error(f"Error requesting part: {e}", exc_info=True)
            db.session.rollback()
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao solicitar peça. Tente novamente."
            }

    @staticmethod
    def executar_status(solicitante: Terceirizado = None, params: dict = None) -> dict:
        """
        Lists active tickets for the requester or updates OS status.
        """
        # If params has novo_status, update OS status
        if params and params.get('novo_status'):
            return ComandoExecutores._atualizar_status_os(solicitante, params['novo_status'])

        # Otherwise, list active tickets
        if not solicitante:
            return {
                'sucesso': False,
                'resposta': "❌ Não foi possível identificar o solicitante."
            }

        chamados = ChamadoExterno.query.filter_by(
            terceirizado_id=solicitante.id
        ).filter(ChamadoExterno.status.in_(['aguardando', 'aceito', 'em_andamento'])).all()

        if not chamados:
            return {
                'sucesso': True,
                'resposta': "📋 Você não tem chamados ativos no momento."
            }

        resposta = "📋 *Seus Chamados Ativos*\n\n"

        for ch in chamados:
            icone = "✅" if ch.prazo_combinado and ch.prazo_combinado > datetime.utcnow() else "⚠️"
            prazo_str = ch.prazo_combinado.strftime('%d/%m') if ch.prazo_combinado else "Sem prazo"
            resposta += f"{icone} {ch.numero_chamado} - {ch.status}\n"
            resposta += f"   Prazo: {prazo_str}\n\n"

        return {
            'sucesso': True,
            'resposta': resposta
        }

    @staticmethod
    def _atualizar_status_os(solicitante: Terceirizado, novo_status: str) -> dict:
        """
        Updates the status of the active OS for the terceirizado.
        """
        try:
            from app.services.whatsapp_service import WhatsAppService
            from app.models.models import Usuario

            # Map command status to system status
            status_map = {
                'ANDAMENTO': 'em_andamento',
                'EM_ANDAMENTO': 'em_andamento',
                'CONCLUIDO': 'concluido',
                'PAUSADO': 'pausado'
            }

            status_sistema = status_map.get(novo_status.upper())
            if not status_sistema:
                return {
                    'sucesso': False,
                    'resposta': "❌ Status inválido.\n\nUse: #STATUS ANDAMENTO, #STATUS CONCLUIDO ou #STATUS PAUSADO"
                }

            # Find active chamado
            chamado = ChamadoExterno.query.filter_by(
                terceirizado_id=solicitante.id
            ).filter(ChamadoExterno.status.in_(['aceito', 'em_andamento'])).first()

            if not chamado:
                return {
                    'sucesso': False,
                    'resposta': "❌ Nenhum chamado ativo encontrado para atualizar."
                }

            # Update status
            status_anterior = chamado.status
            chamado.status = status_sistema
            chamado.atualizado_em = datetime.utcnow()
            db.session.commit()

            # Notify requester
            if chamado.solicitante_id:
                solicitante_usuario = Usuario.query.get(chamado.solicitante_id)
                if solicitante_usuario and solicitante_usuario.telefone:
                    mensagem = f"""📋 *Atualização de Chamado*

*Chamado:* {chamado.numero_chamado}
*Prestador:* {solicitante.nome}
*Status:* {status_anterior} → {status_sistema}

Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
                    WhatsAppService.send_message(solicitante_usuario.telefone, mensagem)

            return {
                'sucesso': True,
                'resposta': f"✅ Status atualizado!\n\n*Chamado:* {chamado.numero_chamado}\n*Novo Status:* {status_sistema}"
            }

        except Exception as e:
            current_app.logger.error(f"Error updating OS status: {e}", exc_info=True)
            db.session.rollback()
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao atualizar status. Tente novamente."
            }

    @staticmethod
    def executar_separado(params: dict, usuario) -> dict:
        """
        Confirms part separation by stock team.
        """
        try:
            from app.models.estoque_models import SolicitacaoPeca
            from app.services.whatsapp_service import WhatsAppService

            item_codigo = params['item']

            # Find pending separation request for this item
            item = Estoque.query.filter_by(codigo=item_codigo).first()
            if not item:
                return {
                    'sucesso': False,
                    'resposta': f"❌ Item {item_codigo} não encontrado."
                }

            solicitacao = SolicitacaoPeca.query.filter_by(
                estoque_id=item.id,
                status='aguardando_separacao'
            ).first()

            if not solicitacao:
                return {
                    'sucesso': False,
                    'resposta': f"❌ Nenhuma solicitação pendente para {item.nome}."
                }

            # Update status
            solicitacao.status = 'separado'
            solicitacao.separado_em = datetime.utcnow()
            solicitacao.separado_por_id = getattr(usuario, 'id', None)

            # Deduct from stock
            item.quantidade -= solicitacao.quantidade
            db.session.commit()

            # Notify terceirizado
            terceirizado = Terceirizado.query.get(solicitacao.solicitante_id)
            if terceirizado and terceirizado.telefone:
                mensagem = f"""✅ *Peça Separada!*

*Item:* {item.nome} ({item.codigo})
*Quantidade:* {solicitacao.quantidade}

📍 Retire no estoque."""
                WhatsAppService.send_message(terceirizado.telefone, mensagem)

            return {
                'sucesso': True,
                'resposta': f"✅ Separação confirmada!\n\n*Item:* {item.nome}\n*Qtd:* {solicitacao.quantidade}\n\nO solicitante foi notificado."
            }

        except Exception as e:
            current_app.logger.error(f"Error confirming separation: {e}", exc_info=True)
            db.session.rollback()
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao confirmar separação. Tente novamente."
            }

    @staticmethod
    def executar_concluido(params: dict, solicitante: Terceirizado) -> dict:
        """
        Concludes the active OS for the terceirizado.
        """
        try:
            from app.services.whatsapp_service import WhatsAppService
            from app.models.models import Usuario

            observacao = params.get('observacao', '')

            # Find active chamado
            chamado = ChamadoExterno.query.filter_by(
                terceirizado_id=solicitante.id
            ).filter(ChamadoExterno.status.in_(['aceito', 'em_andamento'])).first()

            if not chamado:
                return {
                    'sucesso': False,
                    'resposta': "❌ Nenhum chamado ativo para concluir."
                }

            # Update status
            chamado.status = 'concluido'
            chamado.concluido_em = datetime.utcnow()
            chamado.observacao_conclusao = observacao
            db.session.commit()

            # Notify requester
            if chamado.solicitante_id:
                solicitante_usuario = Usuario.query.get(chamado.solicitante_id)
                if solicitante_usuario and solicitante_usuario.telefone:
                    mensagem = f"""✅ *Serviço Concluído!*

*Chamado:* {chamado.numero_chamado}
*Prestador:* {solicitante.nome}

{f'*Observação:* {observacao}' if observacao else ''}

Por favor, avalie o serviço de 1 a 5 estrelas."""
                    WhatsAppService.send_message(solicitante_usuario.telefone, mensagem)

            return {
                'sucesso': True,
                'resposta': f"✅ Chamado {chamado.numero_chamado} concluído!\n\nObrigado pelo serviço."
            }

        except Exception as e:
            current_app.logger.error(f"Error concluding OS: {e}", exc_info=True)
            db.session.rollback()
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao concluir chamado. Tente novamente."
            }

    @staticmethod
    def executar_agenda(params: dict, solicitante: Terceirizado) -> dict:
        """
        Schedules the OS for a specific date.
        """
        try:
            from app.services.whatsapp_service import WhatsAppService
            from app.models.models import Usuario
            from app.services.comando_parser import ComandoParser

            data_str = params.get('data', '')
            data_parsed = ComandoParser.extract_date(data_str)

            if not data_parsed:
                return {
                    'sucesso': False,
                    'resposta': "❌ Data inválida.\n\nUse: #AGENDA DD/MM ou #AGENDA DD/MM/AAAA"
                }

            # Find active chamado
            chamado = ChamadoExterno.query.filter_by(
                terceirizado_id=solicitante.id
            ).filter(ChamadoExterno.status.in_(['aceito', 'em_andamento'])).first()

            if not chamado:
                return {
                    'sucesso': False,
                    'resposta': "❌ Nenhum chamado ativo para agendar."
                }

            # Create scheduled date
            data_agendamento = datetime(
                data_parsed['ano'],
                data_parsed['mes'],
                data_parsed['dia']
            )

            # Validate date is in the future
            if data_agendamento.date() < datetime.now().date():
                return {
                    'sucesso': False,
                    'resposta': "❌ A data deve ser futura."
                }

            # Update chamado
            chamado.data_agendamento = data_agendamento
            chamado.status = 'agendado'
            db.session.commit()

            # Notify requester
            if chamado.solicitante_id:
                solicitante_usuario = Usuario.query.get(chamado.solicitante_id)
                if solicitante_usuario and solicitante_usuario.telefone:
                    mensagem = f"""📅 *Agendamento Confirmado*

*Chamado:* {chamado.numero_chamado}
*Prestador:* {solicitante.nome}
*Data:* {data_agendamento.strftime('%d/%m/%Y')}

O prestador comparecerá na data agendada."""
                    WhatsAppService.send_message(solicitante_usuario.telefone, mensagem)

            return {
                'sucesso': True,
                'resposta': f"✅ Agendamento confirmado!\n\n*Chamado:* {chamado.numero_chamado}\n*Data:* {data_agendamento.strftime('%d/%m/%Y')}"
            }

        except ValueError as e:
            return {
                'sucesso': False,
                'resposta': f"❌ Data inválida: {str(e)}"
            }
        except Exception as e:
            current_app.logger.error(f"Error scheduling OS: {e}", exc_info=True)
            db.session.rollback()
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao agendar. Tente novamente."
            }

    @staticmethod
    def executar_ajuda() -> dict:
        """
        Returns the help menu.
        """
        return {
            'sucesso': True,
            'resposta': """
❓ *Comandos Disponíveis*

*Para Terceirizados:*
- *ACEITO* / *RECUSO* - Responder a uma OS
- *#STATUS* - Ver seus chamados ativos
- *#STATUS ANDAMENTO* - Marcar como em andamento
- *#STATUS PAUSADO* - Pausar OS
- *#PECA [código] [qtd]* - Solicitar peça
- *#CONCLUIDO* - Finalizar OS atual
- *#AGENDA DD/MM* - Agendar visita
- *#AJUDA* - Ver esta mensagem

*Para Estoque:*
- *#SEPARADO [código]* - Confirmar separação

*Para Compras:*
- *#COMPRA [código] [qtd]* - Solicitar compra

Para falar com alguém, responda normalmente.
            """
        }

    @staticmethod
    def executar_menu(usuario_tipo: str = 'comum') -> dict:
        """
        Returns the menu based on user type.
        """
        menus = {
            'admin': """
🏠 *Menu Principal - Administrador*

1️⃣ Ordens de Serviço
2️⃣ Estoque e Compras
3️⃣ Relatórios
4️⃣ Configurações

Ou digite o número da opção desejada.
            """,
            'tecnico': """
🔧 *Menu Principal - Técnico*

1️⃣ Minhas OS
2️⃣ Consultar Estoque
3️⃣ Solicitar Peça

Ou digite o número da opção desejada.
            """,
            'comum': """
📋 *Menu Principal*

1️⃣ Nova Solicitação
2️⃣ Minhas Solicitações
3️⃣ Falar com Suporte

Ou digite o número da opção desejada.
            """,
            'terceirizado': """
🔧 *Menu Principal - Prestador*

1️⃣ Meus Chamados
2️⃣ Solicitar Peça
3️⃣ Atualizar Status
4️⃣ Ajuda

Ou digite o número da opção desejada.
            """
        }

        return {
            'sucesso': True,
            'resposta': menus.get(usuario_tipo, menus['comum'])
        }

    @staticmethod
    def executar_cancelar() -> dict:
        """
        Cancels the current operation.
        """
        return {
            'sucesso': True,
            'resposta': "✅ Operação cancelada.\n\nDigite *#MENU* para ver as opções ou *#AJUDA* para ver os comandos."
        }
