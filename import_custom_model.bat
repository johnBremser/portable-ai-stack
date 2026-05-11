@echo off
setlocal enabledelayedexpansion
title Importar Modelo GGUF - Local AI Stack
cd /d "%~dp0"

set BASE_DIR=%~dp0
set OLLAMA_EXE=%BASE_DIR%bin\ollama-windows.exe
set MODELS_DIR=%BASE_DIR%data\models

:: Configura o caminho de dados do Ollama para o pendrive
set OLLAMA_MODELS=%MODELS_DIR%\ollama_data
set OLLAMA_HOST=127.0.0.1:11434

echo ====================================================
echo    IMPORTAR MODELO CUSTOMIZADO (Hugging Face)
echo ====================================================
echo.

if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

echo Procurando arquivos .gguf em: %MODELS_DIR%
echo.

set count=0
for %%f in ("%MODELS_DIR%\*.gguf") do (
    set /a count+=1
    set "file!count!=%%~nxf"
    echo [!count!] %%~nxf
)

if %count%==0 (
    echo [!] Nenhum arquivo .gguf encontrado na pasta data/models.
    echo [!] Baixe o modelo do Hugging Face e coloque-o la primeiro.
    pause
    exit /b
)

echo.
set /p choice="Escolha o numero do modelo para importar: "

if not defined file%choice% (
    echo [ERRO] Escolha invalida.
    pause
    exit /b
)

set "selected_file=!file%choice%!"
set /p model_name="Dê um nome para este modelo no Ollama: "

echo.
echo [1/2] Criando Modelfile temporario...
echo FROM ./!selected_file! > "%MODELS_DIR%\temp_modelfile"

echo [2/2] Importando para o Ollama (isso pode demorar um pouco)...
cd /d "%MODELS_DIR%"
"%OLLAMA_EXE%" create %model_name% -f temp_modelfile

del temp_modelfile
echo.
echo [!] Sucesso! O modelo '%model_name%' ja pode ser usado no chat.
pause
