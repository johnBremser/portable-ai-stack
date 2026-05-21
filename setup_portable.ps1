# ================================================================
# SETUP PORTABLE AI STACK
# ================================================================
# Este script baixa o Python e o llama.cpp diretamente para o pendrive
# e configura o ambiente sem precisar de nada instalado no PC.
# ================================================================

$ErrorActionPreference = "Stop"
$BaseDir = $PSScriptRoot
$BinDir = "$BaseDir\bin"
$PyDir = "$BinDir\python"
$LlamaDir = "$BinDir\llama.cpp"
$DataDir = "$BaseDir\data"

Write-Host "--- Iniciando Setup Portatil ---" -ForegroundColor Cyan

# 1. Criar estrutura de pastas
Write-Host "[1/5] Criando pastas..."
if (-not (Test-Path $BinDir))                { New-Item -ItemType Directory -Path $BinDir                | Out-Null }
if (-not (Test-Path $DataDir))               { New-Item -ItemType Directory -Path $DataDir               | Out-Null }
if (-not (Test-Path "$DataDir\models"))      { New-Item -ItemType Directory -Path "$DataDir\models"      | Out-Null }
if (-not (Test-Path "$DataDir\attachments")) { New-Item -ItemType Directory -Path "$DataDir\attachments" | Out-Null }
if (-not (Test-Path $LlamaDir))              { New-Item -ItemType Directory -Path $LlamaDir              | Out-Null }

# 2. Baixar Python Embeddable (3.13.3)
if (-not (Test-Path "$PyDir\python.exe")) {
    Write-Host "[2/5] Baixando Python Embeddable (3.13.3)..." -ForegroundColor Yellow
    $PyUrl = "https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip"
    $PyZip = "$BinDir\python.zip"

    curl.exe -L $PyUrl -o $PyZip

    Write-Host "      Extraindo Python..."
    Expand-Archive -Path $PyZip -DestinationPath $PyDir -Force
    Remove-Item $PyZip

    # Habilitar o 'site-packages' (necessario no modo embedded)
    Write-Host "      Configurando caminhos do Python..."
    $PthFile = Get-ChildItem "$PyDir\*.pth" | Select-Object -First 1
    if ($PthFile) {
        (Get-Content $PthFile.FullName) -replace '#import site', 'import site' | Set-Content $PthFile.FullName
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
else {
    Write-Host "[3/5] PIP ja instalado." -ForegroundColor Green
}

# 4. Instalar Dependencias
Write-Host "[4/5] Instalando bibliotecas do requirements.txt..." -ForegroundColor Yellow
& "$PyDir\python.exe" -m pip install --no-cache-dir -r "$BaseDir\requirements.txt"

# 5. Baixar llama.cpp (ultima release do GitHub)
if (-not (Test-Path "$LlamaDir\llama-server.exe")) {
    Write-Host "[5/5] Baixando llama.cpp (ultima release do GitHub)..." -ForegroundColor Yellow

    $ApiUrl = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
    Write-Host "      Consultando GitHub API para ultima versao..."
    $Release = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "User-Agent" = "portable-ai-setup" }
    $Tag = $Release.tag_name
    Write-Host "      Versao encontrada: $Tag"

    # Preferencia: CUDA 12 -> CUDA 11 -> CPU (avx2)
    $Asset = $Release.assets | Where-Object { $_.name -match "win" -and $_.name -match "cuda12" -and $_.name -match "\.zip$" } | Select-Object -First 1
    if (-not $Asset) {
        $Asset = $Release.assets | Where-Object { $_.name -match "win" -and $_.name -match "cuda11" -and $_.name -match "\.zip$" } | Select-Object -First 1
    }
    if (-not $Asset) {
        $Asset = $Release.assets | Where-Object { $_.name -match "win" -and $_.name -match "avx2" -and $_.name -match "\.zip$" } | Select-Object -First 1
    }
    if (-not $Asset) {
        $Asset = $Release.assets | Where-Object { $_.name -match "win" -and $_.name -notmatch "vulkan" -and $_.name -match "\.zip$" } | Select-Object -First 1
    }

    if (-not $Asset) {
        Write-Host "      [ERRO] Nenhum asset compativel encontrado no release. Verifique manualmente:" -ForegroundColor Red
        Write-Host "      https://github.com/ggml-org/llama.cpp/releases/latest"
        pause
        exit 1
    }

    Write-Host "      Baixando: $($Asset.name)"
    $LlamaZip  = "$BinDir\llama.zip"
    $LlamaTemp = "$BinDir\llama_temp"

    curl.exe -L $Asset.browser_download_url -o $LlamaZip

    Write-Host "      Extraindo llama.cpp..."
    Expand-Archive -Path $LlamaZip -DestinationPath $LlamaTemp -Force
    Remove-Item $LlamaZip

    # Move todos os arquivos (exe + DLLs) para bin\llama.cpp\
    Get-ChildItem "$LlamaTemp" -Recurse -File | ForEach-Object {
        Move-Item $_.FullName "$LlamaDir\" -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $LlamaTemp -Recurse -Force

    Write-Host "      llama-server instalado em bin\llama.cpp\" -ForegroundColor Green
}
else {
    Write-Host "[5/5] llama.cpp ja instalado em bin/llama.cpp." -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host "  SETUP CONCLUIDO COM SUCESSO!                      " -ForegroundColor Green
Write-Host "  Coloque um modelo .gguf em data\models\           " -ForegroundColor Green
Write-Host "  e use start_portable.bat para iniciar sua IA.     " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
pause
