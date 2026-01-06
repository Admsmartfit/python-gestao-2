@echo off
REM ============================================================================
REM Script de Inicializacao - Sistema GMM (Windows)
REM Gestao Moderna de Manutencao
REM ============================================================================

echo.
echo ============================================================================
echo   INICIANDO SISTEMA GMM
echo ============================================================================
echo.

set "INSTALL_DIR=%~dp0"
cd /d "%INSTALL_DIR%"

REM Verificar se ambiente virtual existe
if not exist "venv\Scripts\activate.bat" (
    echo [ERRO] Ambiente virtual nao encontrado!
    echo Execute install_windows.bat primeiro
    pause
    exit /b 1
)

REM Verificar se .env existe
if not exist ".env" (
    echo [ERRO] Arquivo .env nao encontrado!
    echo Execute install_windows.bat primeiro
    pause
    exit /b 1
)

REM Verificar Redis
echo [1/4] Verificando Redis...
redis-cli ping >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Redis nao esta respondendo!
    echo.
    echo O sistema Flask vai iniciar, mas tarefas assincronas nao funcionarao.
    echo.
    echo Para iniciar Redis:
    echo - Windows: Execute redis-server.exe
    echo - WSL2: wsl sudo service redis-server start
    echo.
    timeout /t 5 >nul
) else (
    echo [OK] Redis respondendo
)

REM Obter IP
echo.
echo [2/4] Obtendo endereco IP...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP_ADDRESS=%%a
    goto :ip_found
)
:ip_found
set IP_ADDRESS=%IP_ADDRESS:~1%

echo [OK] IP: %IP_ADDRESS%

REM Informacoes de acesso
echo.
echo [3/4] Informacoes de acesso:
echo - Neste computador: http://localhost:5000
echo - Rede local: http://%IP_ADDRESS%:5000
echo.
echo Usuario padrao: admin
echo Senha padrao: admin123
echo.

REM Iniciar servicos em janelas separadas
echo [4/4] Iniciando servicos...
echo.

REM Flask
echo Iniciando Flask Web Server...
start "GMM - Flask (Porta 5000)" cmd /k "cd /d "%INSTALL_DIR%" && venv\Scripts\activate && set FLASK_APP=run.py && python run.py"

REM Aguardar 3 segundos
timeout /t 3 /nobreak >nul

REM Celery Worker
echo Iniciando Celery Worker...
start "GMM - Celery Worker" cmd /k "cd /d "%INSTALL_DIR%" && venv\Scripts\activate && celery -A app.celery worker --loglevel=info --pool=solo"

REM Aguardar 2 segundos
timeout /t 2 /nobreak >nul

REM Celery Beat
echo Iniciando Celery Beat Scheduler...
start "GMM - Celery Beat" cmd /k "cd /d "%INSTALL_DIR%" && venv\Scripts\activate && celery -A app.celery beat --loglevel=info"

echo.
echo ============================================================================
echo   SISTEMA INICIADO!
echo ============================================================================
echo.
echo 3 janelas foram abertas:
echo 1. Flask - Servidor Web (porta 5000^)
echo 2. Celery Worker - Processamento de tarefas
echo 3. Celery Beat - Agendador de tarefas periodicas
echo.
echo Aguarde alguns segundos para o sistema inicializar completamente.
echo.
echo Acesse no navegador:
echo http://localhost:5000
echo.
echo Para parar o sistema, feche todas as 3 janelas ou pressione Ctrl+C em cada uma.
echo.
echo ============================================================================

timeout /t 10 >nul

REM Abrir navegador automaticamente
start http://localhost:5000

exit
