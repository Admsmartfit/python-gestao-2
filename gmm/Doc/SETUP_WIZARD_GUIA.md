# Guia de Uso do Setup Wizard GMM

## 📋 Visão Geral

O Setup Wizard é uma interface web interativa que simplifica a configuração inicial do GMM. Ele gera automaticamente o arquivo `.env` com todas as configurações necessárias.

---

## 🚀 Como Usar

### 1. Primeira Execução

Se o arquivo `.env` não existir, o sistema automaticamente redirecionará para o Setup Wizard:

```bash
# Clone o repositório
git clone <url-do-repo>
cd gmm

# Instale as dependências
pip install -r requirements.txt

# Execute o servidor
python run.py
```

Acesse `http://localhost:5000` e será **automaticamente redirecionado** para o Setup Wizard.

---

## 📝 Etapas do Setup

### Etapa 1: Verificação de Ambiente

O wizard verifica automaticamente:

- ✅ **Python 3.8+**: Versão mínima necessária
- ✅ **Permissão de Escrita**: Capacidade de criar o arquivo `.env`
- ⚠️ **Redis** (Opcional): Para tarefas assíncronas com Celery
- ✅ **Espaço em Disco**: Mínimo 1GB livre

**Ação Necessária**: Se houver erros, siga os comandos sugeridos na tela.

---

### Etapa 2: Chaves de Segurança

O wizard **gera automaticamente** chaves criptográficas:

- **SECRET_KEY**: Protege sessões e cookies do Flask (64 caracteres hex)
- **FERNET_KEY**: Criptografa dados sensíveis no banco (Base64)

**Ações Disponíveis**:
- 📋 **Copiar**: Clique no ícone para copiar a chave
- 🔄 **Regenerar**: Gera novas chaves se necessário
- ⚠️ **Importante**: Guarde essas chaves em local seguro!

**Por que essas chaves são importantes?**
- Sem a SECRET_KEY, hackers podem forjar sessões de login
- Sem a FERNET_KEY, dados criptografados (senhas SMTP, tokens) ficam inacessíveis

---

### Etapa 3: Banco de Dados

Escolha o tipo de banco:

#### Opção A: SQLite (Desenvolvimento)
- ✅ **Vantagens**: Sem configuração, arquivo local
- ⚠️ **Limitações**: Até 50 usuários simultâneos
- 📍 **Uso recomendado**: Desenvolvimento e testes

#### Opção B: PostgreSQL (Produção)
- ✅ **Vantagens**: Alta concorrência, backups, replicação
- ⚠️ **Requer**: Instalação e configuração do PostgreSQL
- 📍 **Uso recomendado**: Produção

**Campos PostgreSQL**:
- **Host**: `localhost` ou IP do servidor
- **Porta**: `5432` (padrão)
- **Nome do Banco**: Ex: `gmm_producao`
- **Usuário**: Ex: `gmm_user`
- **Senha**: Senha do usuário do banco

**Teste de Conexão**: Clique em "Testar Conexão" para validar antes de prosseguir.

**Comandos úteis (PostgreSQL no Linux)**:
```bash
# Instalar PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Criar banco e usuário
sudo -u postgres psql
CREATE DATABASE gmm_producao;
CREATE USER gmm_user WITH PASSWORD 'senha_segura';
GRANT ALL PRIVILEGES ON DATABASE gmm_producao TO gmm_user;
\q
```

---

### Etapa 4: Conectividade (WhatsApp & Email)

**Ambos são OPCIONAIS** - configure apenas se for usar essas funcionalidades.

#### WhatsApp (MegaAPI)

Para enviar notificações via WhatsApp:

1. **API Key**: Obtenha em [mega.chat/dashboard](https://mega.chat)
2. **API URL**: `https://api.mega.chat/v1` (padrão)

**Como obter credenciais**:
1. Acesse [mega.chat](https://mega.chat)
2. Crie uma conta gratuita
3. Conecte seu número WhatsApp Business
4. Copie a API Key do dashboard

#### Email (SMTP/IMAP)

Para enviar e receber emails:

**Campos SMTP (Envio)**:
- **Servidor**: `smtp.gmail.com` (Gmail) ou outro provedor
- **Porta**: `587` (padrão TLS)
- **Usuário**: Seu endereço de email
- **Senha**: Senha de aplicativo (não a senha normal!)

**Campos IMAP (Recebimento)**:
- **Servidor**: `imap.gmail.com` (Gmail)
- **Porta**: `993` (padrão SSL)

**Como obter senha de app do Gmail**:
1. Acesse [myaccount.google.com/security](https://myaccount.google.com/security)
2. Ative "Verificação em 2 etapas"
3. Vá em "Senhas de app"
4. Selecione "Email" → "Outro (GMM)"
5. Copie a senha de 16 dígitos gerada

---

### Etapa 5: Inteligência Artificial (Opcional)

Configure a OpenAI para funcionalidades avançadas:

**Funcionalidades Habilitadas**:
- 🎤 Transcrição automática de áudios do WhatsApp
- 🗣️ Abertura de OS por comando de voz
- 🤖 Chatbot inteligente para responder dúvidas

**Como obter API Key**:
1. Acesse [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Crie uma conta (se ainda não tiver)
3. Clique em "Create new secret key"
4. Copie a chave (começa com `sk-proj-...`)

**Custos Estimados**:
- Transcrição de áudio (Whisper): $0.006/minuto
- Chatbot (GPT-3.5): $0.002/1K tokens
- **Estimativa mensal** (100 áudios + 1000 mensagens): ~$5-10 USD

**Configure limites de gastos** em [platform.openai.com/settings/billing](https://platform.openai.com/settings/billing)

---

## ✅ Finalização

Após preencher todas as etapas, você verá um resumo das configurações:

| Item | Status |
|------|--------|
| Banco de Dados | SQLite / PostgreSQL |
| WhatsApp | ✓ Configurado / Não configurado |
| Email | ✓ Configurado / Não configurado |
| IA | ✓ Configurado / Opcional |

**Clique em "Salvar e Finalizar"** para:
1. Criar o arquivo `.env` na raiz do projeto
2. Criar arquivo `instance/setup.lock` (trava de segurança)
3. Bloquear acesso futuro ao wizard

---

## 🔄 Próximos Passos (Após Finalizar)

### 1. Reinicie o Servidor Flask

```bash
# Pressione Ctrl+C no terminal e execute novamente:
python run.py
```

### 2. Execute as Migrações do Banco

```bash
flask db upgrade
```

Isso cria todas as tabelas necessárias no banco de dados.

### 3. Crie o Usuário Admin Inicial

```bash
flask create-admin
```

Siga as instruções para definir:
- Nome do administrador
- Username
- Email
- Senha

### 4. Acesse o Sistema

Vá para `http://localhost:5000` e faça login com as credenciais criadas!

---

## 🔒 Segurança

### Bloqueio Automático

Após completar o setup, o wizard é **automaticamente bloqueado**:

- ✅ Arquivo `.env` foi criado
- ✅ Arquivo `instance/setup.lock` foi criado
- 🔒 Acessar `/setup` retorna erro 403

### Como Reconfigurar (Se Necessário)

⚠️ **ATENÇÃO**: Isso apagará todas as configurações!

```bash
# Delete o arquivo .env
rm .env

# Delete o arquivo de trava
rm instance/setup.lock

# Reinicie o Flask
python run.py
```

O sistema redirecionará automaticamente para o Setup Wizard novamente.

---

## 🐛 Troubleshooting

### Problema: "Permission Denied" ao salvar .env

**Causa**: Usuário sem permissão de escrita no diretório.

**Solução**:
```bash
# Linux/Mac
sudo chown $USER:$USER /caminho/para/gmm
chmod +w /caminho/para/gmm

# Windows (PowerShell como Admin)
icacls "C:\caminho\para\gmm" /grant Everyone:F
```

---

### Problema: Redis não conecta

**Causa**: Redis não está instalado ou não está rodando.

**Solução**:
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Verificar status
sudo systemctl status redis
```

**Nota**: Redis é **opcional**. O sistema funciona sem ele, mas tarefas agendadas (manutenção preventiva) não executarão automaticamente.

---

### Problema: PostgreSQL "Connection Refused"

**Causa**: PostgreSQL não está configurado para aceitar conexões locais.

**Solução**:
```bash
# Verificar se está rodando
sudo systemctl status postgresql

# Editar configuração
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Adicione esta linha:
local   all   gmm_user   md5

# Reinicie PostgreSQL
sudo systemctl restart postgresql
```

---

### Problema: Import Error ao executar run.py

**Causa**: Dependências não instaladas.

**Solução**:
```bash
# Instale todas as dependências
pip install -r requirements.txt

# Se estiver usando venv, ative primeiro:
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

---

### Problema: Erro "ModuleNotFoundError: No module named 'app.routes.setup'"

**Causa**: Blueprint do setup não foi registrado corretamente.

**Solução**: Verifique se o arquivo `app/routes/setup.py` existe e se `app/__init__.py` foi modificado corretamente conforme o PRD.

---

## 📚 Arquivos Gerados

Após completar o setup, os seguintes arquivos são criados:

### `.env`
```
c:\Users\ralan\python gestao 2\gmm\.env
```
Contém todas as configurações do sistema. **Nunca commite este arquivo no Git!**

### `instance/setup.lock`
```
c:\Users\ralan\python gestao 2\gmm\instance\setup.lock
```
Arquivo vazio que indica que o setup foi concluído.

### `instance/gmm.db` (se SQLite)
```
c:\Users\ralan\python gestao 2\gmm\instance\gmm.db
```
Arquivo do banco de dados SQLite (criado após `flask db upgrade`).

---

## 🎯 Configuração Manual (Alternativa)

Se preferir não usar o wizard, você pode:

1. Copiar `.env.example` para `.env`
2. Editar `.env` manualmente
3. Criar arquivo `instance/setup.lock` vazio

```bash
cp .env.example .env
nano .env  # Edite as configurações
touch instance/setup.lock
python run.py
```

---

## 💡 Dicas e Boas Práticas

### Desenvolvimento Local

- Use **SQLite** para desenvolvimento
- Deixe WhatsApp e Email em branco (opcional)
- Configure OpenAI apenas se for testar funcionalidades de IA

### Produção

- Use **PostgreSQL** para produção
- Configure backups regulares do banco
- Use senha forte para PostgreSQL
- Configure WhatsApp e Email para notificações
- Configure limites de gastos na OpenAI
- Use serviço systemd para manter o Flask rodando

---

## 🔗 Links Úteis

- [Documentação GMM](../README.md)
- [PRD do Setup Wizard](./PRD_SETUP_WIZARD.md)
- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [MegaAPI Dashboard](https://mega.chat/dashboard)
- [Google App Passwords](https://myaccount.google.com/apppasswords)

---

**Pronto!** Seu GMM está configurado e pronto para uso! 🎉
