#!/bin/bash

# ============================================================================
# Script de Inicializacao - Sistema GMM (Linux)
# Gestao Moderna de Manutencao
# ============================================================================

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "============================================================================"
    echo "  $1"
    echo "============================================================================"
    echo -e "${NC}"
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

print_step() {
    echo -e "${GREEN}[$1]${NC} $2"
}

# Diretorio de instalacao
INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$INSTALL_DIR"

print_header "INICIANDO SISTEMA GMM"
echo ""

# Verificar se ambiente virtual existe
if [ ! -f "venv/bin/activate" ]; then
    print_error "Ambiente virtual nao encontrado!"
    echo "Execute install_linux.sh primeiro"
    exit 1
fi

# Verificar se .env existe
if [ ! -f ".env" ]; then
    print_error "Arquivo .env nao encontrado!"
    echo "Execute install_linux.sh primeiro"
    exit 1
fi

# Verificar Redis
print_step "1/4" "Verificando Redis..."
if redis-cli ping &> /dev/null; then
    print_ok "Redis respondendo"
else
    print_warning "Redis nao esta respondendo!"
    echo ""
    echo "O sistema Flask vai iniciar, mas tarefas assincronas nao funcionarao."
    echo ""
    echo "Para iniciar Redis:"
    echo "  sudo systemctl start redis-server"
    echo "  # ou"
    echo "  sudo systemctl start redis"
    echo ""
    read -p "Deseja tentar iniciar o Redis automaticamente? (s/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        sudo systemctl start redis-server || sudo systemctl start redis
        sleep 2
        if redis-cli ping &> /dev/null; then
            print_ok "Redis iniciado com sucesso"
        else
            print_error "Nao foi possivel iniciar o Redis"
            echo "Continue manualmente ou cancele (Ctrl+C)"
            sleep 3
        fi
    fi
fi

# Obter IP
print_step "2/4" "Obtendo endereco IP..."
IP_ADDRESS=$(hostname -I | awk '{print $1}')
print_ok "IP: $IP_ADDRESS"

# Informacoes de acesso
echo ""
print_step "3/4" "Informacoes de acesso:"
echo "  - Neste computador: http://localhost:5000"
echo "  - Rede local: http://$IP_ADDRESS:5000"
echo ""
echo "Usuario padrao: admin"
echo "Senha padrao: admin123"
echo ""

# Verificar se servicos systemd existem
if [ -f "/etc/systemd/system/gmm-flask.service" ]; then
    echo ""
    echo "Servicos systemd detectados!"
    echo ""
    read -p "Deseja iniciar via systemd (recomendado para producao)? (S/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_step "4/4" "Iniciando servicos systemd..."
        sudo systemctl start gmm-flask gmm-celery gmm-celery-beat

        echo ""
        print_header "SISTEMA INICIADO VIA SYSTEMD"
        echo ""
        echo "Servicos iniciados:"
        echo "  - gmm-flask (Web Server - porta 5000)"
        echo "  - gmm-celery (Celery Worker)"
        echo "  - gmm-celery-beat (Agendador)"
        echo ""
        echo "Comandos uteis:"
        echo "  - Verificar status: sudo systemctl status gmm-flask"
        echo "  - Ver logs: sudo journalctl -u gmm-flask -f"
        echo "  - Parar servicos: sudo systemctl stop gmm-flask gmm-celery gmm-celery-beat"
        echo "  - Reiniciar: sudo systemctl restart gmm-flask gmm-celery gmm-celery-beat"
        echo ""
        echo "Acesse no navegador: http://localhost:5000"
        echo "============================================================================"
        echo ""
        exit 0
    fi
fi

# Iniciar em modo foreground (desenvolvimento)
print_step "4/4" "Iniciando servicos em modo foreground..."
echo ""
echo "ATENCAO: Os servicos serao executados em primeiro plano."
echo "Para parar, pressione Ctrl+C em cada terminal."
echo ""
echo "Abrindo 3 processos em background..."
echo ""

# Ativar ambiente virtual
source venv/bin/activate

# Criar arquivo de log temporario
LOG_DIR="$INSTALL_DIR/logs"
mkdir -p "$LOG_DIR"

# Arquivo de PID para gerenciar processos
PID_FILE="$INSTALL_DIR/.gmm_pids"
rm -f "$PID_FILE"

# Funcao para limpar processos ao sair
cleanup() {
    echo ""
    echo "Parando servicos..."
    if [ -f "$PID_FILE" ]; then
        while read PID; do
            if ps -p $PID > /dev/null 2>&1; then
                kill -TERM $PID 2>/dev/null || true
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    echo "Servicos parados."
    exit 0
}

# Capturar Ctrl+C
trap cleanup SIGINT SIGTERM

# Iniciar Flask
echo "Iniciando Flask Web Server..."
export FLASK_APP=run.py
python run.py > "$LOG_DIR/flask.log" 2>&1 &
FLASK_PID=$!
echo $FLASK_PID >> "$PID_FILE"
print_ok "Flask iniciado (PID: $FLASK_PID)"
sleep 3

# Iniciar Celery Worker
echo "Iniciando Celery Worker..."
celery -A app.celery worker --loglevel=info > "$LOG_DIR/celery-worker.log" 2>&1 &
CELERY_PID=$!
echo $CELERY_PID >> "$PID_FILE"
print_ok "Celery Worker iniciado (PID: $CELERY_PID)"
sleep 2

# Iniciar Celery Beat
echo "Iniciando Celery Beat Scheduler..."
celery -A app.celery beat --loglevel=info > "$LOG_DIR/celery-beat.log" 2>&1 &
BEAT_PID=$!
echo $BEAT_PID >> "$PID_FILE"
print_ok "Celery Beat iniciado (PID: $BEAT_PID)"

echo ""
print_header "SISTEMA INICIADO EM MODO FOREGROUND"
echo ""
echo "Servicos em execucao:"
echo "  1. Flask (PID: $FLASK_PID) - Servidor Web na porta 5000"
echo "  2. Celery Worker (PID: $CELERY_PID) - Processamento de tarefas"
echo "  3. Celery Beat (PID: $BEAT_PID) - Agendador de tarefas"
echo ""
echo "Logs salvos em: $LOG_DIR/"
echo "  - flask.log"
echo "  - celery-worker.log"
echo "  - celery-beat.log"
echo ""
echo "Acesse no navegador:"
echo "  http://localhost:5000"
echo "  http://$IP_ADDRESS:5000"
echo ""
echo "Para ver logs em tempo real:"
echo "  tail -f $LOG_DIR/flask.log"
echo ""
echo "Pressione Ctrl+C para parar todos os servicos"
echo "============================================================================"
echo ""

# Aguardar indefinidamente (ou ate Ctrl+C)
wait $FLASK_PID
