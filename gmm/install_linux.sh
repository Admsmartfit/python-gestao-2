#!/bin/bash

# ============================================================================
# Script de Instalacao Automatica - Sistema GMM (Linux)
# Gestao Moderna de Manutencao
# Versao 2.0 - Com Setup Wizard
# ============================================================================

set -e  # Sair em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

print_info() {
    echo -e "${PURPLE}[INFO]${NC} $1"
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


print_header "INSTALADOR GMM - GESTAO MODERNA DE MANUTENCAO (Linux) - v2.0"
echo "Esta versao utiliza o Setup Wizard para configuracao"
echo ""

# Detectar distribuicao
print_step "1/10" "Detectando distribuicao Linux..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    print_ok "Distribuicao detectada: $PRETTY_NAME"
else
    print_error "Nao foi possivel detectar a distribuicao"
    exit 1
fi

# Atualizar repositorios
print_step "2/10" "Atualizando repositorios do sistema..."
case "$DISTRO" in
    ubuntu|debian|linuxmint)
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
print_step "3/10" "Verificando instalacao do Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_ok "Python $PYTHON_VERSION encontrado"
else
    print_warning "Python nao encontrado. Instalando..."
    case "$DISTRO" in
        ubuntu|debian|linuxmint)
            apt-get install -y python3 python3-pip python3-venv python3-dev build-essential
            ;;
        centos|rhel|fedora)
            yum install -y python39 python39-pip python39-devel gcc
            ;;
    esac
    print_ok "Python instalado"
fi

# Verificar versao do Python
print_step "Check" "Verificando versao do Python..."
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    if [[ "$PYTHON_VERSION" == "3.12"* ]] || [[ "$PYTHON_VERSION" == "3.11"* ]] || [[ "$PYTHON_VERSION" == "3.10"* ]]; then
        print_warning "Detectado Python $PYTHON_VERSION. Continuando..."
    else
        print_error "Python 3.9+ requerido. Versao detectada: $PYTHON_VERSION"
        exit 1
    fi
else
    print_ok "Versao do Python validada"
fi

# Instalar Redis
print_step "4/10" "Verificando instalacao do Redis..."
if command -v redis-server &> /dev/null; then
    print_ok "Redis encontrado"
else
    print_warning "Redis nao encontrado. Instalando..."
    case "$DISTRO" in
        ubuntu|debian|linuxmint)
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
        print_warning "Redis nao iniciou. Tarefas agendadas nao funcionarao."
    fi
fi

# Criar ambiente virtual
print_step "5/10" "Criando ambiente virtual Python..."
if [ -d "venv" ]; then
    print_warning "Ambiente virtual ja existe. Removendo..."
    rm -rf venv
fi

# Executar como usuario real, nao root
su - $REAL_USER -c "cd '$INSTALL_DIR' && python3 -m venv venv"
print_ok "Ambiente virtual criado"

# Ativar ambiente virtual e instalar dependencias
print_step "6/10" "Atualizando pip..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && pip install --upgrade pip -q"
print_ok "pip atualizado"

print_step "7/10" "Instalando dependencias Python..."
echo "Isso pode levar alguns minutos..."
su - $REAL_USER -c "cd '$INSTALL_DIR' && source venv/bin/activate && pip install -r requirements.txt -q"
print_ok "Dependencias instaladas"

# Criar estrutura de pastas
print_step "8/10" "Criando estrutura de pastas..."
mkdir -p instance
mkdir -p app/static/uploads/{audios,chamados,os}

# Ajustar permissoes
chown -R $REAL_USER:$REAL_USER instance
chown -R $REAL_USER:$REAL_USER app/static/uploads
chmod -R 755 app/static/uploads
chmod -R 755 instance

# Garantir que o usuario possa escrever o .env
chown $REAL_USER:$REAL_USER "$INSTALL_DIR"

print_ok "Estrutura de pastas criada"

# Configurar firewall
print_step "9/10" "Configurando firewall..."
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

# Obter IP
print_step "10/10" "Obtendo endereco IP da maquina..."
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
EnvironmentFile=-$INSTALL_DIR/.env
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
EnvironmentFile=-$INSTALL_DIR/.env
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
EnvironmentFile=-$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/celery -A app.celery beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Recarregar systemd
    systemctl daemon-reload
    systemctl enable gmm-flask gmm-celery gmm-celery-beat

    print_ok "Servicos systemd criados e habilitados"
fi

# Resumo final
echo ""
print_header "INSTALACAO DE DEPENDENCIAS CONCLUIDA!"
echo ""
echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}  PROXIMO PASSO: SETUP WIZARD${NC}"
echo -e "${PURPLE}========================================${NC}"
echo ""
echo "O GMM agora possui um Setup Wizard interativo para configuracao!"
echo ""
echo "1. Inicie o servidor Flask:"
echo ""
echo -e "   ${GREEN}cd $INSTALL_DIR${NC}"
echo -e "   ${GREEN}source venv/bin/activate${NC}"
echo -e "   ${GREEN}python run.py${NC}"
echo ""
echo "2. Acesse o Setup Wizard no navegador:"
echo ""
echo -e "   - Neste computador: ${GREEN}http://localhost:5000${NC}"
echo -e "   - Outros computadores: ${GREEN}http://$IP_ADDRESS:5000${NC}"
echo ""
echo "3. O Setup Wizard ira guia-lo para configurar:"
echo ""
echo "   - Chaves de seguranca (geradas automaticamente)"
echo "   - Banco de dados (SQLite ou PostgreSQL)"
echo "   - WhatsApp (MegaAPI)"
echo "   - Email (SMTP/IMAP)"
echo "   - Inteligencia Artificial (OpenAI)"
echo ""
echo "4. Apos o Setup Wizard, execute as migracoes:"
echo ""
echo -e "   ${GREEN}flask db upgrade${NC}"
echo -e "   ${GREEN}python seed_db.py${NC}  (cria usuario admin)"
echo ""
echo -e "${YELLOW}IMPORTANTE: Nao esqueca de trocar a senha do admin apos o primeiro login!${NC}"
echo ""
if [ -f "/etc/systemd/system/gmm-flask.service" ]; then
    echo "Gerenciamento de servicos (apos o Setup Wizard):"
    echo "- Iniciar: sudo systemctl start gmm-flask gmm-celery gmm-celery-beat"
    echo "- Parar: sudo systemctl stop gmm-flask gmm-celery gmm-celery-beat"
    echo "- Status: sudo systemctl status gmm-flask"
    echo "- Logs: sudo journalctl -u gmm-flask -f"
    echo ""
fi
echo "Informacoes uteis:"
echo "- Diretorio de instalacao: $INSTALL_DIR"
echo "- Banco de dados (apos setup): $INSTALL_DIR/instance/gmm.db"
echo "- Uploads: $INSTALL_DIR/app/static/uploads/"
echo ""
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
print_header "INSTALACAO FINALIZADA - ACESSE O SETUP WIZARD"
echo ""
