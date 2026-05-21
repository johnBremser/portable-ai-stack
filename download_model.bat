@echo off
setlocal
title Baixar Modelo GGUF - AI Stack Portable
cd /d "%~dp0"

set BASE_DIR=%~dp0
set MODELS_DIR=%BASE_DIR%data\models

echo ====================================================
echo    BAIXAR MODELO GGUF DO HUGGING FACE
echo ====================================================
echo.
echo Este script baixa modelos .gguf diretamente do
echo Hugging Face para a pasta data\models.
echo.
echo Exemplos de URLs (clique em "Download" no HuggingFace
echo e copie o link do arquivo .gguf):
echo.
echo  Qwen3.5-9B-Q4_K_M.gguf
echo  Mistral-7B-Instruct-v0.3.Q4_K_M.gguf
echo  gemma-2-2b-it-Q4_K_M.gguf
echo.
echo ====================================================
echo.

set /p GGUF_URL="Cole a URL do arquivo .gguf: "

if "%GGUF_URL%"=="" (
    echo [ERRO] URL nao pode ser vazia.
    pause
    exit /b
)

:: Extrai o nome do arquivo da URL
for %%A in ("%GGUF_URL%") do set FILE_NAME=%%~nxA

if "%FILE_NAME%"=="" (
    set /p FILE_NAME="Nome do arquivo de saida (ex: modelo.gguf): "
)

echo.
echo [!] Baixando: %FILE_NAME%
echo [!] Destino: %MODELS_DIR%\%FILE_NAME%
echo.

if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

curl.exe -L --progress-bar "%GGUF_URL%" -o "%MODELS_DIR%\%FILE_NAME%"

if %ERRORLEVEL%==0 (
    echo.
    echo [OK] Download concluido! Modelo salvo em:
    echo      %MODELS_DIR%\%FILE_NAME%
    echo.
    echo Inicie o start_portable.bat para usar o modelo.
) else (
    echo.
    echo [ERRO] Falha no download. Verifique a URL e sua conexao.
)

echo.
pause
