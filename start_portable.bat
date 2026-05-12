@echo off
setlocal enabledelayedexpansion
title AI Stack Portable

:: 1. Definir caminhos relativos baseados na localização do .bat
set BASE_DIR=%~dp0
set PYTHON_PATH=%BASE_DIR%bin\python
set OLLAMA_EXE=%BASE_DIR%bin\ollama-windows.exe

:: 2. Configurar variáveis de ambiente do Ollama para o Pendrive
set OLLAMA_HOST=127.0.0.1:11434
:: ESSA LINHA É A CHAVE: impede o Ollama de usar o disco C:
set OLLAMA_MODELS=%BASE_DIR%data\models

echo [1/3] Iniciando Ollama Portable...
if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"
start "Ollama" /min "%OLLAMA_EXE%" serve

:: Aguarda o Ollama subir para verificar modelos
echo [!] Verificando modelos locais...
timeout /t 5 /nobreak > nul

:: Verifica se a pasta de manifestos está vazia (indicando ausência de modelos)
set MODELS_FOUND=0
if exist "%OLLAMA_MODELS%\manifests" (
    for /f %%i in ('dir /b /s "%OLLAMA_MODELS%\manifests" 2^>nul') do set MODELS_FOUND=1
)

if %MODELS_FOUND%==0 (
    echo.
    echo [AVISO] Nenhum modelo local encontrado no pendrive!
    set /p DOWNLOAD_NOW="Deseja baixar o modelo padrao agora? (S/N): "
    if /i "!DOWNLOAD_NOW!"=="S" (
        call download_model.bat
    )
)

:: 3. Iniciar Backend usando o Python local
echo [2/3] Iniciando Backend...
cd /d "%BASE_DIR%backend"
:: Usamos o 'start' para rodar em background e não travar o script aqui
start "Backend" /min "%PYTHON_PATH%\python.exe" -m uvicorn api:app --host 0.0.0.0 --port 8500

:: 4. Iniciar Frontend
echo [3/3] Iniciando Frontend...
cd /d "%BASE_DIR%frontend"
"%PYTHON_PATH%\python.exe" app_web.py

pause
