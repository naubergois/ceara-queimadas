#!/usr/bin/env bash
# ─── Streamlit Dashboard: Queimadas Ceará ──────────────────────────────────
# Uso: bash scripts/run_dashboard.sh [port]
#
# Pré-requisitos:
#   pip install -r backend/app/dashboard/requirements-dash.txt
#
# O backend FastAPI deve estar rodando em http://localhost:8000
# (ou export API_BASE_URL=http://...)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PORT="${1:-8501}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "📡 Dashboard Queimadas Ceará"
echo "─────────────────────────────"
echo "• Porta : $PORT"
echo "• API   : ${API_BASE_URL:-http://localhost:8000}"
echo ""

cd "$SCRIPT_DIR"

# Verifica se streamlit está instalado
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit não encontrado. Instale com:"
    echo "   pip install -r backend/app/dashboard/requirements-dash.txt"
    exit 1
fi

# Verifica se a API está acessível
API_URL="${API_BASE_URL:-http://localhost:8000}"
if curl -sf "$API_URL/health" > /dev/null 2>&1; then
    echo "✅ API FastAPI respondendo em $API_URL"
else
    echo "⚠️  API FastAPI não está respondendo em $API_URL"
    echo "   Inicie o backend primeiro: uvicorn app.main:app --port 8000"
fi

echo ""
echo "🚀 Iniciando Streamlit..."
streamlit run backend/app/dashboard/dashboard.py \
    --server.port "$PORT" \
    --server.address "0.0.0.0" \
    --server.headless true \
    --browser.gatherUsageStats false
