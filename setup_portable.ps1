# ================================================================
# SETUP PORTABLE AI STACK
# ================================================================
# Este script baixa o Python e o Ollama diretamente para o pendrive
# e configura o ambiente sem precisar de nada instalado no PC.
# ================================================================

$ErrorActionPreference = "Stop"
$BaseDir = $PSScriptRoot
$BinDir = "$BaseDir\bin"
$PyDir = "$BinDir\python"
$DataDir = "$BaseDir\data"

Write-Host "--- Iniciando Setup Portatil ---" -ForegroundColor Cyan

# 1. Criar estrutura de pastas
Write-Host "[1/5] Criando pastas..."
if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir | Out-Null }
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir | Out-Null }
if (-not (Test-Path "$DataDir\models")) { New-Item -ItemType Directory -Path "$DataDir\models" | Out-Null }

# 2. Baixar Python Embeddable (3.13.13)
#https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip
if (-not (Test-Path "$PyDir\python.exe")) {
    Write-Host "[2/5] Baixando Python Embeddable (3.13.13)..." -ForegroundColor Yellow
    $PyUrl = "https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip"
    $PyZip = "$BinDir\python.zip"
    
    curl.exe -L $PyUrl -o $PyZip
    
    Write-Host "      Extraindo Python..."
    Expand-Archive -Path $PyZip -DestinationPath $PyDir -Force
    Remove-Item $PyZip
    
    # Habilitar o 'site-packages' (necessario no modo embedded)
    Write-Host "      Configurando caminhos do Python..."
    $PthFile = "$PyDir\python313._pth"
    if (Test-Path $PthFile) {
        (Get-Content $PthFile) -replace '#import site', 'import site' | Set-Content $PthFile
    }
}
else {
    Write-Host "[2/5] Python ja instalado em bin/python." -ForegroundColor Green
}

# 3. Instalar PIP
if (-not (Test-Path "$PyDir\Scripts\pip.exe")) {
    Write-Host "[3/5] Instalando PIP gerenciador de pacotes..." -ForegroundColor Yellow
    $GetPip = "$PyDir\get-pip.py"
    curl.exe -L "https://bootstrap.pypa.io/get-pip.py" -o $GetPip
    & "$PyDir\python.exe" $GetPip
    Remove-Item $GetPip
}

# 4. Instalar Dependencias
Write-Host "[4/5] Instalando bibliotecas do requirements.txt..." -ForegroundColor Yellow
& "$PyDir\python.exe" -m pip install --no-cache-dir -r "$BaseDir\requirements.txt"

# 5. Baixar Ollama
if (-not (Test-Path "$BinDir\ollama-windows.exe")) {
    Write-Host "[5/5] Baixando Ollama Engine..." -ForegroundColor Yellow
    $OllamaUrl = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
    $OllamaZip = "$BinDir\ollama.zip"
    $OllamaTemp = "$BinDir\ollama_temp"
    
    curl.exe -L $OllamaUrl -o $OllamaZip
    
    Write-Host "      Extraindo Ollama..."
    Expand-Archive -Path $OllamaZip -DestinationPath $OllamaTemp -Force
    Move-Item "$OllamaTemp\ollama.exe" "$BinDir\ollama-windows.exe" -Force
    
    # Limpeza
    Remove-Item $OllamaZip
    Remove-Item $OllamaTemp -Recurse -Force
}
else {
    Write-Host "[5/5] Ollama ja esta em bin/ollama-windows.exe." -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host "  SETUP CONCLUIDO COM SUCESSO!                      " -ForegroundColor Green
Write-Host "  Use o start_portable.bat para iniciar sua IA.     " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
pause
