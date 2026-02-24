import hmac
import hashlib
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.terceirizados_models import HistoricoNotificacao
from app.models.estoque_models import ComunicacaoFornecedor, Fornecedor

bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)


def vincular_whatsapp_fornecedor(remetente, texto):
    """
    Tenta vincular uma mensagem WhatsApp recebida a um ComunicacaoFornecedor.
    Busca o fornecedor pelo telefone e vincula a comunicacao pendente mais recente.
    """
    try:
        from app.services.whatsapp_service import WhatsAppService
        try:
            telefone_normalizado = WhatsAppService.normalizar_telefone(remetente)
        except Exception:
            telefone_normalizado = None

        # Buscar fornecedor pelo telefone ou whatsapp (ultimos 10 digitos)
        digitos = remetente[-10:] if remetente else None
        if not digitos:
            return

        filtros = [
            Fornecedor.telefone.contains(digitos),
            Fornecedor.whatsapp.contains(digitos),
        ]
        if telefone_normalizado:
            digitos_norm = telefone_normalizado[-10:]
            filtros.append(Fornecedor.telefone.contains(digitos_norm))
            filtros.append(Fornecedor.whatsapp.contains(digitos_norm))

        fornecedor = Fornecedor.query.filter(
            db.or_(*filtros),
            Fornecedor.ativo == True
        ).first()

        if not fornecedor:
            logger.debug(f"Nenhum fornecedor encontrado para telefone {remetente}")
            return

        logger.info(f"Fornecedor encontrado: {fornecedor.nome} (ID {fornecedor.id}) para telefone {remetente}")

        # Buscar comunicacao enviada mais recente para este fornecedor (ultimos 30 dias)
        from datetime import timedelta
        limite = datetime.utcnow() - timedelta(days=30)

        # Buscar qualquer comunicacao enviada pendente (whatsapp ou email) - fornecedor pode responder por outro canal
        comunicacao_pendente = ComunicacaoFornecedor.query.filter(
            ComunicacaoFornecedor.fornecedor_id == fornecedor.id,
            ComunicacaoFornecedor.direcao == 'enviado',
            ComunicacaoFornecedor.status.in_(['enviado', 'entregue', 'pendente']),
            ComunicacaoFornecedor.data_envio >= limite
        ).order_by(ComunicacaoFornecedor.data_envio.desc()).first()

        if comunicacao_pendente:
            # Atualizar a comunicacao original com a resposta
            comunicacao_pendente.resposta = texto[:2000]
            comunicacao_pendente.status = 'respondido'
            comunicacao_pendente.data_resposta = datetime.utcnow()
            db.session.add(comunicacao_pendente)
            logger.info(f"Comunicacao #{comunicacao_pendente.id} atualizada com resposta do fornecedor {fornecedor.nome} (Pedido #{comunicacao_pendente.pedido_compra_id})")

            # Criar registro de recebimento no historico
            com_recebida = ComunicacaoFornecedor(
                pedido_compra_id=comunicacao_pendente.pedido_compra_id,
                fornecedor_id=fornecedor.id,
                tipo_comunicacao='whatsapp',
                direcao='recebido',
                mensagem=texto[:2000],
                status='respondido',
                data_envio=datetime.utcnow()
            )
            db.session.add(com_recebida)
            db.session.commit()
            logger.info(f"[COMPRAS] Resposta WhatsApp salva - Pedido #{comunicacao_pendente.pedido_compra_id} - Fornecedor: {fornecedor.nome}")
        else:
            # Sem comunicacao pendente recente - tentar vincular ao pedido mais recente do fornecedor
            from app.models.estoque_models import PedidoCompra
            pedido_recente = PedidoCompra.query.filter(
                PedidoCompra.fornecedor_id == fornecedor.id
            ).order_by(PedidoCompra.data_solicitacao.desc()).first()

            if pedido_recente:
                nova_com = ComunicacaoFornecedor(
                    pedido_compra_id=pedido_recente.id,
                    fornecedor_id=fornecedor.id,
                    tipo_comunicacao='whatsapp',
                    direcao='recebido',
                    mensagem=texto[:2000],
                    status='pendente',
                    data_envio=datetime.utcnow()
                )
                db.session.add(nova_com)
                db.session.commit()
                logger.info(f"[COMPRAS] Mensagem espontanea de {fornecedor.nome} vinculada ao Pedido #{pedido_recente.id}")
            else:
                logger.info(f"[COMPRAS] Nenhum pedido encontrado para fornecedor {fornecedor.nome} - mensagem apenas no HistoricoNotificacao")

    except Exception as e:
        logger.error(f"Erro ao vincular WhatsApp ao fornecedor: {e}", exc_info=True)


def validar_webhook(req):
    """
    Valida origem do webhook.
    - Se WEBHOOK_SECRET configurado: valida HMAC
    - Se nao configurado: aceita TODAS as requisicoes (dev/ngrok/MegaAPI)
    """
    secret = current_app.config.get('WEBHOOK_SECRET')

    # Se nao tem secret configurado, aceitar tudo (modo dev/ngrok)
    if not secret:
        logger.info("WEBHOOK_SECRET nao configurado - aceitando requisicao sem validacao HMAC")
        return True

    # Validar HMAC se secret existe
    signature = req.headers.get('X-Webhook-Signature', '')
    if not signature:
        # MegaAPI nao envia header X-Webhook-Signature - aceitar mesmo assim
        logger.info("Webhook sem header X-Webhook-Signature - aceitando (MegaAPI nao envia HMAC)")
        return True

    payload = req.get_data()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, f"sha256={expected}") and not hmac.compare_digest(signature, expected):
        logger.warning(f"HMAC invalido. Expected: {expected[:16]}..., Got: {signature[:16]}...")
        return False

    return True


def extrair_dados_megaapi(payload):
    """
    Extrai dados da mensagem do payload MegaAPI.
    Suporta formato com e sem wrapper 'data'.

    MegaAPI envia eventos como:
    {
        "event": "messages.upsert",
        "instance": "megastart-xxx",
        "data": {
            "key": {"remoteJid": "55..@s.whatsapp.net", "fromMe": false, "id": "xxx"},
            "message": {"conversation": "texto"},
            "messageType": "conversation",
            "messageTimestamp": 1234567890
        }
    }
    """
    if not payload:
        return None

    # Verificar tipo de evento
    event = payload.get('event', '')

    # Eventos que devemos IGNORAR (nao sao mensagens)
    EVENTOS_IGNORAR = {
        'connection.update',
        'contacts.update',
        'contacts.upsert',
        'groups.update',
        'groups.upsert',
        'presence.update',
        'chats.update',
        'chats.upsert',
        'chats.delete',
        'call',
        'qrcode.updated',
        'status.instance',
    }

    if event and event in EVENTOS_IGNORAR:
        logger.debug(f"Evento ignorado (nao e mensagem): {event}")
        return None

    # Logar evento aceito para debug
    logger.info(f"Evento aceito para processamento: '{event}' (payload keys: {list(payload.keys())})")

    # Extrair dados - com ou sem wrapper 'data'
    data = payload.get('data', payload)
    logger.info(f"Data extraido do payload (type={type(data).__name__}, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'})")

    # Se data for lista (messages.upsert pode enviar array), pegar primeiro
    if isinstance(data, list):
        logger.info(f"Data e lista com {len(data)} itens")
        if len(data) == 0:
            logger.warning("Lista de dados vazia - ignorando")
            return None
        data = data[0]

    # Extrair remetente
    key = data.get('key', {})
    remote_jid = key.get('remoteJid', '')
    from_me = key.get('fromMe', False)
    msg_id = key.get('id', '')
    logger.info(f"Key extraido: remoteJid={remote_jid}, fromMe={from_me}, id={msg_id}")

    # Ignorar mensagens enviadas por nos
    if from_me:
        logger.info(f"Mensagem fromMe=True ignorada (enviada por nos): {msg_id}")
        return None

    # Extrair telefone do JID (5511999999999@s.whatsapp.net -> 5511999999999)
    remetente = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
    if not remetente:
        logger.warning(f"Remetente vazio apos extrair de JID: {remote_jid}")
        return None

    # Tipo de mensagem
    message_type = data.get('messageType', 'conversation')
    message_obj = data.get('message', {})
    timestamp = data.get('messageTimestamp', int(datetime.utcnow().timestamp()))

    # Log timestamp para debug (sem rejeitar - relogios podem estar dessincronizados)
    try:
        msg_time = datetime.fromtimestamp(int(timestamp))
        logger.info(f"Timestamp da mensagem: {msg_time} (agora: {datetime.utcnow()})")
    except (ValueError, TypeError, OSError):
        logger.info(f"Timestamp invalido/ausente: {timestamp} - continuando mesmo assim")

    resultado = {
        'remetente': remetente,
        'msg_id': msg_id,
        'timestamp': timestamp,
        'tipo': 'text',
        'texto': None,
        'url_midia': None,
        'mimetype': None,
        'caption': None,
        'interactive_id': None,
        'interactive_title': None,
    }

    if message_type in ('conversation', 'extendedTextMessage'):
        resultado['tipo'] = 'text'
        resultado['texto'] = (
            message_obj.get('conversation') or
            message_obj.get('extendedTextMessage', {}).get('text') or
            ''
        )

    elif message_type == 'imageMessage':
        resultado['tipo'] = 'image'
        img = message_obj.get('imageMessage', {})
        resultado['url_midia'] = img.get('url')
        resultado['mimetype'] = img.get('mimetype')
        resultado['caption'] = img.get('caption')

    elif message_type == 'audioMessage':
        resultado['tipo'] = 'audio'
        audio = message_obj.get('audioMessage', {})
        resultado['url_midia'] = audio.get('url')
        resultado['mimetype'] = audio.get('mimetype')

    elif message_type == 'documentMessage':
        resultado['tipo'] = 'document'
        doc = message_obj.get('documentMessage', {})
        resultado['url_midia'] = doc.get('url')
        resultado['mimetype'] = doc.get('mimetype')
        resultado['caption'] = doc.get('fileName')

    elif message_type in ('listResponseMessage', 'buttonsResponseMessage'):
        resultado['tipo'] = 'interactive'
        if message_type == 'listResponseMessage':
            lr = message_obj.get('listResponseMessage', {})
            resultado['interactive_id'] = lr.get('singleSelectReply', {}).get('selectedRowId')
            resultado['interactive_title'] = lr.get('title')
        else:
            br = message_obj.get('buttonsResponseMessage', {})
            resultado['interactive_id'] = br.get('selectedButtonId')
            resultado['interactive_title'] = br.get('selectedDisplayText')

    else:
        # Tentar extrair texto de formatos desconhecidos
        resultado['tipo'] = 'text'
        resultado['texto'] = str(message_obj) if message_obj else None

    return resultado


@bp.route('/webhook/whatsapp', methods=['POST', 'GET'])
def webhook_whatsapp():
    """
    Receives POSTs from MegaAPI.
    GET retorna 200 para verificacao de URL pela MegaAPI.
    """
    # Log toda requisicao para debug
    logger.info(f"=== WEBHOOK CHAMADO === method={request.method}, headers={str(dict(request.headers))[:200] if request.headers else 'N/A'}")

    # GET = verificacao de URL
    if request.method == 'GET':
        logger.info("Webhook GET - verificacao de URL")
        return jsonify({'status': 'ok', 'webhook': 'active'}), 200

    # Validacao de seguranca
    if not validar_webhook(request):
        logger.warning("Webhook rejeitado - validacao falhou")
        return jsonify({'error': 'Unauthorized'}), 403

    # Parse do payload
    try:
        raw_data = request.get_data(as_text=True)
        logger.info(f"Webhook raw data (primeiros 500 chars): {raw_data[:500]}")

        payload = request.json
        if not payload:
            logger.warning("Webhook payload vazio")
            return jsonify({'status': 'ignored', 'reason': 'empty_payload'}), 200

        logger.info(f"Webhook recebido: event={payload.get('event', 'N/A')}, instance={payload.get('instance', 'N/A')}")

        dados = extrair_dados_megaapi(payload)
        if not dados:
            logger.info(f"extrair_dados_megaapi retornou None - sem dados acionaveis para event={payload.get('event', 'N/A')}")
            return jsonify({'status': 'ignored', 'reason': 'no_actionable_data'}), 200

        remetente_raw = dados['remetente']
        tipo = dados['tipo']

        # Normalizar telefone para formato consistente (5527988010899)
        try:
            from app.services.whatsapp_service import WhatsAppService
            remetente = WhatsAppService.normalizar_telefone(remetente_raw)
        except Exception:
            remetente = remetente_raw

        logger.info(f"Mensagem de {remetente} (raw: {remetente_raw}) tipo={tipo}")

    except Exception as e:
        logger.error(f"Erro ao parsear payload: {e}", exc_info=True)
        return jsonify({'error': 'Invalid payload'}), 400

    # Processar baseado no tipo
    try:
        if tipo == 'text':
            texto = dados['texto']
            if not texto:
                return jsonify({'status': 'ignored', 'reason': 'empty_text'}), 200

            notif = HistoricoNotificacao(
                tipo='resposta_auto',
                direcao='inbound',
                remetente=remetente,
                destinatario='sistema',
                status_envio='recebido',
                mensagem=texto,
                mensagem_hash=hashlib.sha256(texto.encode()).hexdigest(),
                megaapi_id=dados['msg_id'],
                tipo_conteudo='text',
                status_leitura='nao_lida',
            )
            db.session.add(notif)
            db.session.commit()

            # Vincular ao historico de comunicacoes de compras (se for fornecedor)
            vincular_whatsapp_fornecedor(remetente, texto)

            # Processar assincronamente (chamar direto se Celery nao estiver rodando)
            try:
                from app.tasks.whatsapp_tasks import processar_mensagem_inbound
                processar_mensagem_inbound.delay(remetente, texto, dados['timestamp'])
            except Exception as e:
                logger.warning(f"Celery indisponivel, processando sincrono: {e}")
                try:
                    from app.services.roteamento_service import RoteamentoService
                    RoteamentoService.processar(remetente, texto)
                except Exception as e2:
                    logger.error(f"Erro ao processar mensagem: {e2}")

        elif tipo == 'interactive':
            interactive_id = dados['interactive_id']
            if not interactive_id:
                return jsonify({'status': 'ignored', 'reason': 'no_interactive_response'}), 200

            notif = HistoricoNotificacao(
                tipo='resposta_interativa',
                direcao='inbound',
                remetente=remetente,
                destinatario='sistema',
                status_envio='recebido',
                mensagem=interactive_id,
                caption=dados['interactive_title'],
                megaapi_id=dados['msg_id'],
                tipo_conteudo='interactive',
                status_leitura='nao_lida',
            )
            db.session.add(notif)
            db.session.commit()

            # Processar resposta interativa
            try:
                from app.services.roteamento_service import RoteamentoService
                resultado = RoteamentoService.processar_resposta_interativa(notif)
                if resultado and resultado.get('acao') == 'enviar_mensagem':
                    from app.services.whatsapp_service import WhatsAppService
                    WhatsAppService.enviar_mensagem(resultado['telefone'], resultado['mensagem'], prioridade=1)
            except Exception as e:
                logger.error(f"Erro ao processar interativo: {e}")

        elif tipo in ('image', 'audio', 'document'):
            notif = HistoricoNotificacao(
                tipo='midia_recebida',
                direcao='inbound',
                remetente=remetente,
                destinatario='sistema',
                status_envio='recebido',
                mensagem=dados['caption'] or f'[{tipo.upper()}]',
                megaapi_id=dados['msg_id'],
                tipo_conteudo=tipo,
                mimetype=dados['mimetype'],
                caption=dados['caption'],
                status_leitura='nao_lida',
            )
            db.session.add(notif)
            db.session.commit()

            # Baixar midia
            if dados['url_midia']:
                try:
                    from app.tasks.whatsapp_tasks import baixar_midia_task
                    baixar_midia_task.delay(notif.id, dados['url_midia'], tipo)
                except Exception as e:
                    logger.warning(f"Celery indisponivel para download de midia: {e}")

        else:
            logger.warning(f"Tipo de mensagem desconhecido: {tipo}")
            return jsonify({'status': 'ignored', 'reason': f'unknown_type_{tipo}'}), 200

    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Processing failed', 'details': str(e)}), 500

    return jsonify({'success': True, 'processed_at': datetime.utcnow().isoformat()})


@bp.route('/webhook/teste-inbound', methods=['POST'])
def teste_inbound():
    """
    Rota de teste para simular uma mensagem inbound.
    Use para verificar se o sistema esta salvando mensagens corretamente.

    POST /webhook/teste-inbound
    Body: {"telefone": "5527999888777", "mensagem": "Ola, teste!"}
    """
    try:
        data = request.json or {}
        telefone = data.get('telefone', '5527999999999')
        mensagem = data.get('mensagem', 'Mensagem de teste inbound')

        # Simular payload MegaAPI
        payload_simulado = {
            "event": "messages.upsert",
            "instance": "teste-local",
            "data": {
                "key": {
                    "remoteJid": f"{telefone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": f"teste_{datetime.utcnow().timestamp()}"
                },
                "message": {
                    "conversation": mensagem
                },
                "messageType": "conversation",
                "messageTimestamp": int(datetime.utcnow().timestamp())
            }
        }

        logger.info(f"=== TESTE INBOUND === telefone={telefone}, msg={mensagem}")

        # Processar como se fosse webhook real
        dados = extrair_dados_megaapi(payload_simulado)
        if not dados:
            return jsonify({'error': 'Falha ao extrair dados do payload simulado'}), 400

        # Salvar no banco
        notif = HistoricoNotificacao(
            tipo='resposta_auto',
            direcao='inbound',
            remetente=dados['remetente'],
            destinatario='sistema',
            status_envio='recebido',
            mensagem=dados['texto'],
            megaapi_id=dados['msg_id'],
            tipo_conteudo='text',
            status_leitura='nao_lida',
        )
        db.session.add(notif)
        db.session.commit()

        return jsonify({
            'success': True,
            'notificacao_id': notif.id,
            'remetente': dados['remetente'],
            'mensagem': dados['texto'],
            'info': 'Mensagem de teste salva. Verifique a Central de Mensagens.'
        })

    except Exception as e:
        logger.error(f"Erro no teste inbound: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
