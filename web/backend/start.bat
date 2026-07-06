@echo off
cd /d "%~dp0"

if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Iniciando servidor ZefiroSplit API em http://localhost:8000
echo Pressione Ctrl+C para encerrar.
echo.

uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-dir . --reload-dir ..\..\src
