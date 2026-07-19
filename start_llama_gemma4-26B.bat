@echo off
setlocal enabledelayedexpansion
title llama.cpp - Gemma 4

:: Caminhos
set BASE_DIR=%~dp0
set LLAMA_EXE=%BASE_DIR%bin\llama.cpp\llama-server.exe
set MODELS_DIR=%BASE_DIR%data\models

echo.
echo ===========================================
echo        Iniciando Gemma 4 26B
echo ===========================================
echo.

"%LLAMA_EXE%" --version

"%LLAMA_EXE%" ^
--host 0.0.0.0 ^
--port 8080 ^
--fit off ^
-c 32768 ^
-np 1 ^
-t 12 ^
-tb 12 ^
-fa on ^
--model "%MODELS_DIR%\gemma-4-26B-A4B-it-qat-UD-Q4_K_XL\gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf" ^
--mmproj "%MODELS_DIR%\gemma-4-26B-A4B-it-qat-UD-Q4_K_XL\mmproj-BF16.gguf" ^
-ctk bf16 ^
-ctv bf16 ^
--jinja ^
--tools all ^
--models-max 1 ^
--metrics ^
--no-mmap ^
--no-warmup


::--model-draft "%MODELS_DIR%\gemma-4-26B-A4B-it-qat-UD-Q4_K_XL\mtp-gemma-4-26B-A4B-it.gguf" ^
::--spec-type draft-mtp ^
::--spec-draft-n-max 4 ^