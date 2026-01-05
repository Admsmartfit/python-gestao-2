# Changelog - PRD v3.0 Atualizado
**Data**: Janeiro 2026
**Versão**: 3.1 (Com melhorias incorporadas)

---

## 📝 Resumo das Alterações

Este documento detalha as melhorias incorporadas ao PRD v3.0 com base na auditoria técnica realizada.

---

## ✅ Sugestões Implementadas

### 1. **Separação de "Histórico Próprio" e "Central de Mensagens"**
**Problema Original**: Conceitos técnicos (armazenamento) e de interface (UI) estavam misturados.

**Solução Implementada**:
- **Seção 1.2**: Renomeada para "Princípio Zero-Loss (Armazenamento Técnico)" - foca na camada de persistência.
- **Seção 2.1**: Renomeada para "Central de Mensagens - Interface de Usuário" - foca na camada de apresentação.
- Adicionada referência cruzada entre seções para clareza.

**Benefício**: Arquitetura mais clara, separação de responsabilidades entre backend e frontend.

---

### 2. **Especificação de Limites de Armazenamento**
**Problema Original**: PRD mencionava "Cold Storage após 6 meses" mas sem detalhes técnicos.

**Solução Implementada** (Nova Seção 1.3):

#### Limites de Arquivo
- Máximo **10MB por arquivo** de mídia (áudio, imagem, PDF).

#### Política de Retenção
- **0-3 meses**: Armazenamento em disco local (`/static/uploads`) para acesso rápido.
- **3-6 meses**: Compressão automática de imagens para WebP (redução de ~70% do tamanho).
- **> 6 meses**: Migração para "Cold Storage" (S3 Glacier ou pasta de arquivo compactada), mantendo referência no banco.

#### Estratégia de Backup
- Backup incremental diário dos uploads locais.
- Backup semanal completo para S3/Backup externo.
- Retenção de backups: 90 dias.

**Benefício**: Controle de custos de armazenamento, performance otimizada, auditoria completa.

---

### 3. **Definição de SLA Técnico do Sistema**
**Problema Original**: PRD mencionava "SLA de OS" mas não do sistema em si.

**Solução Implementada** (Nova Seção 8.1):

#### Performance
- Webhook: < 500ms (retorno 200 OK).
- Download de mídia: < 30 segundos (timeout).
- Central de Mensagens: < 2 segundos (últimas 50 mensagens).
- API endpoints JSON: < 1 segundo.

#### Confiabilidade
- Taxa de sucesso no envio: **> 95%** (medida semanal).
- Uptime: **99.5%** (permitido ~3.6 horas de downtime/mês).
- Taxa de perda de mensagens: **0%** (princípio Zero-Loss).

#### Escalabilidade
- Suporte para até **1.000 mensagens/dia** (30k/mês).
- Máximo **100 usuários simultâneos** na Central de Mensagens.
- Banco de dados: > 500k registros sem degradação.

**Benefício**: Métricas mensuráveis para monitoramento, expectativas claras de performance.

---

### 4. **Protocolo de Fallback Detalhado**
**Problema Original**: "Se MegaAPI cair... tentar SMS/Email" era muito vago.

**Solução Implementada** (Nova Seção 8.3):

#### Circuit Breaker (MegaAPI)
- Estado OPEN após **5 falhas consecutivas**.
- Timeout de recuperação: **10 minutos**.
- Durante OPEN: Mensagens enfileiradas para retry.

#### Ordem de Prioridade de Fallback
1. **WhatsApp (MegaAPI)** - Canal primário.
2. **Email (SMTP)** - Após 3 falhas consecutivas do WhatsApp.
3. **SMS (Twilio/AWS SNS)** - Apenas alertas críticos (OSs urgentes, aprovações).
4. **Notificação Push** - Se disponível, última camada.

#### Serviços de Terceiros
- SMS: **Twilio** (~R$0.30/SMS) ou **AWS SNS** (R$0.20/SMS).
- Email: **SendGrid** (plano free: 100 emails/dia) ou SMTP próprio.

#### Critérios para Ativação
- WhatsApp indisponível por **> 15 minutos**.
- Taxa de falha **> 50%** em 1 hora.
- Circuit Breaker em OPEN por **> 30 minutos**.

**Benefício**: Resiliência clara, custos previsíveis, zero downtime para comunicações críticas.

---

### 5. **Custos e Escalabilidade**
**Problema Original**: PRD não mencionava limites de uso da MegaAPI nem estimativas de custo.

**Solução Implementada** (Nova Seção 9):

#### 9.1 Estimativa de Volume Operacional
- 1.000 mensagens WhatsApp/dia (30k/mês).
- 200 áudios para transcrição/mês (400 minutos).
- 500 downloads de mídia/mês (1GB).
- 50 OSs/dia (1.500/mês).
- 20 usuários ativos simultâneos (pico).

#### 9.2 Custos de Serviços de Terceiros

| Serviço | Custo Mensal | Observações |
|---------|--------------|-------------|
| **MegaAPI** | R$ 200-500 | 30k mensagens |
| **OpenAI Whisper** | R$ 12 | 400 min/mês |
| **Twilio SMS** | R$ 6 | < 20 SMS emergência |
| **SendGrid** | R$ 0-80 | Free até 100/dia |
| **AWS S3** | R$ 1.15 | 10GB de mídias |
| **TOTAL** | **R$ 220-600/mês** | Operação normal |

#### 9.3 Limites de Escalabilidade

**Gargalos Identificados**:
1. MegaAPI Rate Limit: 60 msgs/min (atual). Se > 2k/dia, negociar upgrade.
2. Celery workers: Escalar horizontalmente (mínimo 2 em produção).
3. Download de mídia: 30s timeout pode ser insuficiente em conexões lentas.
4. Database: SQLite até ~10k OSs. PostgreSQL em produção (> 50k).

**Estratégia de Crescimento**:
- **Até 50 usuários**: Servidor único (2 CPU, 4GB RAM) + Redis local.
- **50-200 usuários**: Load balancer + 2 servidores app + Redis dedicado + PostgreSQL.
- **> 200 usuários**: Kubernetes + RDS PostgreSQL + ElastiCache Redis + S3.

**Benefício**: Planejamento financeiro claro, roadmap de infraestrutura, evita surpresas de custo.

---

### 6. **Detalhamento do NLP (Transcrição de Áudio)**
**Problema Original**: "Transcrição automática" era muito genérico.

**Solução Implementada** (Nova Seção 2.2.1):

#### Tecnologia
- **OpenAI Whisper API** (modelo "whisper-1").
- Idioma: **Português do Brasil (pt-BR)** com fallback para detecção automática.
- Precisão mínima: **85%** de confiança.

#### Fluxo de Processamento
1. Áudio recebido → baixado localmente.
2. Task Celery `transcrever_audio_task` disparada.
3. Arquivo enviado para Whisper API (.ogg, .mp3, .wav).
4. Transcrição salva em `historico_notificacoes.mensagem_transcrita` (novo campo).
5. Se confiança < 70% → marca "Requer Revisão Manual".

#### Limitações
- Áudios **> 25MB** rejeitados (limite da API).
- Custo: **~$0.006/min** (~R$0.03/min).
- Timeout: **60 segundos**.

#### Fallback
- Se API indisponível: retry (3 tentativas com backoff exponencial).

#### 2.2.2 Abertura de Chamado por Voz
- **Keywords de Equipamento**: "esteira", "motor", "balança" → Busca no catálogo.
- **Keywords de Urgência**: "parou", "queimado", "vazamento" → Prioridade Alta.
- **Keywords de Local**: "Centro", "Filial 2" → Identifica unidade.
- Se dados completos → Cria OS automática. Senão → Pede confirmação via botões.

**Benefício**: Implementação clara, custos previsíveis, expectativas de precisão definidas.

---

### 7. **QR Code - Especificação Técnica**
**Problema Original**: Não definia formato de URL nem especificações de impressão.

**Solução Implementada** (Seção 2.3 Expandida):

#### Especificação Técnica
- **Formato de URL**: `https://wa.me/{NUMERO}?text=EQUIP:{ID}`
  - Exemplo: `https://wa.me/5511999999999?text=EQUIP:127`
- **Formato de Imagem**: PNG, 300x300 pixels.
- **Error Correction Level**: M (15% de correção - resistente a sujeira/desgaste).

#### Especificações de Impressão
- **Tamanho**: Etiqueta 5x5cm.
- **Material**: Adesivo resistente a óleo, água e temperatura (poliéster ou vinil).
- **Informações adicionais**: Nome do equipamento, Código patrimonial, Logo da empresa.

#### Fluxo de Uso
1. Técnico escaneia QR com WhatsApp.
2. Abre conversa com bot contextualizado.
3. Menu automático: [Abrir Chamado, Ver Histórico, Baixar Manual PDF, Dados Técnicos].

#### Geração de Etiquetas
- Biblioteca: `qrcode` (Python) + PIL para layout.
- Endpoint: `/equipamentos/{id}/gerar-etiqueta` → PDF para impressão.
- **Impressão em massa**: Grid 4x4 (16 etiquetas por página A4).

**Benefício**: Padronização para compra de material, facilita implementação, ROI claro.

---

## 📊 Impacto das Mudanças

### Antes
- PRD genérico com lacunas técnicas.
- Custos imprevisíveis.
- Falta de métricas de sucesso.

### Depois
- **Especificações técnicas completas** para implementação direta.
- **Estimativa de custo mensal**: R$ 220-600.
- **SLAs mensuráveis**: Webhook < 500ms, Uptime 99.5%.
- **Roadmap de escalabilidade** claro (50 → 200 → 200+ usuários).
- **Protocolo de fallback** detalhado com 4 camadas de redundância.

---

## 🎯 Próximos Passos Recomendados

1. **Validar custos** com provedores:
   - Confirmar pricing da MegaAPI (30k mensagens/mês).
   - Criar conta Twilio/AWS SNS para SMS (fallback).
   - Configurar conta OpenAI para Whisper API.

2. **Setup de monitoramento**:
   - Implementar dashboard de métricas (seção 9.3).
   - Configurar alertas de SLA (latência, uptime, fila Celery).

3. **Testes de carga**:
   - Simular 1.000 mensagens/dia.
   - Validar tempos de resposta do webhook.
   - Testar protocolo de fallback (desligar MegaAPI intencionalmente).

4. **Documentação operacional**:
   - Criar runbook para ativação de fallback.
   - Documentar processo de migração de mídias para Cold Storage.
   - Treinar equipe nos novos SLAs.

---

## 📁 Arquivos Modificados

- **`gmm/Doc/prd.md`** - PRD v3.1 atualizado com todas as melhorias.
- **`gmm/Doc/prd_changelog.md`** - Este documento (registro de mudanças).

---

## ✍️ Autoria

- **Auditoria e Sugestões**: Claude Code (Análise técnica do sistema existente).
- **Implementação**: Incorporação das sugestões 1, 2, 3, 4, 7 e 8 ao PRD oficial.
- **Data**: Janeiro 2026.

---

**Versão do PRD**: 3.0 → **3.1 (Definitiva com Especificações Técnicas)**
