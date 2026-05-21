@echo off
setlocal enabledelayedexpansion
title AI Stack Portable (llama.cpp)

:: 1. Definir caminhos relativos baseados na localização do .bat
set BASE_DIR=%~dp0
set PYTHON_PATH=%BASE_DIR%bin\python
set LLAMA_EXE=%BASE_DIR%bin\llama.cpp\llama-server.exe
set MODELS_DIR=%BASE_DIR%data\models

:: 2. Verificar se o llama-server existe
if not exist "%LLAMA_EXE%" (
    echo [ERRO] llama-server.exe nao encontrado na pasta bin!
    pause
    exit /b
)

:: 3. Tentar encontrar um modelo .gguf na pasta data\models (busca recursiva)
echo [1/3] Procurando modelos GGUF em data\models...
set GGUF_MODEL=
for /r "%MODELS_DIR%" %%f in (*.gguf) do (
    set GGUF_MODEL=%%f
    goto :found_model
)

:found_model
if "%GGUF_MODEL%"=="" (
    echo.
    echo [AVISO] Nenhum modelo .gguf encontrado em %MODELS_DIR%
    echo Por favor, coloque um arquivo .gguf la ou informe o caminho completo.
    set /p GGUF_MODEL="Caminho do modelo GGUF: "
)

if not exist "!GGUF_MODEL!" (
    echo [ERRO] Modelo nao encontrado: !GGUF_MODEL!
    pause
    exit /b
)

echo [!] Usando modelo: !GGUF_MODEL!

:: 4. Iniciar llama-server
:: --ctx-size 4096 (padrao razoavel) --port 8080
echo [2/3] Iniciando llama-server...
start "llama-server" /min "%LLAMA_EXE%" -m "%BASE_DIR%data\models\Qwen3.5-9B-GGUF\Qwen3.5-9B-Q4_K_M.gguf" --alias "Qwen3.5_9B" --mmproj "%BASE_DIR%data\models\Qwen3.5-9B-GGUF\mmproj-Qwen3.5-9B-BF16.gguf" --port 8080 --host 0.0.0.0 -c 32768 --flash-attn on --no-mmap --cache-type-k q8_0 --cache-type-v q8_0 --parallel 1

:: Aguarda o servidor subir (modelos grandes podem demorar)
echo [!] Aguardando servidor LLM (12s)...
timeout /t 12 /nobreak > nul

:: 5. Iniciar Backend usando o Python local
echo [3/3] Iniciando Backend...
cd /d "%BASE_DIR%backend"
start "Backend" /min "%PYTHON_PATH%\python.exe" -m uvicorn api:app --host 0.0.0.0 --port 8500

:: 6. Iniciar Frontend
echo [4/4] Iniciando Frontend...
cd /d "%BASE_DIR%frontend"
"%PYTHON_PATH%\python.exe" app_web.py

