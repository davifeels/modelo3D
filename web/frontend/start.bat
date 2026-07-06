@echo off
cd /d "%~dp0"

where npm >nul 2>&1
if errorlevel 1 (
    echo Node.js nao encontrado. Instale em https://nodejs.org
    pause
    exit /b 1
)

if not exist node_modules (
    echo Instalando dependencias...
    npm install
)

echo.
echo Iniciando frontend ZefiroSplit em http://localhost:5173
echo Pressione Ctrl+C para encerrar.
echo.

npm run dev
