#!/usr/bin/env bash
# =============================================================================
# start.sh — inicializa o ambiente e sobe o frontend Streamlit
# Execute após o backend já estar rodando (backend/start.sh)
# =============================================================================

set -e

VENV_DIR=".venv"
PORT=8502

echo ""
echo "============================================"
echo "  Local AI Stack — Frontend (HTML5)"
echo "============================================"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "[1/2] Criando ambiente virtual..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/2] Ambiente virtual já existe."
fi

source "$VENV_DIR/bin/activate"

echo "[2/2] Verificando dependências..."
# pip install -q -r requirements.txt # Não há dependências externas no momento

echo ""
echo "  Interface disponível em: http://localhost:$PORT"
echo "  Certifique-se de que o backend está rodando em: http://localhost:8000"
echo ""

export WEB_PORT=$PORT
python3 app_web.py
