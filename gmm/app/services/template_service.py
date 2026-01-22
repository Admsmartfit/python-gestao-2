class TemplateService:
    """
    Renders message templates with provided variables.
    Supports all WhatsApp notification templates for the GMM system.
    """

    TEMPLATES = {
        # =============================================
        # TEMPLATES PARA TERCEIRIZADOS
        # =============================================

        'novo_chamado': """
🔧 *Novo Chamado GMM*

*Número:* {numero_chamado}
*Título:* {titulo}
*Prazo:* {prazo}

{descricao}

Para aceitar: {link_aceite}
Ou responda: SIM
        """,

        'lembrete': """
⏰ *Lembrete GMM*

*Chamado:* {numero_chamado}
*Prazo:* {prazo} (em 48h)

Tudo certo? 👍
        """,

        'cobranca': """
🚨 *Prazo Vencido*

*Chamado:* {numero_chamado}
Precisamos de atualização urgente!

Qual a previsão?
        """,

        'nova_os_terceirizado': """
🔧 *Nova Ordem de Serviço*

*OS:* #{numero_os}
*Cliente:* {cliente}
*Endereço:* {endereco}
*Prazo:* {prazo}

*Descrição:*
{descricao}

Responda *ACEITO* para confirmar ou *RECUSO* para recusar.
        """,

        'os_aceita_terceirizado': """
✅ *OS #{numero_os} Confirmada!*

Você aceitou a ordem de serviço.

*Cliente:* {cliente}
*Endereço:* {endereco}
*Prazo:* {prazo}

Use #STATUS para atualizar o andamento.
        """,

        'os_recusada_terceirizado': """
❌ *OS #{numero_os} Recusada*

Você recusou esta ordem de serviço.
O responsável será notificado.

Caso tenha recusado por engano, entre em contato com a administração.
        """,

        'peca_solicitada': """
📦 *Solicitação de Peça Registrada*

*OS:* #{numero_os}
*Item:* {item_nome} ({item_codigo})
*Quantidade:* {quantidade}

⏳ Aguardando separação pelo estoque.
Você será notificado quando estiver pronta para retirada.
        """,

        'peca_separada': """
✅ *Peça Pronta para Retirada*

*OS:* #{numero_os}
*Item:* {item_nome}
*Quantidade:* {quantidade}

📍 Retire no estoque.
Responda *#SEPARADO {item_codigo}* após retirar.
        """,

        'os_concluida_terceirizado': """
✅ *OS #{numero_os} Concluída!*

Obrigado pelo serviço realizado.

{observacao}

O cliente será notificado para avaliação.
        """,

        # =============================================
        # TEMPLATES PARA SOLICITANTES/RESPONSÁVEIS
        # =============================================

        'os_aceita_solicitante': """
✅ *OS #{numero_os} Aceita!*

O prestador *{prestador}* aceitou sua ordem de serviço.

*Previsão:* {prazo}

Você receberá atualizações sobre o andamento.
        """,

        'os_recusada_solicitante': """
❌ *OS #{numero_os} Recusada*

O prestador recusou a ordem de serviço.

*Motivo:* {motivo}

A OS será redistribuída automaticamente.
        """,

        'os_atualizacao_solicitante': """
📋 *Atualização OS #{numero_os}*

*Status:* {status}
*Prestador:* {prestador}

{observacao}
        """,

        'os_concluida_solicitante': """
✅ *OS #{numero_os} Concluída!*

O serviço foi finalizado por *{prestador}*.

{observacao}

Por favor, avalie o serviço de 1 a 5 estrelas.
        """,

        'os_agendada_solicitante': """
📅 *Agendamento Confirmado*

*OS:* #{numero_os}
*Prestador:* {prestador}
*Data:* {data_agendamento}

O prestador irá comparecer na data agendada.
        """,

        # =============================================
        # TEMPLATES PARA ESTOQUE/COMPRAS
        # =============================================

        'separacao_solicitada': """
📦 *Nova Solicitação de Separação*

*OS:* #{numero_os}
*Solicitante:* {solicitante}
*Item:* {item_nome} ({item_codigo})
*Quantidade:* {quantidade}

Após separar, responda *#SEPARADO {item_codigo}*
        """,

        'estoque_baixo': """
⚠️ *Alerta de Estoque Baixo*

*Item:* {item_nome} ({item_codigo})
*Quantidade Atual:* {quantidade_atual}
*Mínimo:* {quantidade_minima}

Considere fazer um pedido de reposição.
        """,

        'pedido_compra_aprovado': """
✅ *Pedido de Compra Aprovado*

*Pedido:* #{numero_pedido}
*Item:* {item_nome}
*Quantidade:* {quantidade}

Aprovado por: {aprovador}
        """,

        'pedido_compra_rejeitado': """
❌ *Pedido de Compra Rejeitado*

*Pedido:* #{numero_pedido}
*Item:* {item_nome}

*Motivo:* {motivo}

Rejeitado por: {aprovador}
        """,

        # =============================================
        # TEMPLATES PARA USUÁRIOS INTERNOS
        # =============================================

        'menu_admin': """
🏠 *Menu Principal - Administrador*

Selecione uma opção:

1️⃣ Ordens de Serviço
2️⃣ Estoque e Compras
3️⃣ Relatórios
4️⃣ Configurações

Ou digite o número da opção desejada.
        """,

        'menu_tecnico': """
🔧 *Menu Principal - Técnico*

Selecione uma opção:

1️⃣ Minhas OS
2️⃣ Consultar Estoque
3️⃣ Solicitar Peça

Ou digite o número da opção desejada.
        """,

        'menu_comum': """
📋 *Menu Principal*

Selecione uma opção:

1️⃣ Nova Solicitação
2️⃣ Minhas Solicitações
3️⃣ Falar com Suporte

Ou digite o número da opção desejada.
        """,

        # =============================================
        # TEMPLATES DE SISTEMA
        # =============================================

        'telefone_nao_cadastrado': """
⚠️ *Telefone não cadastrado*

Este número não está registrado no sistema GMM.

Se você é prestador de serviços ou funcionário, entre em contato com a administração para cadastro.
        """,

        'erro_generico': """
❌ *Erro no processamento*

Não foi possível processar sua solicitação.
Por favor, tente novamente ou entre em contato com o suporte.
        """,

        'ajuda': """
❓ *Comandos Disponíveis*

*Para Terceirizados:*
- *ACEITO* / *RECUSO* - Responder a uma OS
- *#STATUS* - Ver seus chamados ativos
- *#PECA [código] [qtd]* - Solicitar peça
- *#CONCLUIDO* - Finalizar OS atual
- *#AJUDA* - Ver esta mensagem

*Para Compras:*
- *#COMPRA [código] [qtd]* - Solicitar compra
- *#SEPARADO [código]* - Confirmar separação

Para falar com alguém, responda normalmente.
        """,

        'boas_vindas': """
👋 *Bem-vindo ao GMM!*

Sistema de Gestão de Manutenção

{mensagem_personalizada}

Digite *#AJUDA* para ver os comandos disponíveis.
        """,

        'avaliacao_solicitada': """
⭐ *Avalie o Serviço*

*OS:* #{numero_os}
*Prestador:* {prestador}

Como você avalia o serviço? (1 a 5)

1️⃣ Muito Ruim
2️⃣ Ruim
3️⃣ Regular
4️⃣ Bom
5️⃣ Excelente

Responda com o número da sua avaliação.
        """,

        'avaliacao_registrada': """
✅ *Avaliação Registrada*

Obrigado pelo feedback!

*Sua nota:* {'⭐' * nota}
{comentario}

Sua opinião é importante para melhorarmos nossos serviços.
        """
    }

    @staticmethod
    def render(template_name: str, **kwargs) -> str:
        """
        Renders a template by name using the provided keyword arguments.
        Returns the rendered string or the template name if not found.
        """
        template_text = TemplateService.TEMPLATES.get(template_name)
        if not template_text:
            return f"Template {template_name} not found."

        try:
            return template_text.strip().format(**kwargs)
        except KeyError as e:
            return f"Error: Missing variable {str(e)} for template {template_name}"
        except Exception as e:
            return f"Error rendering template: {str(e)}"

    @staticmethod
    def list_templates() -> list:
        """
        Returns a list of all available template names.
        """
        return list(TemplateService.TEMPLATES.keys())

    @staticmethod
    def get_template_vars(template_name: str) -> list:
        """
        Returns a list of variables required by a template.
        """
        import re
        template_text = TemplateService.TEMPLATES.get(template_name, "")
        # Find all {variable} patterns
        vars_found = re.findall(r'\{(\w+)\}', template_text)
        return list(set(vars_found))
