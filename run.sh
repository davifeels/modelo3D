#!/usr/bin/env bash
# Inicia o ZefiroSplit (Linux / macOS)

set -e

if [ ! -d "venv" ]; then
    echo "Ambiente virtual não encontrado. Execute ./setup.sh primeiro."
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

# Necessário no Linux para PyVista/VTK com offscreen rendering
export QT_XCB_GL_INTEGRATION=none 2>/dev/null || true

python main.py "$@"
