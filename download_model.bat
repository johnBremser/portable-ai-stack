@echo off
setlocal
title Baixar Modelos - Local AI Stack
cd /d "%~dp0"

set BASE_DIR=%~dp0
set OLLAMA_EXE=%BASE_DIR%bin\ollama-windows.exe
set OLLAMA_MODELS=%BASE_DIR%data\models

:: Garantir que o Ollama saiba onde salvar
set OLLAMA_HOST=127.0.0.1:11434

echo ====================================================
echo    BAIXAR MODELOS PARA O PENDRIVE
echo ====================================================
echo Sugestoes:
echo  - gemma2:2b (Leve e rapido)
echo  - llama3.2 (Equilibrado)
echo  - deepseek-r1:1.5b (Bom para raciocinio)
echo ====================================================
echo.

set /p MODEL_NAME="Digite o nome do modelo (ex: gemma2:2b): "

if "%MODEL_NAME%"=="" (
    echo [ERRO] Nome do modelo nao pode ser vazio.
    pause
    exit /b
)

echo.
echo [!] Iniciando download do modelo: %MODEL_NAME%
echo [!] Os arquivos serao salvos em: %OLLAMA_MODELS%
echo.

:: O Ollama precisa estar rodando o 'serve' em background ou a gente usa o pull direto se ele for capaz
:: No modo portable, o pull tenta conectar no server. Vamos garantir que o server suba se nao estiver rodando.

"%OLLAMA_EXE%" pull %MODEL_NAME%

echo.
echo [!] Processo concluido.
pause
