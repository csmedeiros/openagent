@echo off
REM ============================================================
REM  OpenAgent — Script de inicialização para Windows
REM  Uso: start.bat
REM ============================================================

setlocal EnableDelayedExpansion

REM ── Localiza o diretório do script ──────────────────────────
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM ── Verifica se .env existe ──────────────────────────────────
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado.
    echo         Copiando .env.example para .env ...
    copy ".env.example" ".env" >nul
    echo         Por favor edite .env com suas chaves de API antes de continuar.
    echo         Pressione qualquer tecla apos editar o arquivo .env ...
    pause >nul
)

REM ── Carrega variaveis do .env (basico — sem suporte a espacos/aspas) ───────
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "line=%%A"
    if not "!line:~0,1!"=="#" (
        if not "%%A"=="" set "%%A=%%B"
    )
)

REM ── Detecta Python ───────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo        Instale o Python 3.12+ e adicione ao PATH.
    pause
    exit /b 1
)

REM ── Instala dependencias (apenas se necessario) ───────────────
echo [INFO] Verificando dependencias ...
pip install -q -r openagent-core\requirements.txt
pip install -q fastapi "uvicorn[standard]" flask flask-cors aiofiles

REM ── Cria diretorio de workspace ───────────────────────────────
if not defined WORKSPACE_ROOT set "WORKSPACE_ROOT=%USERPROFILE%\Documents\openagent-tests"
if not exist "%WORKSPACE_ROOT%" mkdir "%WORKSPACE_ROOT%"
if not exist "%WORKSPACE_ROOT%\uploads" mkdir "%WORKSPACE_ROOT%\uploads"

echo.
echo ============================================================
echo   OpenAgent
echo   API  ^> http://localhost:8080
echo   Web  ^> http://localhost:3000
echo   Workspace: %WORKSPACE_ROOT%
echo ============================================================
echo.

REM ── Inicia a API FastAPI numa nova janela ─────────────────────
echo [INFO] Iniciando API FastAPI (porta 8080) ...
start "OpenAgent API" cmd /k "python -m uvicorn api:app --host 0.0.0.0 --port 8080 --reload"

REM ── Aguarda 3s para a API subir ──────────────────────────────
timeout /t 3 /nobreak >nul

REM ── Inicia o servidor web Flask numa nova janela ──────────────
echo [INFO] Iniciando servidor Web Flask (porta 3000) ...
start "OpenAgent Web" cmd /k "python web.py"

echo.
echo [OK] Ambos os servicos iniciados em janelas separadas.
echo      Feche as janelas para parar os servicos.
echo.
pause
endlocal
