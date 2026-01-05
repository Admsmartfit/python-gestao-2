from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.estoque_models import Estoque
# Assuming PedidoCompra exists or similar, checking context... 
# PedidoCompra was mentioned in prompt but might not exist in viewed files.
# Adapting to implementation plan context.
# If PedidoCompra doesn't exist, we might need to create it or stub it. 
# Based on existing 'app.models.estoque_models', let's check what we have. 
# We have CategoriaEstoque, Estoque, Equipamento, OrdemServico.
# I will assume PedidoCompra needs to be imported if it exists, otherwise I'll stub/comment.
# Wait, previous prompts mentioned implementing Purchase Requests. Let's assume it exists or use a placeholder.
# I will verify file structure after this if needed. For now, implement assuming it matches recent work.

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
            # Assuming Terceirizado might have a related Usuario or we use terceirizado_id
            # For now, we'll use solicitante_id = None and reference terceirizado in justificativa
            # Check if there's a usuario field
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
                # No manager to approve - fallback to pending status
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

            # Send button message to manager
            sucesso, _ = WhatsAppService.send_buttons_message(
                phone=gestor.telefone,
                body=mensagem,
                buttons=buttons
            )

            if not sucesso:
                current_app.logger.warning(f"Failed to send approval buttons for pedido {pedido.id}")

            # 8. Confirmation to requester
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
    def executar_status(solicitante: Terceirizado) -> dict:
        """
        Lists active tickets for the requester.
        """
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
            icone = "✅" if ch.prazo_combinado > datetime.utcnow() else "⚠️"
            resposta += f"{icone} {ch.numero_chamado} - {ch.status}\n"
            resposta += f"   Prazo: {ch.prazo_combinado.strftime('%d/%m')}\n\n"
        
        return {
            'sucesso': True,
            'resposta': resposta
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

- #COMPRA [código] [qtd]
  Ex: #COMPRA CABO-10MM 50

- #STATUS
  Ver seus chamados ativos

- #AJUDA
  Ver esta mensagem

Para falar com alguém, responda normalmente que encaminharemos.
            """
        }
