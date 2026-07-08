#!/usr/bin/env bash
# Roda a suíte de testes num stack ISOLADO com banco EFÊMERO (docker-compose.
# test.yml). Sobe → pytest → derruba tudo. O banco de dev/produção (zefiro-db)
# nunca é tocado, então nada de usuário de teste aparece no /admin.
#
# Uso:
#   ./scripts/test.sh                      # suíte não-E2E (padrão)
#   ./scripts/test.sh tests/test_auth.py   # arquivo/args específicos do pytest
#   ./scripts/test.sh tests/               # tudo, incluindo E2E
#
# Precisa das portas 8000/5173 livres — pare o stack de dev antes:
#   docker compose down
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.test.yml"
PYTEST="${PYTEST:-web/backend/venv/Scripts/python.exe -m pytest}"

# Credenciais/segredos que a suíte espera (batem com o docker-compose.test.yml)
export ADMIN_EMAIL="${ADMIN_EMAIL:-davifeels23@gmail.com}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-ZefiroAdmin!f50077e3}"
export ZS_DEV_BILLING=1
export WEBHOOK_SECRET=test-secret
# MP_ACCESS_TOKEN (se exportado) habilita os testes reais do Mercado Pago.

cleanup() {
  echo "→ derrubando stack de teste (banco efêmero descartado)…"
  $COMPOSE down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "→ subindo stack de teste isolado (banco em RAM)…"
$COMPOSE up -d --build --wait

# Alvo padrão: tudo menos o test_e2e.py legado (a suíte E2E nova roda junto)
if [ "$#" -eq 0 ]; then
  set -- tests/ --ignore=tests/test_e2e.py
fi

echo "→ pytest $*"
$PYTEST "$@"
