@echo off
echo =============================================
echo   ZefiroSplit - Iniciando Backend + Frontend
echo =============================================
echo.

REM Inicia backend em janela separada
start "ZefiroSplit Backend" cmd /k "cd /d "%~dp0backend" && start.bat"

REM Aguarda backend iniciar
timeout /t 4 /nobreak >nul

REM Inicia frontend
start "ZefiroSplit Frontend" cmd /k "cd /d "%~dp0frontend" && start.bat"

REM Abre o browser
timeout /t 6 /nobreak >nul
start http://localhost:5173

echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Feche as janelas do terminal para encerrar.
