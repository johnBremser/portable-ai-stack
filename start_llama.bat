@echo off

setlocal enabledelayedexpansion
title Llama.cpp Server

:: 1. Definir caminhos relativos
set BASE_DIR=%~dp0
set LLAMA_EXE=%BASE_DIR%bin\llama.cpp\llama-server.exe
set MODELS_DIR=%BASE_DIR%data\models

:: 2. Verificar se o llama-server existe
if not exist "%LLAMA_EXE%" (
    echo [ERRO] llama-server.exe nao encontrado em bin\llama.cpp\
    pause
    exit /b
)

:: 3. Definir o modelo padrão (Qwen 3.6 35B)
:: set MODEL_PATH=%BASE_DIR%data\models\Qwen3.6-35B-A3B-UD-IQ4_NL\Qwen3.6-35B-A3B-UD-IQ4_NL.gguf
set MODEL_PATH=%BASE_DIR%data\models\Qwen3-Coder-30B-A3B-Instruct-GGUF\Qwen3-Coder-30B-A3B-Instruct-Q3_K_L.gguf

:: 4. Definir modelo de visao
rem set MM_PROJ_PATH=%BASE_DIR%data\models\Qwen3.6-35B-A3B-UD-IQ4_NL\mmproj-F16.gguf
set MM_PROJ_PATH=%BASE_DIR%data\models\Qwen3.5-9B-GGUF\mmproj-Qwen3.5-9B-BF16.gguf

:: Caso o modelo acima nao exista, tenta procurar qualquer .gguf na pasta de modelos
if not exist "%MODEL_PATH%" (
    echo [AVISO] Modelo padrao nao encontrado em %MODEL_PATH%
    echo Procurando outro modelo GGUF na pasta data\models...
    for /r "%MODELS_DIR%" %%f in (*.gguf) do (
        set MODEL_PATH=%%f
        goto :found_model
    )
)

:found_model
if not exist "%MODEL_PATH%" (
    echo [ERRO] Nenhum modelo GGUF encontrado!
    pause
    exit /b
)

echo ======================================================
echo [!] Iniciando llama-server em MODO ROTEADOR (Router Mode)
echo [!] Pasta de modelos: %MODELS_DIR%
echo [!] Limite de modelos na memoria: 1
echo [!] Pressione Ctrl+C para encerrar o servidor.
echo ======================================================
echo.

:: Executa o llama-server no modo roteador. Ele vai gerenciar e alternar
:: os modelos da pasta data\models automaticamente sob demanda.
"%LLAMA_EXE%" --models-dir "%MODELS_DIR%" --models-max 1 --port 8080 --host 0.0.0.0 -c 65536 --flash-attn on --no-mmap --cache-type-k q8_0 --cache-type-v q8_0 --parallel 1 --tools all --jinja

pause