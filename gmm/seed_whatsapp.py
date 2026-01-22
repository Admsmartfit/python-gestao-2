"""
Seed script for WhatsApp automation rules.
Run with: python seed_whatsapp.py
"""
from app import create_app, db
from app.models.whatsapp_models import RegrasAutomacao

app = create_app()

REGRAS_PADRAO = [
    # =============================================
    # REGRAS DE SAUDAÇÃO E AJUDA
    # =============================================
    {
        'palavra_chave': 'OI',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'resposta_texto': '👋 Olá! Bem-vindo ao GMM.\n\nDigite *#AJUDA* para ver os comandos disponíveis.',
        'prioridade': 10
    },
    {
        'palavra_chave': 'OLA',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'resposta_texto': '👋 Olá! Bem-vindo ao GMM.\n\nDigite *#AJUDA* para ver os comandos disponíveis.',
        'prioridade': 10
    },
    {
        'palavra_chave': 'BOM DIA',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'resposta_texto': '☀️ Bom dia! Como posso ajudar?\n\nDigite *#AJUDA* para ver os comandos.',
        'prioridade': 10
    },
    {
        'palavra_chave': 'BOA TARDE',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'resposta_texto': '🌤️ Boa tarde! Como posso ajudar?\n\nDigite *#AJUDA* para ver os comandos.',
        'prioridade': 10
    },
    {
        'palavra_chave': 'BOA NOITE',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'resposta_texto': '🌙 Boa noite! Como posso ajudar?\n\nDigite *#AJUDA* para ver os comandos.',
        'prioridade': 10
    },
    {
        'palavra_chave': '#AJUDA',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'executar_ajuda',
        'prioridade': 100
    },
    {
        'palavra_chave': 'AJUDA',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'executar_ajuda',
        'prioridade': 50
    },
    {
        'palavra_chave': 'MENU',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'exibir_menu',
        'prioridade': 50
    },

    # =============================================
    # REGRAS DE CONFIRMAÇÃO DE OS
    # =============================================
    {
        'palavra_chave': 'ACEITO',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_os_aceita',
        'prioridade': 100
    },
    {
        'palavra_chave': 'ACEITAR',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_os_aceita',
        'prioridade': 100
    },
    {
        'palavra_chave': 'SIM',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_os_aceita',
        'prioridade': 90
    },
    {
        'palavra_chave': 'RECUSO',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_os_recusada',
        'prioridade': 100
    },
    {
        'palavra_chave': 'RECUSAR',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_os_recusada',
        'prioridade': 100
    },
    {
        'palavra_chave': 'NAO',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_os_recusada',
        'prioridade': 90
    },

    # =============================================
    # REGRAS DE STATUS
    # =============================================
    {
        'palavra_chave': '#STATUS',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'executar_status',
        'prioridade': 100
    },
    {
        'palavra_chave': 'STATUS',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'executar_status',
        'prioridade': 50
    },

    # =============================================
    # REGRAS DE COMPRA/PEÇAS
    # =============================================
    {
        'palavra_chave': '#COMPRA',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'funcao_sistema': 'executar_compra',
        'prioridade': 100
    },
    {
        'palavra_chave': '#PECA',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'funcao_sistema': 'solicitar_peca',
        'prioridade': 100
    },
    {
        'palavra_chave': '#SEPARADO',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'funcao_sistema': 'confirmar_separacao',
        'prioridade': 100
    },

    # =============================================
    # REGRAS DE CONCLUSÃO
    # =============================================
    {
        'palavra_chave': '#CONCLUIDO',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'concluir_os',
        'prioridade': 100
    },
    {
        'palavra_chave': 'CONCLUIDO',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'concluir_os',
        'prioridade': 50
    },
    {
        'palavra_chave': 'FINALIZADO',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'concluir_os',
        'prioridade': 50
    },

    # =============================================
    # REGRAS DE TRANSBORDO (Falar com humano)
    # =============================================
    {
        'palavra_chave': 'FALAR',
        'tipo_correspondencia': 'contem',
        'acao': 'transbordar',
        'encaminhar_para_perfil': 'admin',
        'resposta_texto': '📞 Entendi que você precisa falar com alguém.\n\nEstou encaminhando sua mensagem para a equipe. Aguarde!',
        'prioridade': 30
    },
    {
        'palavra_chave': 'URGENTE',
        'tipo_correspondencia': 'contem',
        'acao': 'transbordar',
        'encaminhar_para_perfil': 'admin',
        'resposta_texto': '🚨 Mensagem marcada como *URGENTE*.\n\nEncaminhando para a equipe imediatamente!',
        'prioridade': 80
    },
    {
        'palavra_chave': 'PROBLEMA',
        'tipo_correspondencia': 'contem',
        'acao': 'transbordar',
        'encaminhar_para_perfil': 'admin',
        'resposta_texto': '⚠️ Identificamos que você está com um problema.\n\nUm responsável entrará em contato em breve.',
        'prioridade': 40
    },
    {
        'palavra_chave': 'RECLAMACAO',
        'tipo_correspondencia': 'contem',
        'acao': 'transbordar',
        'encaminhar_para_perfil': 'admin',
        'resposta_texto': '📝 Sua reclamação foi registrada.\n\nUm responsável analisará e entrará em contato.',
        'prioridade': 60
    },

    # =============================================
    # REGRAS DE AVALIAÇÃO
    # =============================================
    {
        'palavra_chave': '1',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'registrar_avaliacao',
        'prioridade': 20
    },
    {
        'palavra_chave': '2',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'registrar_avaliacao',
        'prioridade': 20
    },
    {
        'palavra_chave': '3',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'registrar_avaliacao',
        'prioridade': 20
    },
    {
        'palavra_chave': '4',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'registrar_avaliacao',
        'prioridade': 20
    },
    {
        'palavra_chave': '5',
        'tipo_correspondencia': 'exata',
        'acao': 'responder',
        'funcao_sistema': 'registrar_avaliacao',
        'prioridade': 20
    },

    # =============================================
    # REGRAS DE AGENDAMENTO
    # =============================================
    {
        'palavra_chave': 'AGENDAR',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'funcao_sistema': 'iniciar_agendamento',
        'prioridade': 50
    },
    {
        'palavra_chave': '#AGENDA',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'funcao_sistema': 'iniciar_agendamento',
        'prioridade': 100
    },

    # =============================================
    # REGRAS DE INFORMAÇÃO
    # =============================================
    {
        'palavra_chave': 'HORARIO',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'resposta_texto': '🕐 *Horário de Atendimento*\n\nSegunda a Sexta: 08:00 às 18:00\nSábado: 08:00 às 12:00\n\nFora deste horário, deixe sua mensagem que responderemos assim que possível.',
        'prioridade': 30
    },
    {
        'palavra_chave': 'ENDERECO',
        'tipo_correspondencia': 'contem',
        'acao': 'responder',
        'resposta_texto': '📍 *Endereço*\n\nPor favor, entre em contato com a administração para informações de endereço.',
        'prioridade': 30
    },

    # =============================================
    # REGRA PADRÃO (FALLBACK)
    # =============================================
    {
        'palavra_chave': '*',
        'tipo_correspondencia': 'contem',
        'acao': 'transbordar',
        'encaminhar_para_perfil': 'admin',
        'resposta_texto': '📨 Sua mensagem foi recebida.\n\nPara comandos disponíveis, digite *#AJUDA*.',
        'prioridade': 0
    }
]

with app.app_context():
    print("=" * 50)
    print("Seed de Regras de Automação WhatsApp")
    print("=" * 50)

    # Verificar se já existem regras
    regras_existentes = RegrasAutomacao.query.count()

    if regras_existentes > 0:
        resposta = input(f"\nJá existem {regras_existentes} regras. Deseja substituir? (s/n): ")
        if resposta.lower() != 's':
            print("Operação cancelada.")
            exit()

        print("Removendo regras existentes...")
        RegrasAutomacao.query.delete()
        db.session.commit()

    print(f"\nInserindo {len(REGRAS_PADRAO)} regras de automação...")

    for regra_data in REGRAS_PADRAO:
        # Remover espaços da palavra-chave se houver (para manter compatibilidade)
        palavra_chave = regra_data['palavra_chave'].replace(' ', '_') if ' ' in regra_data['palavra_chave'] else regra_data['palavra_chave']

        # Se a palavra-chave original tinha espaço, usar tipo_correspondencia 'contem'
        if ' ' in regra_data['palavra_chave']:
            regra_data['tipo_correspondencia'] = 'contem'
            palavra_chave = regra_data['palavra_chave'].split()[0]  # Usar primeira palavra

        regra = RegrasAutomacao(
            palavra_chave=palavra_chave,
            tipo_correspondencia=regra_data.get('tipo_correspondencia', 'exata'),
            acao=regra_data['acao'],
            resposta_texto=regra_data.get('resposta_texto'),
            encaminhar_para_perfil=regra_data.get('encaminhar_para_perfil'),
            funcao_sistema=regra_data.get('funcao_sistema'),
            prioridade=regra_data.get('prioridade', 0),
            ativo=True
        )
        db.session.add(regra)

    db.session.commit()

    print("\n✅ Regras de automação criadas com sucesso!")
    print(f"Total: {RegrasAutomacao.query.count()} regras ativas")

    # Listar regras por prioridade
    print("\n📋 Regras ordenadas por prioridade:")
    print("-" * 50)
    regras = RegrasAutomacao.query.order_by(RegrasAutomacao.prioridade.desc()).all()
    for r in regras:
        print(f"  [{r.prioridade:3d}] {r.palavra_chave:15s} -> {r.acao}")

    print("\n" + "=" * 50)
