@echo off
setlocal
title Frontend - AI Stack Portable
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
echo   Iniciando Frontend HTML5 (Porta 8502)
echo ============================================
echo.

"%PYTHON_EXE%" app_web.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Ocorreu um erro ao iniciar o frontend.
    pause
)
