@echo off
if not exist venv (
    echo Ambiente virtual nao encontrado. Execute setup.bat primeiro.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python main.py
