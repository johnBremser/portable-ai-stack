#!/usr/bin/env bash
# =============================================================================
# test_api.sh — testa os endpoints do backend manualmente
# Execute após o servidor estar rodando (ex.: uvicorn api:app --port 8500)
#
# Nota: /chat e /chat/upload agora retornam SSE streaming.
#       Os testes usam curl para pegar os primeiros tokens e validar conexão.
# =============================================================================

BASE="http://localhost:8500"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'

echo ""
echo -e "${CYAN}=== TESTE 1: Health Check ===${NC}"
curl -s "$BASE/health" | python3 -m json.tool

echo ""
echo -e "${CYAN}=== TESTE 2: Listar Modelos ===${NC}"
curl -s "$BASE/models" | python3 -m json.tool

echo ""
echo -e "${CYAN}=== TESTE 3: Chat SSE (primeiros 500 chars) ===${NC}"
curl -s -X POST "$BASE/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "O que é um Large Language Model? Responda em 2 frases.",
    "model": "gemma4:e2b",
    "temperature": 0.7
  }' | head -c 500

echo ""
echo ""
echo -e "${CYAN}=== TESTE 4: Histórico da sessão (DELETE /sessions primeiro para limpar) ===${NC}"
curl -s -X DELETE "$BASE/sessions" | python3 -m json.tool

# Faz uma requisição completa (sem head) para gerar sessão, depois pega o session_id do primeiro evento
RESP=$(curl -s -X POST "$BASE/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Diga apenas OK.",
    "model": "gemma4:e2b"
  }')
SESSION_ID=$(echo "$RESP" | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data: '):
        d = json.loads(line[6:])
        if d.get('session_id'):
            print(d['session_id'])
            break
")

if [ -n "$SESSION_ID" ]; then
    echo -e "${CYAN}      Session ID extraído: $SESSION_ID${NC}"
    echo ""
    echo -e "${CYAN}=== TESTE 5: Histórico da sessão ===${NC}"
    curl -s "$BASE/session/$SESSION_ID" | python3 -m json.tool
fi

echo ""
echo -e "${CYAN}=== TESTE 6: Chat SSE com thinking (primeiros 500 chars) ===${NC}"
curl -s -X POST "$BASE/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explique o mecanismo de atenção dos Transformers.",
    "model": "gemma4:e2b",
    "think": true
  }' | head -c 500

echo ""
echo ""
echo -e "${GREEN}Testes concluídos.${NC}"
echo ""
