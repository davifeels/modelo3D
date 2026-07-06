#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Criando ambiente virtual..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

echo "Iniciando servidor ZefiroSplit API em http://localhost:8000"
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
