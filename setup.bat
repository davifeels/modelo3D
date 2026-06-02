@echo off
echo ============================================
echo  3D Part Splitter - Setup do ambiente
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Python nao encontrado. Instale o Python 3.10+ e tente novamente.
    pause
    exit /b 1
)

echo [1/4] Criando ambiente virtual...
python -m venv venv
if %errorlevel% neq 0 (
    echo ERRO ao criar ambiente virtual.
    pause
    exit /b 1
)

echo [2/4] Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo [3/4] Atualizando pip...
python -m pip install --upgrade pip --quiet

echo [4/4] Instalando dependencias...
pip install PyQt5 pyvista pyvistaqt trimesh manifold3d numpy scipy shapely
if %errorlevel% neq 0 (
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup concluido com sucesso!
echo  Para rodar: execute run.bat
echo ============================================
pause
