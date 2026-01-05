PRD v3.0 - Plataforma GMM: Operações & Comunicação Unificada
Versão: 3.0 (Definitiva) Data: Janeiro 2026 Visão: Transformar o GMM de um simples gestor de OS num Ecossistema de Operações Inteligente, onde o WhatsApp (via MegaAPI) atua como interface primária para técnicos e gestores, eliminando fricção e centralizando dados.

1. Arquitetura e Fundações Técnicas
1.1 Stack Tecnológico
Backend: Python (Flask) + SQLAlchemy.

Async/Fila: Celery + Redis (Crítico para envios e downloads de mídia).

Database: SQLite (Dev) / PostgreSQL (Prod).

WhatsApp Gateway: MegaAPI (Protocolo WhatsApp Web).

Armazenamento: Sistema de Arquivos Local (/static/uploads) para mídias baixadas.

1.2 Princípio "Zero-Loss" (Armazenamento Técnico)
Como a MegaAPI não armazena mensagens, o GMM deve atuar como um "Cliente WhatsApp Completo":

Interceptação: O Webhook recebe tudo (texto, áudio, foto, status).

Ingestão de Mídia: Se a mensagem contém mídia, o backend dispara uma task Celery imediata para baixar o arquivo da URL temporária da MegaAPI e salvá-lo no disco local/S3.

Persistência: Nada é confiado à memória do telefone conectado. O banco de dados do GMM é a fonte da verdade.

1.3 Gestão de Armazenamento & Retenção
Limites de Arquivo: Máximo 10MB por arquivo de mídia (áudio, imagem, PDF).

Política de Retenção:
- Primeiros 3 meses: Armazenamento em disco local (/static/uploads) para acesso rápido.
- 3-6 meses: Compressão automática de imagens para formato WebP (redução de ~70% do tamanho).
- Após 6 meses: Migração para "Cold Storage" (S3 Glacier ou pasta de arquivo compactada), mantendo referência no banco de dados.

Estratégia de Backup:
- Backup incremental diário dos uploads locais.
- Backup semanal completo para S3/Backup externo.
- Retenção de backups: 90 dias.

2. Módulo de Comunicação & Automação (Conversational Core)
2.1 Central de Mensagens - Interface de Usuário
Substitui o WhatsApp Web oficial para a administração. Esta é a camada visual de apresentação das mensagens armazenadas no sistema (seção 1.2).

Interface Unificada: Uma tela única (/admin/chat) que mistura e-mails de fornecedores e WhatsApps de técnicos em uma timeline cronológica.

Funcionalidades de Chat:

Envio de Texto, Áudio (gravador no navegador) e Anexos (PDFs de OS, Notas Fiscais).

Indicadores de Status: Relógio (Fila), Check (Enviado), Check Azul (Lido - via webhook status).

Player de Áudio: Transcrição automática (via NLP - seção 2.2.1) e player HTML5 para ouvir os áudios dos técnicos (PTT).

Visualizador de Mídia: Imagens exibidas inline, PDFs com preview, vídeos com player nativo.

2.2 Chatbot Inteligente & NLP (Natural Language Processing)
2.2.1 Sistema de Transcrição de Áudio
Tecnologia: OpenAI Whisper API (modelo "whisper-1").

Idioma: Português do Brasil (pt-BR) com fallback para detecção automática.

Precisão Mínima: 85% de confiança na transcrição.

Fluxo de Processamento:
1. Áudio recebido via WhatsApp é baixado localmente (seção 1.2).
2. Task Celery `transcrever_audio_task` é disparada.
3. Arquivo é enviado para Whisper API (formato aceito: .ogg, .mp3, .wav).
4. Transcrição é salva em `historico_notificacoes.mensagem_transcrita`.
5. Se confiança < 70%, o sistema marca como "Requer Revisão Manual".

Limitações:
- Áudios > 25MB são rejeitados (limite da API Whisper).
- Custo: ~$0.006 por minuto de áudio (~R$0.03/min).
- Timeout: 60 segundos para processamento.

Fallback: Se API indisponível, o áudio é marcado para processamento posterior via retry (3 tentativas com backoff exponencial).

2.2.2 Abertura de Chamado por Voz
Após transcrição bem-sucedida, o sistema utiliza NLP básico (regex + keywords) para extrair informações:

Keywords de Equipamento: "esteira", "motor", "balança", "elevador" → Busca no catálogo de equipamentos.

Keywords de Urgência: "parou", "queimado", "vazamento", "fogo" → Define prioridade como "Alta".

Keywords de Local: "Centro", "Filial 2", "Depósito" → Identifica a unidade.

Se todos os dados são extraídos com sucesso, cria OS automaticamente. Caso contrário, solicita confirmação ao técnico via botões interativos.

2.2.3 Menu Interativo (List Messages)
Substituir comandos de texto (#STATUS) por menus nativos da MegaAPI:

Botão "Menu": Abre lista com [Minhas OSs, Solicitar Peça, Falar com Humano].

2.2.4 Gestão de OS via Chat
Check-in/Check-out: Botões na mensagem da OS para iniciar/pausar o trabalho.

Encerramento: Ao finalizar, o bot pede uma foto (obrigatória) e a descrição da solução.

2.3 QR Code Inteligente (Asset Tags)
Cada equipamento recebe uma etiqueta QR com especificações técnicas padronizadas.

Especificação Técnica:
- Formato de URL: `https://wa.me/{NUMERO_WHATSAPP_BOT}?text=EQUIP:{EQUIPAMENTO_ID}`
  - Exemplo: `https://wa.me/5511999999999?text=EQUIP:127`
- Formato de Imagem: PNG, 300x300 pixels.
- Error Correction Level: M (15% de correção de erro - resistente a sujeira/desgaste).
- Especificações de Impressão:
  - Tamanho: Etiqueta 5x5cm.
  - Material: Adesivo resistente a óleo, água e temperatura (poliéster ou vinil).
  - Informações adicionais na etiqueta: Nome do equipamento, Código patrimonial, Logo da empresa.

Fluxo de Uso:
1. Técnico escaneia QR Code com câmera do WhatsApp.
2. Abre conversa com bot já contextualizado naquele equipamento.
3. Menu automático: [Abrir Chamado, Ver Histórico, Baixar Manual PDF, Dados Técnicos].

Geração de Etiquetas:
- Biblioteca: `qrcode` (Python) + PIL para layout.
- Endpoint web: `/equipamentos/{id}/gerar-etiqueta` → PDF pronto para impressão.
- Impressão em massa: Botão "Imprimir Todas Etiquetas" gera PDF com grid 4x4 (16 etiquetas por página A4).

3. Módulo de Manutenção (OS)
3.1 Ciclo de Vida da OS
Criação: Via Web ou WhatsApp (NLP).

Vínculo: Toda OS criada gera um "Tópico" virtual no chat do técnico. Fotos enviadas nesse contexto vão direto para a galeria da OS (AnexosOS).

SLA Dinâmico: O prazo é calculado com base na prioridade e no contrato do prestador.

3.2 Alertas Preditivos
Detecção de Anomalia: Se um ativo tem >3 OSs em 30 dias, o sistema envia um "Insight" via WhatsApp para o Gerente sugerindo troca ou revisão profunda.

4. Módulo de Estoque e Compras (Supply Chain)
4.1 Controle Multi-Unidade
Saldos Locais: A tabela EstoqueSaldo rastreia a quantidade exata em cada unidade física.

Consumo Inteligente: O sistema tenta consumir do saldo local da unidade da OS. Se zero, sugere transferência ou compra.

4.2 Fluxo de Compras "One-Tap"
Solicitação: Técnico pede peça via Chat (Menu Lista) ou Web.

Notificação: Comprador recebe alerta no WhatsApp: "Nova solicitação: 5x Rolamento 608ZZ (Urgente)".

Cotação: Comprador insere preços.

Aprovação Executiva: Se o valor for alto, o Gerente recebe no WhatsApp:

Msg: "Aprovar compra de Motor WEG (R$ 1.200)?"

Botões: [ ✅ Aprovar ] [ ❌ Rejeitar ]. A ação reflete imediatamente no sistema.

Pedido: Disparo automático de PDF do pedido para o e-mail/WhatsApp do fornecedor.

4.3 Recebimento (Inbound Logistics)
Obrigatório: Ao marcar "Entregue", o usuário deve selecionar a Unidade de Destino. Isso cria o registro em MovimentacaoEstoque e atualiza o EstoqueSaldo correto.

5. Módulo Analytics & KPIs
5.1 Dashboards
MTTR (Tempo Médio de Reparo): Gráfico evolutivo.

Custo Total de Propriedade (TCO): Custo de aquisição + manutenção de cada equipamento.

5.2 Morning Briefing
Relatório Automático: Todo dia às 08:00, o Gerente recebe no WhatsApp um resumo:

"Bom dia! 🌤️ Status Hoje:"

🔴 2 OSs Atrasadas

🟡 3 Peças com Estoque Crítico

🟢 95% das OSs ontem foram concluídas.

6. Modelo de Dados (Schema Database v3.0)
Atualizações Críticas nas Tabelas Existentes
1. historico_notificacoes (Upgrade para Chat Completo)

megaapi_id (String, Index): ID único da mensagem na API (deduplicação).

tipo_conteudo (String): 'text', 'image', 'audio', 'document', 'location', 'interactive'.

url_midia_local (String): Caminho do arquivo salvo (/static/uploads/...).

mimetype (String): ex: audio/ogg.

caption (Text): Legenda da mídia.

status_leitura (String): 'enviado', 'entregue', 'lido'.

2. ordens_servico

tempo_execucao_minutos (Integer): Calculado via check-in/out.

origem_criacao (String): 'web', 'whatsapp_bot', 'qr_code'.

3. movimentacoes_estoque

unidade_id (FK): Obrigatório. Define onde a peça entrou/saiu.

custo_momento (Decimal): Grava o valor unitário no momento da transação (snapshot para auditoria financeira).

7. Roadmap de Implementação
🚀 Fase 1: Fundação & Ingestão (Semana 1)
Migration DB: Atualizar historico_notificacoes e estoque_saldo.

Webhook Engine: Implementar o "Roteador de Tipos" (Texto vs Mídia) e o "Downloader Service" para salvar arquivos da MegaAPI.

Auditoria: Garantir que 100% das mensagens (in/out) sejam salvas no banco.

🤖 Fase 2: Automação Básica (Semana 2)
Menus: Implementar envio de listMessage (MegaAPI) para o comando "#AJUDA" ou "Oi".

Aprovação: Implementar botões interativos para "Aceitar OS".

Chat UI: Criar a tela /admin/chat para visualização das conversas salvas.

📦 Fase 3: Compras & Fluxos Complexos (Semana 3)
Solicitação/Aprovação: Implementar o fluxo de "One-Tap Approval" no WhatsApp do gerente.

Recebimento: Interface de entrada de nota fiscal com alocação de unidade.

🧠 Fase 4: Inteligência (Semana 4)
NLP: Integração simples (Regex avançado ou API OpenAI) para transcrição de áudio.

Briefing: Tarefa Celery agendada para o relatório matinal.

QR Codes: Gerador de etiquetas PDF para os equipamentos.

8. Requisitos Não Funcionais (SLA & Segurança)
8.1 SLAs Técnicos do Sistema
Performance:
- Webhook deve responder em < 500ms (retorno 200 OK após validação).
- Download de mídia da MegaAPI: < 30 segundos (timeout).
- Carregamento da Central de Mensagens: < 2 segundos (últimas 50 mensagens).
- API endpoints (JSON): < 1 segundo para consultas simples.

Confiabilidade:
- Taxa de sucesso no envio de mensagens: > 95% (medida semanal).
- Uptime do sistema: 99.5% (permitido ~3.6 horas de downtime/mês).
- Taxa de perda de mensagens: 0% (princípio Zero-Loss).

Escalabilidade:
- Suporte para até 1.000 mensagens/dia (30k/mês).
- Máximo 100 usuários simultâneos na Central de Mensagens.
- Banco de dados deve suportar > 500k registros em `historico_notificacoes` sem degradação.

8.2 Segurança
Idempotência: O Webhook deve tratar duplicidade de eventos (usar megaapi_id como chave).

Segurança: Validação HMAC obrigatória em todos os webhooks.

Backup: Conforme definido em seção 1.3 (Gestão de Armazenamento).

8.3 Resiliência & Protocolo de Fallback
Circuit Breaker (MegaAPI):
- Estado OPEN após 5 falhas consecutivas.
- Timeout de recuperação: 10 minutos (tenta HALF_OPEN).
- Durante OPEN: Todas mensagens são enfileiradas para retry.

Protocolo de Fallback (Ordem de Prioridade):
1. WhatsApp (MegaAPI) - Canal primário.
2. Email (SMTP) - Após 3 falhas consecutivas do WhatsApp, ativar envio por email.
3. SMS (Twilio/AWS SNS) - Apenas para alertas críticos (OSs urgentes, aprovações executivas).
4. Notificação Push (Web/App) - Se disponível, como última camada.

Serviços de Terceiros:
- SMS: Twilio (custo: ~R$0.30/SMS) ou AWS SNS (R$0.20/SMS).
- Email: SendGrid (plano free: 100 emails/dia) ou SMTP próprio.

Critérios para Ativação de Fallback:
- WhatsApp indisponível por > 15 minutos.
- Taxa de falha > 50% em 1 hora.
- Circuit Breaker em estado OPEN por > 30 minutos.

9. Considerações de Custo & Escalabilidade
9.1 Estimativa de Volume Operacional
Volume Esperado (Operação Normal):
- 1.000 mensagens WhatsApp/dia (30.000/mês).
- 200 áudios para transcrição/mês (média 2min cada = 400min/mês).
- 500 downloads de mídia/mês (média 2MB cada = 1GB/mês).
- 50 OSs abertas/dia (1.500/mês).
- 20 usuários ativos simultâneos (pico).

9.2 Custos de Serviços de Terceiros
MegaAPI (WhatsApp Gateway):
- Modelo de cobrança: Verificar com provedor (geralmente por mensagem ou plano fixo).
- Estimativa conservadora: R$ 200-500/mês (baseado em 30k mensagens).
- Limite de mensagens/mês: Verificar contrato (exemplo: 50k mensagens).

OpenAI Whisper API:
- Custo: $0.006/minuto (~R$ 0.03/minuto na cotação R$5/USD).
- Volume: 400 minutos/mês = $2.40/mês (~R$ 12/mês).
- Limite de tamanho: 25MB por arquivo.

Twilio SMS (Fallback):
- Custo: ~R$ 0.30/SMS.
- Uso esperado: < 20 SMS/mês (apenas emergências) = R$ 6/mês.

SendGrid (Email):
- Plano Free: 100 emails/dia (suficiente para fase inicial).
- Plano Pago (se necessário): ~R$ 80/mês (40k emails).

AWS S3 / Cloud Storage (Cold Storage):
- S3 Standard: ~$0.023/GB/mês (primeiros 50GB).
- S3 Glacier: ~$0.004/GB/mês (arquivamento).
- Estimativa: 10GB de mídias = ~$0.23/mês (R$ 1.15/mês).

Total Estimado de Custos Mensais (APIs):
- Operação normal: R$ 220-520/mês.
- Com transcrição intensiva: +R$ 50/mês.
- Fallback SMS ativado: +R$ 20-100/mês.

9.3 Limites de Escalabilidade & Pontos de Atenção
Gargalos Identificados:
1. MegaAPI Rate Limit: 60 mensagens/minuto (atual). Se volume > 2.000 msgs/dia, negociar upgrade.
2. Webhook Processing: Celery workers devem escalar horizontalmente (mínimo 2 workers em produção).
3. Download de Mídia: 30s timeout pode ser insuficiente em conexões lentas. Considerar CDN/S3 direto.
4. Database: SQLite é adequado até ~10k OSs. Migrar para PostgreSQL em produção (> 50k registros).

Estratégia de Crescimento:
- Até 50 usuários: Servidor único (2 CPU, 4GB RAM) + Redis local.
- 50-200 usuários: Load balancer + 2 servidores app + Redis dedicado + PostgreSQL.
- > 200 usuários: Kubernetes/Docker Swarm + RDS PostgreSQL + ElastiCache Redis + S3.

Monitoramento de Limites:
- Dashboard de métricas deve exibir: Taxa de uso da API (% do limite), Latência média de webhook, Fila Celery (tamanho).
- Alertas automáticos se: Taxa de uso > 80% do limite, Latência > 1s, Fila > 100 tasks pendentes.