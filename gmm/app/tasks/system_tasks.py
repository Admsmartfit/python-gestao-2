from datetime import datetime, timedelta
from celery import shared_task
from app.extensions import db
from app.models.terceirizados_models import ChamadoExterno, HistoricoNotificacao
from app.tasks.whatsapp_tasks import enviar_whatsapp_task

@shared_task
def lembretes_automaticos_task():
    """
    Periodic task to check for upcoming deadlines and send WhatsApp reminders.
    """
    hoje = datetime.utcnow()
    limite = hoje + timedelta(days=2)
    
    # Chamados 'aguardando' ou 'em_andamento' próximos do prazo
    chamados = ChamadoExterno.query.filter(
        ChamadoExterno.status.notin_(['concluido', 'cancelado']),
        ChamadoExterno.prazo_combinado <= limite,
        ChamadoExterno.prazo_combinado >= hoje
    ).all()
    
    for ch in chamados:
        msg = f"🔧 Lembrete GMM\n\nChamado: {ch.numero_chamado} vence em breve.\nPrazo: {ch.prazo_combinado.strftime('%d/%m %H:%M')}"
        
        # Cria registro de notificação
        notif = HistoricoNotificacao(
            chamado_id=ch.id,
            tipo='lembrete',
            destinatario=ch.terceirizado.telefone,
            mensagem=msg,
            prioridade=1 # Alta prioridade para lembretes
        )
        db.session.add(notif)
        db.session.commit()
        
        # Dispara envio assíncrono (nova versão que usa apenas o ID)
        enviar_whatsapp_task.delay(notif.id)

@shared_task
def enviar_morning_briefing_task():
    """
    Morning Briefing (RF-016): Resumo diário às 08:00.
    Envia resumo das OSs e pendências para administradores e gerentes.
    """
    from app.models.estoque_models import OrdemServico, PedidoCompra
    from app.models.models import Usuario
    from app.services.whatsapp_service import WhatsAppService
    
    hoje = datetime.utcnow().date()
    
    # 1. Coleta dados
    total_abertas = OrdemServico.query.filter(OrdemServico.status != 'concluida').count()
    compras_pendentes = PedidoCompra.query.filter_by(status='solicitado').count()
    
    # OSs críticas (prioridade alta/urgente e não concluída)
    criticas = OrdemServico.query.filter(
        OrdemServico.status != 'concluida',
        OrdemServico.prioridade.in_(['alta', 'urgente'])
    ).count()

    # Peças críticas
    from app.models.estoque_models import Estoque
    itens_criticos = Estoque.query.filter(Estoque.quantidade_atual <= Estoque.quantidade_minima).count()

    # Concluídas ontem
    ontem = hoje - timedelta(days=1)
    concluidas_ontem = OrdemServico.query.filter(
        OrdemServico.status == 'concluida',
        OrdemServico.data_conclusao >= ontem
    ).count()
    
    # 2. Monta mensagem
    resumo = f"🌅 *MORNING BRIEFING GMM*\n"
    resumo += f"Data: {hoje.strftime('%d/%m/%Y')}\n\n"
    resumo += f"📊 *Resumo Operacional:*\n"
    resumo += f"• OSs em aberto: {total_abertas}\n"
    resumo += f"• OSs prioritárias: {criticas}\n"
    resumo += f"• OSs concluídas ontem: {concluidas_ontem}\n"
    resumo += f"• Itens abaixo do estoque mínimo: {itens_criticos}\n"
    resumo += f"• Pedidos de compra pendentes: {compras_pendentes}\n\n"
    resumo += "🛠️ Tenha uma excelente jornada de trabalho!"
    
    # 3. Dispara para gerentes
    gerentes = Usuario.query.filter(
        Usuario.tipo.in_(['admin', 'gerente']), 
        Usuario.telefone.isnot(None),
        Usuario.telefone != ''
    ).all()
    
    for g in gerentes:
        WhatsAppService.enviar_mensagem(g.telefone, resumo, prioridade=1)
        
    return {"status": "success", "notified": len(gerentes)}

@shared_task
def verificar_estoque_critico_task():
    """US-009: Alerta proativo de estoque crítico."""
    from app.models.estoque_models import Estoque
    from app.models.models import Usuario
    from app.services.whatsapp_service import WhatsAppService

    itens = Estoque.query.filter(Estoque.quantidade_atual <= Estoque.quantidade_minima).all()
    
    if not itens:
        return {"status": "no_items"}

    msg = "⚠️ *ALERTA: ESTOQUE CRÍTICO*\n\nOs seguintes itens atingiram o nível mínimo:\n\n"
    for item in itens:
        msg += f"• *{item.nome}*: {item.quantidade_atual} {item.unidade_medida} (Mín: {item.quantidade_minima})\n"
    
    msg += "\nPor favor, providencie a reposição."

    # Notifica compradores e admins
    destinatarios = Usuario.query.filter(
        Usuario.tipo.in_(['admin', 'comprador', 'gerente']),
        Usuario.telefone != ''
    ).all()

    for d in destinatarios:
        WhatsAppService.enviar_mensagem(d.telefone, msg, prioridade=1)

    return {"status": "success", "items_alerted": len(itens)}

@shared_task
def detectar_anomalias_equipamentos_task():
    """US-008: Alertas preditivos de equipamentos."""
    from app.models.estoque_models import Equipamento, OrdemServico
    from app.models.models import Usuario
    from app.services.whatsapp_service import WhatsAppService

    # RF-017: Equipamento sem manutenção há mais de 30 dias
    limite = datetime.utcnow() - timedelta(days=30)
    
    anomalias = []
    equipamentos = Equipamento.query.filter_by(ativo=True).all()

    for eq in equipamentos:
        ultima_os = OrdemServico.query.filter_by(equipamento_id=eq.id, status='concluida').order_by(OrdemServico.data_conclusao.desc()).first()
        
        if not ultima_os or ultima_os.data_conclusao < limite:
            anomalias.append(eq)

    if not anomalias:
        return {"status": "no_anomalies"}

    msg = "🔍 *ANALISADOR PREDITIVO: ALERTAS*\n\nEquipamentos sem manutenção recente (>30 dias):\n\n"
    for eq in anomalias:
        msg += f"• *{eq.nome}* ({eq.unidade.nome})\n"
    
    msg += "\nRecomenda-se agendar uma revisão preventiva."

    # Notifica gestores
    gestores = Usuario.query.filter(Usuario.tipo.in_(['admin', 'gerente'])).all()
    for g in gestores:
        if g.telefone:
            WhatsAppService.enviar_mensagem(g.telefone, msg)

    return {"status": "success", "anomalies_found": len(anomalias)}

@shared_task
def executar_manutencoes_preventivas_task():
    """
    Verifica planos de manutenção preventiva vencidos e cria OSs automaticamente.
    Deve ser executada diariamente.
    """
    from app.models.estoque_models import PlanoManutencao, Equipamento, OrdemServico
    from app.models.models import Usuario
    from app.services.whatsapp_service import WhatsAppService

    hoje = datetime.utcnow()
    planos_ativos = PlanoManutencao.query.filter_by(ativo=True).all()

    oss_criadas = []
    planos_executados = []

    for plano in planos_ativos:
        # Verificar se o plano está vencido
        if plano.ultima_execucao:
            proxima_execucao = plano.ultima_execucao + timedelta(days=plano.frequencia_dias)
            if proxima_execucao > hoje:
                continue  # Ainda não venceu
        # Se nunca foi executado, executar agora

        # Determinar equipamentos afetados
        equipamentos_afetados = []
        if plano.equipamento_id:
            equipamentos_afetados = [plano.equipamento]
        elif plano.categoria_equipamento:
            equipamentos_afetados = Equipamento.query.filter_by(
                categoria=plano.categoria_equipamento,
                ativo=True
            ).all()

        if not equipamentos_afetados:
            continue

        # Criar OSs para cada equipamento
        for equipamento in equipamentos_afetados:
            # Buscar um técnico responsável (admin ou gerente)
            tecnico = Usuario.query.filter(
                Usuario.tipo.in_(['admin', 'gerente', 'tecnico'])
            ).first()

            if not tecnico:
                continue

            os = OrdemServico(
                tipo='preventiva',
                prioridade='media',
                status='aberta',
                equipamento_id=equipamento.id,
                unidade_id=equipamento.unidade_id,
                descricao_problema=f"[MANUTENÇÃO PREVENTIVA] {plano.nome}",
                observacoes=plano.descricao_procedimento,
                tecnico_id=tecnico.id,
                data_abertura=hoje
            )

            db.session.add(os)
            oss_criadas.append({
                'plano': plano.nome,
                'equipamento': equipamento.nome,
                'unidade': equipamento.unidade.nome if equipamento.unidade else 'N/A'
            })

        # Atualizar última execução
        plano.ultima_execucao = hoje
        planos_executados.append(plano.nome)

    db.session.commit()

    # Notificar gestores se houver OSs criadas
    if oss_criadas:
        msg = f"🔧 *MANUTENÇÕES PREVENTIVAS AGENDADAS*\n\n"
        msg += f"Total de OSs criadas: {len(oss_criadas)}\n"
        msg += f"Planos executados: {len(planos_executados)}\n\n"
        msg += "*Planos:*\n"
        for plano in set([os['plano'] for os in oss_criadas]):
            count = len([os for os in oss_criadas if os['plano'] == plano])
            msg += f"• {plano}: {count} OS(s)\n"

        # Notificar gestores
        gestores = Usuario.query.filter(
            Usuario.tipo.in_(['admin', 'gerente']),
            Usuario.telefone.isnot(None)
        ).all()

        for g in gestores:
            WhatsAppService.enviar_mensagem(g.telefone, msg, prioridade=1)

    return {
        "status": "success",
        "oss_criadas": len(oss_criadas),
        "planos_executados": planos_executados
    }
