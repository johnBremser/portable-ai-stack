@echo off
setlocal
title Configurar Usuario Git - Local
cd /d "%~dp0"

echo ============================================
echo   Configurando Usuario Git Local
echo ============================================
echo.

set /p GIT_NAME="Digite o Nome (ex: johnBremser): "
set /p GIT_EMAIL="Digite o Email: "

if "%GIT_NAME%"=="" goto erro
if "%GIT_EMAIL%"=="" goto erro

git config --local user.name "%GIT_NAME%"
git config --local user.email "%GIT_EMAIL%"

echo.
echo [!] Configurado com sucesso para este repositório!
echo Nome:  %GIT_NAME%
echo Email: %GIT_EMAIL%
echo.
pause
exit /b

:erro
echo [ERRO] Nome e Email sao obrigatorios.
pause
