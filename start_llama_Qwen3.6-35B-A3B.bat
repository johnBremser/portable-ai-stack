@echo off
setlocal enabledelayedexpansion
title llama.cpp - Qwen3.6

:: Caminhos
set BASE_DIR=%~dp0
set LLAMA_EXE=%BASE_DIR%bin\llama.cpp\llama-server.exe
set MODELS_DIR=%BASE_DIR%data\models

echo.
echo ===========================================
echo        Iniciando QWEN 3.6 35B
echo ===========================================
echo.

"%LLAMA_EXE%" --version

"%LLAMA_EXE%" ^
--host 0.0.0.0 ^
--port 8080 ^
--fit off ^
-c 262144 ^
-np 1 ^
-t 12 ^
-tb 12 ^
-fa on ^
--model "%MODELS_DIR%\Qwen3.6-35B-A3B-UD-IQ4_NL\Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf" ^
--mmproj "%MODELS_DIR%\Qwen3.6-35B-A3B-UD-IQ4_NL\mmproj-F16.gguf" ^
-ctk bf16 ^
-ctv bf16 ^
--jinja ^
--tools all ^
--models-max 1 ^
--metrics ^
--no-mmap ^
--no-warmup



::-c 32768 ^
:: Qwen3.6-35B-A3B-UD-IQ4_NL.gguf
:: Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf