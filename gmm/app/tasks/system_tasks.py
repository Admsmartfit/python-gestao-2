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
    
    # OSs críticas (prioridade alta e não concluída)
    criticas = OrdemServico.query.filter(
        OrdemServico.status != 'concluida',
        OrdemServico.prioridade == 'alta'
    ).count()
    
    # 2. Monta mensagem
    resumo = f"🌅 *MORNING BRIEFING GMM*\n"
    resumo += f"Data: {hoje.strftime('%d/%m/%Y')}\n\n"
    resumo += f"📊 *Resumo Operacional:*\n"
    resumo += f"• OSs em aberto: {total_abertas}\n"
    resumo += f"• OSs prioritárias: {criticas}\n"
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
