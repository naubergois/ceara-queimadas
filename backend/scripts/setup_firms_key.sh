#!/bin/bash
# =============================================================================
# setup_firms_key.sh
#
# Configura a API Key do NASA FIRMS no .env do backend.
#
# USO:
#   1. Obtenha sua MAP_KEY gratuita em:
#      https://firms.modaps.eosdis.nasa.gov/api/map_key/
#      (insira seu email e a chave será enviada)
#
#   2. Execute este script:
#      ./scripts/setup_firms_key.sh SUA_CHAVE_AQUI
#
# A chave é uma string alfanumérica de 32 caracteres (ex: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"

if [ $# -lt 1 ]; then
    echo "Erro: informe a MAP_KEY como argumento."
    echo "Uso: $0 SUA_CHAVE_FIRMS"
    echo ""
    echo "Para obter uma chave: https://firms.modaps.eosdis.nasa.gov/api/map_key/"
    exit 1
fi

FIRMS_KEY="$1"

# Valida: chave deve ter 32 caracteres hex
if [[ ! "$FIRMS_KEY" =~ ^[a-f0-9]{32}$ ]]; then
    echo "⚠️  Aviso: a chave não parece ser uma MAP_KEY válida (32 caracteres hex)."
    echo "   A chave informada: $FIRMS_KEY"
    echo -n "   Continuar mesmo assim? [s/N] "
    read -r confirm
    if [[ ! "$confirm" =~ ^[sS]$ ]]; then
        echo "Abortado."
        exit 1
    fi
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Erro: .env não encontrado em $ENV_FILE"
    echo "Copie de .env.example primeiro: cp .env.example .env"
    exit 1
fi

# Verifica se já existe uma chave configurada
CURRENT_KEY=$(grep -oP '^NASA_FIRMS_API_KEY=\K.*' "$ENV_FILE" || true)
if [ -n "$CURRENT_KEY" ]; then
    echo "⚠️  Já existe uma chave FIRMS configurada."
    echo "   Atual: $CURRENT_KEY"
    echo -n "   Substituir? [s/N] "
    read -r confirm
    if [[ ! "$confirm" =~ ^[sS]$ ]]; then
        echo "Abortado."
        exit 1
    fi
fi

# Atualiza o .env
if grep -q '^NASA_FIRMS_API_KEY=' "$ENV_FILE"; then
    sed -i '' "s/^NASA_FIRMS_API_KEY=.*/NASA_FIRMS_API_KEY=$FIRMS_KEY/" "$ENV_FILE"
else
    echo "NASA_FIRMS_API_KEY=$FIRMS_KEY" >> "$ENV_FILE"
fi

echo "✅ FIRMS MAP_KEY configurada com sucesso!"
echo ""
echo "Para verificar:"
echo "  cd $BACKEND_DIR && python3 -c \"from app.core.config import settings; print('OK' if settings.NASA_FIRMS_API_KEY else 'FALHA')\""
echo ""
echo "Para testar a coleta via API:"
echo "  cd $BACKEND_DIR && python3 scripts/test_firms_api.py"
