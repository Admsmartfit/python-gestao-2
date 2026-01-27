# Melhorias no Painel de Compras

## 📋 Resumo das Implementações

Este documento descreve as melhorias implementadas no painel de compras para facilitar o trabalho do comprador.

---

## 🆕 Novas Funcionalidades

### 1. **Histórico de Comunicações**
- Registro completo de todas as interações com fornecedores
- Rastreamento de envios via WhatsApp e Email
- Visualização de status (pendente, enviado, entregue, respondido)
- Armazenamento de respostas dos fornecedores

### 2. **Formas Alternativas de Contato**
- Campo para cadastrar contatos alternativos (site, telefone fixo, etc.)
- Exibição destacada na interface de fornecedores
- Orientações sobre como entrar em contato quando não há WhatsApp/Email

### 3. **Interface Melhorada de Detalhes do Pedido**
- Visualização clara de todos os fornecedores disponíveis
- Ícones indicando canais de comunicação disponíveis
- Histórico completo de comunicações em ordem cronológica
- Ações rápidas para enviar WhatsApp ou Email

---

## 🗄️ Alterações no Banco de Dados

### Modelo `Fornecedor`
```python
# Novo campo adicionado:
forma_contato_alternativa = db.Column(db.Text, nullable=True)
```

**Uso:**
- Armazenar informações como: "Site: www.exemplo.com.br", "Telefone: (11) 1234-5678", etc.
- Aparece na interface quando o fornecedor não tem WhatsApp ou Email

### Nova Tabela: `ComunicacaoFornecedor`
```sql
CREATE TABLE comunicacoes_fornecedor (
    id INTEGER PRIMARY KEY,
    pedido_compra_id INTEGER NOT NULL,
    fornecedor_id INTEGER NOT NULL,
    tipo_comunicacao VARCHAR(20) NOT NULL,  -- whatsapp, email, telefone, site
    direcao VARCHAR(10) NOT NULL,           -- enviado, recebido
    mensagem TEXT,
    status VARCHAR(20) DEFAULT 'pendente',  -- pendente, enviado, entregue, lido, respondido
    resposta TEXT,
    data_envio DATETIME,
    data_resposta DATETIME
)
```

---

## 🔌 Novos Endpoints (API)

### 1. Registrar Comunicação
```
POST /compras/<pedido_id>/registrar_comunicacao
```
**Payload:**
```json
{
    "fornecedor_id": 1,
    "tipo_comunicacao": "whatsapp",
    "mensagem": "Solicitação de orçamento..."
}
```

### 2. Registrar Resposta
```
POST /compras/comunicacao/<com_id>/resposta
```
**Payload:**
```json
{
    "resposta": "Preço: R$ 150,00. Prazo: 5 dias"
}
```

### 3. Listar Comunicações
```
GET /compras/<pedido_id>/comunicacoes
```

### 4. Solicitar Orçamento
```
POST /compras/<pedido_id>/solicitar_orcamento
```
**Payload:**
```json
{
    "fornecedor_ids": [1, 2, 3],
    "mensagem": "Mensagem personalizada opcional"
}
```

---

## 🎨 Melhorias na Interface

### Tela de Detalhes do Pedido

#### Coluna Principal:
1. **Card de Detalhes do Pedido**
   - Informações básicas
   - Status destacado
   - Solicitante e aprovador

2. **Card de Histórico de Comunicações**
   - Timeline de todas as interações
   - Ícones de tipo (WhatsApp/Email)
   - Badge de status
   - Mensagens e respostas
   - Botão "Atualizar"

#### Coluna Lateral:
1. **Card de Fornecedores Disponíveis**
   - Lista todos os fornecedores cadastrados para o item
   - Ícones de canais disponíveis:
     - 🟢 WhatsApp
     - 📧 Email
     - 🌐 Contato Alternativo
   - Preço e prazo de cada fornecedor
   - Alerta com instruções de contato alternativo
   - Botões de ação rápida:
     - "WhatsApp" (se disponível)
     - "Email" (se disponível)

2. **Card de Fornecedor Atual** (se selecionado)
   - Destaque visual
   - Informações completas
   - Badge de prazo

---

## 📦 Arquivos Criados/Modificados

### Novos Arquivos:
- `gmm/app/templates/compras/detalhes_melhorado.html` - Interface melhorada
- `gmm/apply_fornecedor_migration.py` - Script de migração
- `gmm/migrations/manual_add_fornecedor_fields.sql` - SQL da migração

### Arquivos Modificados:
- `gmm/app/models/estoque_models.py` - Novos modelos
- `gmm/app/routes/compras.py` - Novos endpoints
- `gmm/app/routes/os.py` - Correção de bug

---

## 🚀 Como Aplicar

### 1. Aplicar Migração do Banco de Dados

```bash
cd "c:\Users\ralan\python gestao 2\gmm"
python apply_fornecedor_migration.py
```

### 2. Reiniciar o Servidor

```bash
python run.py
```

### 3. Testar

1. Acesse: `http://localhost:5000/admin/compras`
2. Clique em um pedido
3. Você verá a nova interface com:
   - Histórico de comunicações
   - Lista de fornecedores
   - Opções de contato

---

## 💡 Como Usar

### Cadastrar Forma de Contato Alternativa

1. Acesse a página de edição de fornecedor
2. Preencha o campo "Forma de Contato Alternativa"
3. Exemplos:
   - "Site: www.empresa.com.br - Enviar orçamento pelo formulário"
   - "Telefone: (11) 1234-5678 - Falar com João"
   - "WhatsApp comercial: (11) 98888-8888"

### Solicitar Orçamento para Múltiplos Fornecedores

1. Acesse os detalhes de um pedido
2. Na lista de fornecedores, clique nos botões de ação
3. O sistema:
   - Envia automaticamente via WhatsApp (se disponível)
   - Ou envia via Email (se não tiver WhatsApp)
   - Registra a comunicação no histórico

### Registrar Resposta Manual

Se o fornecedor responder por outro canal (telefone, site):

1. Acesse o histórico de comunicações
2. Clique em "Registrar Resposta"
3. Digite a resposta recebida
4. Salve

---

## 🎯 Benefícios

### Para o Comprador:
✅ **Visão completa** de todas as comunicações em um só lugar
✅ **Acompanhamento fácil** de quem respondeu e quem não
✅ **Rastreamento** de status de envio (entregue, lido, etc)
✅ **Instruções claras** para fornecedores sem contato digital
✅ **Histórico permanente** de todas as interações

### Para a Gestão:
✅ **Auditoria completa** de cotações solicitadas
✅ **Tempo de resposta** de cada fornecedor
✅ **Relatórios** de comunicações (futuro)
✅ **Análise de desempenho** de fornecedores

---

## 🔮 Próximas Melhorias Sugeridas

1. **Integração com WhatsApp Business API**
   - Receber respostas automaticamente
   - Atualizar status em tempo real

2. **Dashboard de Fornecedores**
   - Taxa de resposta
   - Tempo médio de resposta
   - Ranking de melhores fornecedores

3. **Notificações**
   - Alertar quando fornecedor responder
   - Lembrar de cobrar quem não respondeu

4. **Templates de Mensagens**
   - Mensagens pré-definidas
   - Variáveis dinâmicas

5. **Comparativo de Cotações**
   - Tabela comparativa lado a lado
   - Recomendação de melhor custo-benefício

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs do servidor
2. Consulte este documento
3. Verifique se a migração foi aplicada corretamente

---

**Última atualização:** 2026-01-27
