@echo off
REM ============================================================================
REM Script de Instalacao Automatica - Sistema GMM (Windows)
REM Gestao Moderna de Manutencao
REM ============================================================================

echo.
echo ============================================================================
echo   INSTALADOR GMM - GESTAO MODERNA DE MANUTENCAO (Windows)
echo ============================================================================
echo.

REM Verificar se esta sendo executado como Administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] Este script precisa ser executado como Administrador!
    echo Clique com botao direito e selecione "Executar como administrador"
    pause
    exit /b 1
)

REM Salvar diretorio atual
set "INSTALL_DIR=%~dp0"
cd /d "%INSTALL_DIR%"

echo [1/12] Verificando instalacao do Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Por favor, instale Python 3.9 ou superior de python.org
    echo Marque a opcao "Add Python to PATH" durante a instalacao
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% encontrado

echo.
echo [2/12] Verificando instalacao do pip...
python -m pip --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] pip nao encontrado!
    echo Reinstale o Python com pip incluido
    pause
    exit /b 1
)
echo [OK] pip encontrado

echo.
echo [3/12] Verificando Redis...
redis-cli ping >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Redis nao encontrado ou nao esta em execucao!
    echo.
    echo O Redis e necessario para tarefas assincronas (Celery).
    echo.
    echo Opcoes de instalacao:
    echo 1. Redis para Windows: https://github.com/tporadowski/redis/releases
    echo 2. Redis via WSL2: wsl --install
    echo.
    echo Deseja continuar mesmo assim? (S/N)
    set /p CONTINUE_WITHOUT_REDIS=
    if /i not "%CONTINUE_WITHOUT_REDIS%"=="S" (
        echo Instalacao cancelada. Instale o Redis e execute novamente.
        pause
        exit /b 1
    )
) else (
    echo [OK] Redis encontrado e respondendo
)

echo.
echo [4/12] Criando ambiente virtual Python...
if exist "venv" (
    echo [AVISO] Ambiente virtual ja existe. Removendo...
    rmdir /s /q venv
)
python -m venv venv
if %errorLevel% neq 0 (
    echo [ERRO] Falha ao criar ambiente virtual
    pause
    exit /b 1
)
echo [OK] Ambiente virtual criado

echo.
echo [5/12] Ativando ambiente virtual...
call venv\Scripts\activate.bat
if %errorLevel% neq 0 (
    echo [ERRO] Falha ao ativar ambiente virtual
    pause
    exit /b 1
)
echo [OK] Ambiente virtual ativado

echo.
echo [6/12] Atualizando pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip atualizado

echo.
echo [7/12] Instalando dependencias Python...
echo Isso pode levar alguns minutos...
pip install -r requirements.txt --quiet
if %errorLevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias
    echo Verifique o arquivo requirements.txt e sua conexao com a internet
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

echo.
echo [8/12] Criando estrutura de pastas...
if not exist "instance" mkdir instance
if not exist "app\static\uploads" mkdir app\static\uploads
if not exist "app\static\uploads\audios" mkdir app\static\uploads\audios
if not exist "app\static\uploads\chamados" mkdir app\static\uploads\chamados
if not exist "app\static\uploads\os" mkdir app\static\uploads\os
echo [OK] Estrutura de pastas criada

echo.
echo [9/12] Criando arquivo de configuracao .env...
if exist ".env" (
    echo [AVISO] Arquivo .env ja existe. Criando backup...
    copy .env .env.backup.%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2% >nul
)

REM Gerar chaves aleatorias
for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SECRET_KEY=%%i
for /f "delims=" %%i in ('python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"') do set FERNET_KEY=%%i

REM Criar arquivo .env
(
echo # Configuracao do Sistema GMM - Gerado automaticamente
echo # Data: %date% %time%
echo.
echo # Flask
echo SECRET_KEY=%SECRET_KEY%
echo FLASK_APP=run.py
echo FLASK_ENV=development
echo.
echo # Banco de Dados
echo # SQLite para desenvolvimento
echo DATABASE_URL=sqlite:///instance/gmm.db
echo.
echo # Para usar PostgreSQL em producao, descomente e configure:
echo # DATABASE_URL=postgresql://usuario:senha@localhost:5432/gmm
echo.
echo # Redis (Celery^)
echo CELERY_BROKER_URL=redis://localhost:6379/0
echo CELERY_RESULT_BACKEND=redis://localhost:6379/0
echo.
echo # WhatsApp MegaAPI (configure suas credenciais^)
echo MEGA_API_KEY=sua-chave-api-aqui
echo MEGA_API_URL=https://api.megaapi.com.br/v1/messages
echo.
echo # Criptografia
echo FERNET_KEY=%FERNET_KEY%
echo.
echo # Email (opcional - configure se necessario^)
echo MAIL_SERVER=smtp.gmail.com
echo MAIL_PORT=587
echo MAIL_USE_TLS=True
echo MAIL_USERNAME=
echo MAIL_PASSWORD=
echo MAIL_DEFAULT_SENDER=
echo PURCHASE_EMAIL=
echo.
echo # Slack (opcional^)
echo SLACK_WEBHOOK_URL=
echo.
echo # OpenAI (opcional^)
echo OPENAI_API_KEY=
) > .env

echo [OK] Arquivo .env criado com chaves aleatorias

echo.
echo [10/12] Configurando firewall do Windows...
echo Permitindo porta 5000 (Flask^) no firewall...
netsh advfirewall firewall show rule name="Flask GMM" >nul 2>&1
if %errorLevel% neq 0 (
    netsh advfirewall firewall add rule name="Flask GMM" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
    if %errorLevel% equ 0 (
        echo [OK] Regra de firewall adicionada
    ) else (
        echo [AVISO] Nao foi possivel adicionar regra de firewall automaticamente
        echo Configure manualmente: Firewall do Windows ^> Regras de Entrada ^> Nova Regra ^> Porta 5000 TCP
    )
) else (
    echo [OK] Regra de firewall ja existe
)

echo.
echo [11/12] Inicializando banco de dados...
set FLASK_APP=run.py
flask db upgrade
if %errorLevel% neq 0 (
    echo [AVISO] Falha ao executar migracoes. Tentando inicializar banco...
)

echo.
echo Criando usuario administrador padrao...
python seed_db.py
if %errorLevel% neq 0 (
    echo [AVISO] Nao foi possivel criar dados iniciais
    echo Execute manualmente: python seed_db.py
) else (
    echo [OK] Usuario admin criado (usuario: admin / senha: admin123^)
)

echo.
echo Inicializando saldos de estoque...
python init_saldos_estoque.py
if %errorLevel% neq 0 (
    echo [AVISO] Nao foi possivel inicializar saldos
) else (
    echo [OK] Saldos de estoque inicializados
)

echo.
echo [12/12] Obtendo endereco IP da maquina...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP_ADDRESS=%%a
    goto :ip_found
)
:ip_found
set IP_ADDRESS=%IP_ADDRESS:~1%

echo.
echo ============================================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo ============================================================================
echo.
echo Proximos passos:
echo.
echo 1. IMPORTANTE: Edite o arquivo .env e configure:
echo    - MEGA_API_KEY (chave da API do WhatsApp^)
echo    - Configuracoes de email (se necessario^)
echo.
echo 2. Inicie o sistema executando:
echo    start_windows.bat
echo.
echo 3. Acesse o sistema no navegador:
echo    - Neste computador: http://localhost:5000
echo    - Outros computadores na rede: http://%IP_ADDRESS%:5000
echo.
echo 4. Login padrao:
echo    Usuario: admin
echo    Senha: admin123
echo    [ALTERE A SENHA APOS O PRIMEIRO LOGIN!]
echo.
echo 5. Para producao, considere:
echo    - Alterar FLASK_ENV=production no .env
echo    - Usar PostgreSQL em vez de SQLite
echo    - Configurar HTTPS com certificado SSL
echo    - Usar servidor web como Nginx ou IIS como proxy reverso
echo.
echo Logs e informacoes:
echo - Arquivo de configuracao: %INSTALL_DIR%.env
echo - Banco de dados: %INSTALL_DIR%instance\gmm.db
echo - Uploads: %INSTALL_DIR%app\static\uploads\
echo.
echo Para desinstalar:
echo - Delete a pasta 'venv'
echo - Delete a pasta 'instance'
echo - Delete o arquivo '.env'
echo.
echo ============================================================================
echo.

pause
