@echo off
title Configurando Local AI Stack Portable
cd /d "%~dp0"

echo [!] Iniciando configuracao automatica...
echo [!] Isso pode levar alguns minutos dependendo da sua internet.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "setup_portable.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRO] A instalacao falhou. Verifique sua conexao com a internet.
    pause
)
