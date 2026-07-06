#!/usr/bin/env bash
# Setup para Linux e macOS

set -e

PYTHON="${PYTHON:-python3}"

echo "=== ZefiroSplit — Setup ==="
echo "Python: $($PYTHON --version)"

# Cria venv se não existir
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    $PYTHON -m venv venv
fi

echo "Ativando ambiente virtual..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "Instalando dependências..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo ""
echo "=== Setup concluído! ==="
echo "Para iniciar: ./run.sh"
