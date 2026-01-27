# 🔧 Sistema de Manutenção Preventiva

## Visão Geral

O sistema de manutenção preventiva permite criar planos recorrentes de manutenção que geram automaticamente Ordens de Serviço (OSs) em intervalos programados. Isso garante que equipamentos críticos recebam manutenção regular, reduzindo falhas inesperadas.

---

## 📋 Acesso

**URL:** `http://127.0.0.1:5000/manutencao/preventiva`

**Permissões:**
- **Visualizar:** Admin, Gerente, Técnico
- **Criar/Editar/Excluir:** Admin, Gerente
- **Executar Planos:** Admin, Gerente, Técnico

**Menu:** Recursos → Manutenção Preventiva

---

## 🎯 Funcionalidades

### 1. **Criar Plano de Manutenção**

Um plano define:
- **Nome:** Descrição da manutenção (ex: "Lubrificação Semanal")
- **Aplicação:** Onde será aplicado
  - **Equipamento Específico:** Um único equipamento
  - **Categoria:** Todos os equipamentos de uma categoria (ex: Esteiras, Bombas)
- **Frequência:** Intervalo em dias (7, 15, 30, 90, etc.)
- **Procedimento:** Checklist ou instruções detalhadas

#### Exemplo 1: Manutenção em Equipamento Específico
```
Nome: Troca de Óleo - Compressor #1
Aplicação: Equipamento Específico → Compressor #1
Frequência: 30 dias (Mensal)
Procedimento:
- Desligar o compressor
- Drenar óleo usado
- Verificar filtros
- Adicionar óleo novo especificado (SAE 30)
- Registrar nível de óleo
```

#### Exemplo 2: Manutenção por Categoria
```
Nome: Inspeção Geral de Esteiras
Aplicação: Categoria → Esteira
Frequência: 7 dias (Semanal)
Procedimento:
- Verificar tensão da correia
- Limpar rolos
- Lubrificar articulações
- Verificar sensores
- Testar funcionamento
```

---

### 2. **Visualizar Planos**

A tela principal exibe:
- **Status:** Ativo ou Inativo
- **Aplicação:** Equipamento ou categoria
- **Frequência:** Intervalo de execução
- **Última Execução:** Quando foi executado pela última vez
- **Próxima Execução:** Quando vence
- **Alertas:**
  - 🔴 **Vencido:** Necessita execução imediata
  - 🟡 **Próximo:** Vence em até 3 dias
  - ⚪ **Regular:** Dentro do prazo

---

### 3. **Executar Plano Manualmente**

- Clique no botão ▶️ (Play) ao lado do plano
- O sistema cria automaticamente uma OS para cada equipamento afetado
- O plano registra a data de execução
- Gestores recebem notificação via WhatsApp com resumo

**Resultado da Execução:**
```
✅ 3 OS(s) criada(s) com sucesso

OSs criadas:
• Esteira #1 - Fábrica Centro
• Esteira #2 - Fábrica Centro
• Esteira #3 - Fábrica Sul
```

---

### 4. **Execução Automática (Tarefa Agendada)**

O sistema pode executar planos automaticamente através de uma tarefa Celery:

**Tarefa:** `executar_manutencoes_preventivas_task()`

**Quando executar:** Diariamente às 6h (recomendado)

**Configuração no Celery Beat:**
```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'manutencoes-preventivas-diarias': {
        'task': 'app.tasks.system_tasks.executar_manutencoes_preventivas_task',
        'schedule': crontab(hour=6, minute=0),  # Todos os dias às 6h
    },
}
```

**O que a tarefa faz:**
1. Verifica todos os planos ativos
2. Identifica planos vencidos (próxima execução <= hoje)
3. Cria OSs automaticamente para cada equipamento
4. Atualiza a data de última execução
5. Envia notificação WhatsApp para gestores

**Notificação Enviada:**
```
🔧 MANUTENÇÕES PREVENTIVAS AGENDADAS

Total de OSs criadas: 5
Planos executados: 2

Planos:
• Lubrificação Semanal: 3 OS(s)
• Inspeção Elétrica Mensal: 2 OS(s)
```

---

## 📊 Exemplos de Uso

### Cenário 1: Fábrica com Múltiplas Esteiras

**Problema:** 10 esteiras precisam de lubrificação semanal

**Solução:**
```
Plano: Lubrificação Semanal de Esteiras
Aplicação: Categoria → Esteira
Frequência: 7 dias
```

**Resultado:** A cada 7 dias, 10 OSs são criadas automaticamente, uma para cada esteira.

---

### Cenário 2: Equipamento Crítico

**Problema:** Transformador principal precisa de inspeção mensal

**Solução:**
```
Plano: Inspeção Mensal - Transformador Principal
Aplicação: Equipamento → Transformador Principal
Frequência: 30 dias
```

**Resultado:** Uma OS é criada todo mês para o transformador específico.

---

### Cenário 3: Manutenção Trimestral

**Problema:** Todos os compressores precisam de revisão completa a cada 3 meses

**Solução:**
```
Plano: Revisão Trimestral de Compressores
Aplicação: Categoria → Compressor
Frequência: 90 dias
```

**Resultado:** A cada 90 dias, OSs são criadas para todos os compressores cadastrados.

---

## 🔄 Fluxo de Trabalho

### Criação e Gestão
```
1. Criar Plano
   ↓
2. Definir Aplicação (Equipamento ou Categoria)
   ↓
3. Definir Frequência
   ↓
4. Ativar Plano
   ↓
5. Primeira Execução (Manual ou Automática)
   ↓
6. Sistema Agenda Próxima Execução
```

### Execução Automática Diária
```
Tarefa Celery (6h)
   ↓
Verificar Planos Vencidos
   ↓
Criar OSs Automaticamente
   ↓
Notificar Gestores
   ↓
Técnicos Recebem OSs no Dashboard
```

---

## ⚙️ Operações Disponíveis

| Ação | Ícone | Descrição |
|------|-------|-----------|
| **Executar** | ▶️ | Executa o plano imediatamente, criando OSs |
| **Editar** | ✏️ | Altera nome, frequência ou procedimento |
| **Ativar/Desativar** | 🔘 | Ativa ou pausa o plano |
| **Excluir** | 🗑️ | Remove o plano permanentemente |

---

## 📈 Benefícios

### Para a Operação
- ✅ Reduz falhas inesperadas em equipamentos
- ✅ Garante manutenções regulares
- ✅ Elimina esquecimento de manutenções críticas
- ✅ Histórico completo de manutenções preventivas

### Para a Gestão
- ✅ Visibilidade de planos vencidos
- ✅ Controle de conformidade com cronograma
- ✅ Relatórios de execução automáticos
- ✅ Otimização de custos com manutenção corretiva

### Para Técnicos
- ✅ Checklist padronizado de procedimentos
- ✅ OSs criadas automaticamente
- ✅ Instruções claras de manutenção
- ✅ Rastreamento de execuções

---

## 🚨 Alertas e Notificações

### Alertas na Interface
- **Vencido há X dias:** Plano não executado no prazo
- **Vence em X dias:** Plano próximo do vencimento (≤ 3 dias)

### Notificações WhatsApp
- **Execução Automática:** Resumo de OSs criadas
- **Alertas Críticos:** Múltiplos planos vencidos

---

## 🛠️ Configuração Inicial

### Passo 1: Cadastrar Categorias nos Equipamentos
```
1. Vá em Recursos → Equipamentos
2. Edite cada equipamento
3. Preencha o campo "Categoria"
4. Exemplos: Esteira, Bomba, Compressor, Transformador
```

### Passo 2: Criar Primeiro Plano
```
1. Acesse Manutenção Preventiva
2. Clique em "Novo Plano"
3. Preencha os dados
4. Salve
```

### Passo 3: Executar Primeiro Teste
```
1. Clique em ▶️ Executar
2. Verifique OSs criadas no Dashboard
3. Confirme recebimento da notificação
```

### Passo 4: Ativar Tarefa Automática
```
1. Configure o Celery Beat
2. Adicione o schedule conforme exemplo acima
3. Reinicie o Celery Worker
```

---

## 📝 Boas Práticas

### Nomenclatura de Planos
- ✅ **Boa:** "Lubrificação Semanal - Esteiras Linha A"
- ✅ **Boa:** "Inspeção Elétrica Mensal - Transformadores"
- ❌ **Ruim:** "Manutenção 1"
- ❌ **Ruim:** "Plano Novo"

### Descrição de Procedimentos
Use formato de checklist:
```
- [ ] Desligar equipamento
- [ ] Verificar componente X
- [ ] Limpar área Y
- [ ] Testar funcionamento
- [ ] Registrar observações
```

### Frequências Recomendadas
- **Semanal (7 dias):** Limpeza, lubrificação básica
- **Quinzenal (15 dias):** Inspeções visuais
- **Mensal (30 dias):** Ajustes e calibrações
- **Trimestral (90 dias):** Revisões completas
- **Semestral (180 dias):** Manutenções maiores

---

## 🔍 Troubleshooting

### Problema: OSs não são criadas automaticamente
**Solução:**
1. Verificar se o Celery Beat está rodando
2. Verificar logs do Celery
3. Confirmar que o plano está **Ativo**
4. Verificar se existe técnico cadastrado

### Problema: Plano não aparece como vencido
**Solução:**
1. Verificar se `ultima_execucao` foi registrada
2. Calcular manualmente: última execução + frequência
3. Se necessário, editar plano e executar manualmente

### Problema: Múltiplas OSs duplicadas
**Solução:**
1. Não executar plano manualmente no mesmo dia da tarefa automática
2. Verificar configuração do Celery Beat (não duplicar schedule)

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique este documento
2. Consulte os logs do sistema
3. Contate o administrador do sistema

---

**Última atualização:** 2026-01-27
