@echo off
setlocal enabledelayedexpansion
title Listar Modelos - AI Stack Portable
cd /d "%~dp0"

set BASE_DIR=%~dp0
set MODELS_DIR=%BASE_DIR%data\models

echo ====================================================
echo    MODELOS GGUF DISPONIVEIS
echo ====================================================
echo.
echo Pasta: %MODELS_DIR%
echo.

set count=0
for /r "%MODELS_DIR%" %%f in (*.gguf) do (
    set /a count+=1
    echo  [!count!] %%~nxf
    echo       Pasta: %%~dpf
    echo       Tamanho: %%~zf bytes
    echo.
)

if %count%==0 (
    echo  Nenhum modelo .gguf encontrado.
    echo.
    echo  Use o download_model.bat para baixar um modelo,
    echo  ou copie um arquivo .gguf para data\models\
)

echo ====================================================
echo  Total: %count% modelo(s) encontrado(s)
echo ====================================================
echo.
pause
