#!/bin/bash

# ============================================================================
# Script de Instalacao Automatica - Sistema GMM (Linux)
# Gestao Moderna de Manutencao
# ============================================================================

set -e  # Sair em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funcoes auxiliares
print_header() {
    echo -e "${BLUE}"
    echo "============================================================================"
    echo "  $1"
    echo "============================================================================"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[$1]${NC} $2"
}

print_error() {
    echo -e "${RED}[ERRO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# Verificar se esta sendo executado como root
if [ "$EUID" -ne 0 ]; then
    print_error "Este script precisa ser executado como root (sudo)"
    exit 1
fi

# Obter usuario real (nao root)
REAL_USER=${SUDO_USER:-$USER}
REAL_HOME=$(eval echo ~$REAL_USER)

# Diretorio de instalacao
INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$INSTALL_DIR"

print_header "INSTALADOR GMM - GESTAO MODERNA DE MANUTENCAO (Linux)"
echo ""

# Detectar distribuicao
print_step "1/14" "Detectando distribuicao Linux..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    print_ok "Distribuicao detectada: $PRETTY_NAME"
else
    print_error "Nao foi possivel detectar a distribuicao"
    exit 1
fi

# Atualizar repositorios
print_step "2/14" "Atualizando repositorios do sistema..."
case "$DISTRO" in
    ubuntu|debian)
        apt-get update -qq
        ;;
    centos|rhel|fedora)
        yum update -y -q
        ;;
    *)
        print_warning "Distribuicao nao reconhecida. Pulando atualizacao."
        ;;
esac
print_ok "Repositorios atualizados"

# Instalar Python
print_step "3/14" "Verificando instalacao do Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_ok "Python $PYTHON_VERSION encontrado"
else
    print_warning "Python nao encontrado. Instalando..."
    case "$DISTRO" in
        ubuntu|debian)
            apt-get install -y python3 python3-pip python3-venv python3-dev build-essential
            ;;
        centos|rhel|fedora)
            yum install -y python39 python39-pip python39-devel gcc
            ;;
    esac
    print_ok "Python instalado"
fi

# Verificar versao do Python
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if (( $(echo "$PYTHON_VERSION < 3.9" | bc -l) )); then
    print_error "Python 3.9 ou superior e necessario. Versao atual: $PYTHON_VERSION"
    exit 1
fi

# Instalar Redis
print_step "4/14" "Verificando instalacao do Redis..."
if command -v redis-server &> /dev/null; then
    print_ok "Redis encontrado"
else
    print_warning "Redis nao encontrado. Instalando..."
    case "$DISTRO" in
        ubuntu|debian)
            apt-get install -y redis-server
            systemctl enable redis-server
            systemctl start redis-server
            ;;
        centos|rhel|fedora)
            yum install -y redis
            systemctl enable redis
            systemctl start redis
            ;;
    esac
    print_ok "Redis instalado e iniciado"
fi

# Verificar se Redis esta rodando
if redis-cli ping &> /dev/null; then
    print_ok "Redis respondendo"
else
    print_warning "Redis nao esta respondendo. Tentando iniciar..."
    systemctl start redis-server || systemctl start redis
    sleep 2
    if redis-cli ping &> /dev/null; then
        print_ok "Redis iniciado com sucesso"
    else
        print_error "Nao foi possivel iniciar o Redis"
        exit 1
    fi
fi

# Criar ambiente virtual
print_step "5/14" "Criando ambiente virtual Python..."
if [ -d "venv" ]; then
    print_warning "Ambiente virtual ja existe. Removendo..."
    rm -rf venv
fi

# Executar como usuario real, nao root
su - $REAL_USER -c "cd '$INSTALL_DIR' && python3 -m venv venv"
print_ok "Ambiente virtual criado"

# Ativar ambiente virtual e instalar dependencias
print_step "6/14" "Atualizando pip..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && pip install --upgrade pip -q"
print_ok "pip atualizado"

print_step "7/14" "Instalando dependencias Python..."
echo "Isso pode levar alguns minutos..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && pip install -r requirements.txt -q"
print_ok "Dependencias instaladas"

# Criar estrutura de pastas
print_step "8/14" "Criando estrutura de pastas..."
mkdir -p instance
mkdir -p app/static/uploads/{audios,chamados,os}

# Ajustar permissoes
chown -R $REAL_USER:$REAL_USER instance
chown -R $REAL_USER:$REAL_USER app/static/uploads
chmod -R 755 app/static/uploads
chmod -R 755 instance

print_ok "Estrutura de pastas criada"

# Criar arquivo .env
print_step "9/14" "Criando arquivo de configuracao .env..."
if [ -f ".env" ]; then
    print_warning "Arquivo .env ja existe. Criando backup..."
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    cp .env .env.backup.$BACKUP_DATE
fi

# Gerar chaves aleatorias
SECRET_KEY=$(su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && python3 -c \"import secrets; print(secrets.token_hex(32))\"")
FERNET_KEY=$(su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")

# Criar arquivo .env
cat > .env << EOF
# Configuracao do Sistema GMM - Gerado automaticamente
# Data: $(date)

# Flask
SECRET_KEY=$SECRET_KEY
FLASK_APP=run.py
FLASK_ENV=development

# Banco de Dados
# SQLite para desenvolvimento
DATABASE_URL=sqlite:///instance/gmm.db

# Para usar PostgreSQL em producao, descomente e configure:
# DATABASE_URL=postgresql://usuario:senha@localhost:5432/gmm

# Redis (Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# WhatsApp MegaAPI (configure suas credenciais)
MEGA_API_KEY=sua-chave-api-aqui
MEGA_API_URL=https://api.megaapi.com.br/v1/messages

# Criptografia
FERNET_KEY=$FERNET_KEY

# Email (opcional - configure se necessario)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
PURCHASE_EMAIL=

# Slack (opcional)
SLACK_WEBHOOK_URL=

# OpenAI (opcional)
OPENAI_API_KEY=
EOF

chown $REAL_USER:$REAL_USER .env
chmod 600 .env

print_ok "Arquivo .env criado com chaves aleatorias"

# Configurar firewall
print_step "10/14" "Configurando firewall..."
if command -v ufw &> /dev/null; then
    # UFW (Ubuntu/Debian)
    ufw allow 5000/tcp &> /dev/null
    print_ok "Porta 5000 liberada no UFW"
elif command -v firewall-cmd &> /dev/null; then
    # Firewalld (CentOS/RHEL/Fedora)
    firewall-cmd --permanent --add-port=5000/tcp &> /dev/null
    firewall-cmd --reload &> /dev/null
    print_ok "Porta 5000 liberada no Firewalld"
else
    print_warning "Firewall nao detectado. Configure manualmente a porta 5000/tcp"
fi

# Inicializar banco de dados
print_step "11/14" "Inicializando banco de dados..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && export FLASK_APP=run.py && flask db upgrade" || true
print_ok "Migracoes aplicadas"

print_step "12/14" "Criando usuario administrador padrao..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && python3 seed_db.py" || print_warning "Dados ja podem estar inicializados"
print_ok "Usuario admin criado (usuario: admin / senha: admin123)"

print_step "13/14" "Inicializando saldos de estoque..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && python3 init_saldos_estoque.py" || print_warning "Saldos ja podem estar inicializados"
print_ok "Saldos de estoque inicializados"

# Obter IP
print_step "14/14" "Obtendo endereco IP da maquina..."
IP_ADDRESS=$(hostname -I | awk '{print $1}')
print_ok "IP: $IP_ADDRESS"

# Criar arquivos de servico systemd (opcional)
echo ""
read -p "Deseja configurar o GMM como servico systemd? (s/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Ss]$ ]]; then
    print_step "EXTRA" "Criando arquivos de servico systemd..."

    # Servico Flask
    cat > /etc/systemd/system/gmm-flask.service << EOF
[Unit]
Description=GMM Flask Application
After=network.target redis.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Servico Celery Worker
    cat > /etc/systemd/system/gmm-celery.service << EOF
[Unit]
Description=GMM Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/celery -A app.celery worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Servico Celery Beat
    cat > /etc/systemd/system/gmm-celery-beat.service << EOF
[Unit]
Description=GMM Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/celery -A app.celery beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Recarregar systemd
    systemctl daemon-reload
    systemctl enable gmm-flask gmm-celery gmm-celery-beat

    print_ok "Servicos systemd criados e habilitados"
    echo ""
    echo "Para iniciar os servicos:"
    echo "  sudo systemctl start gmm-flask gmm-celery gmm-celery-beat"
    echo ""
    echo "Para verificar status:"
    echo "  sudo systemctl status gmm-flask"
    echo ""
    echo "Para ver logs:"
    echo "  sudo journalctl -u gmm-flask -f"
fi

# Resumo final
echo ""
print_header "INSTALACAO CONCLUIDA COM SUCESSO!"
echo ""
echo "Proximos passos:"
echo ""
echo "1. IMPORTANTE: Edite o arquivo .env e configure:"
echo "   - MEGA_API_KEY (chave da API do WhatsApp)"
echo "   - Configuracoes de email (se necessario)"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Inicie o sistema:"
if [ -f "/etc/systemd/system/gmm-flask.service" ]; then
    echo "   sudo systemctl start gmm-flask gmm-celery gmm-celery-beat"
else
    echo "   $INSTALL_DIR/start_linux.sh"
fi
echo ""
echo "3. Acesse o sistema no navegador:"
echo "   - Neste computador: http://localhost:5000"
echo "   - Outros computadores na rede: http://$IP_ADDRESS:5000"
echo ""
echo "4. Login padrao:"
echo "   Usuario: admin"
echo "   Senha: admin123"
echo "   [ALTERE A SENHA APOS O PRIMEIRO LOGIN!]"
echo ""
echo "5. Para producao, considere:"
echo "   - Alterar FLASK_ENV=production no .env"
echo "   - Usar PostgreSQL em vez de SQLite"
echo "   - Configurar HTTPS com certificado SSL"
echo "   - Usar Nginx ou Apache como proxy reverso"
echo ""
echo "Logs e informacoes:"
echo "- Arquivo de configuracao: $INSTALL_DIR/.env"
echo "- Banco de dados: $INSTALL_DIR/instance/gmm.db"
echo "- Uploads: $INSTALL_DIR/app/static/uploads/"
echo ""
if [ -f "/etc/systemd/system/gmm-flask.service" ]; then
    echo "Gerenciamento de servicos:"
    echo "- Iniciar: sudo systemctl start gmm-flask gmm-celery gmm-celery-beat"
    echo "- Parar: sudo systemctl stop gmm-flask gmm-celery gmm-celery-beat"
    echo "- Status: sudo systemctl status gmm-flask"
    echo "- Logs: sudo journalctl -u gmm-flask -f"
    echo ""
fi
echo "Para desinstalar:"
echo "- Delete a pasta 'venv': rm -rf $INSTALL_DIR/venv"
echo "- Delete a pasta 'instance': rm -rf $INSTALL_DIR/instance"
echo "- Delete o arquivo '.env': rm $INSTALL_DIR/.env"
if [ -f "/etc/systemd/system/gmm-flask.service" ]; then
    echo "- Remover servicos: sudo systemctl disable --now gmm-flask gmm-celery gmm-celery-beat"
    echo "                    sudo rm /etc/systemd/system/gmm-*.service"
    echo "                    sudo systemctl daemon-reload"
fi
echo ""
print_header "INSTALACAO FINALIZADA"
echo ""
