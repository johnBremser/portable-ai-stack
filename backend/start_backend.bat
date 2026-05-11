@echo off
setlocal
title Backend - AI Stack Portable
cd /d "%~dp0"

:: Caminho para o Python portátil (sobe um nível para chegar na raiz, depois entra em bin\python)
set PYTHON_EXE=..\bin\python\python.exe

if not exist "%PYTHON_EXE%" (
    echo.
    echo [ERRO] Python portatil nao encontrado em: ..\bin\python\python.exe
    echo Certifique-se de que executou o setup_portable.bat primeiro.
    echo.
    pause
    exit /b
)

echo ============================================
echo   Iniciando Backend FastAPI (Porta 8500)
echo ============================================
echo.

"%PYTHON_EXE%" -m uvicorn api:app --host 0.0.0.0 --port 8500

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Ocorreu um erro ao iniciar o backend.
    pause
)
