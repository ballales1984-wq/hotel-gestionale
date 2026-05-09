@echo off
echo.
echo ==============================================
echo     Avvio Backend Hotel ABC Platform (No Docker)
echo ==============================================
echo.

cd backend

if not exist "venv\" (
    echo [INFO] Creazione ambiente virtuale con Python 3.12 in corso...
    py -3.12 -m venv venv
)

echo [INFO] Attivazione ambiente virtuale...
call venv\Scripts\activate

echo [INFO] Installazione dipendenze (potrebbe richiedere qualche minuto la prima volta)...
pip install -r requirements.txt
pip install -r requirements_ai.txt

echo.
echo [INFO] Avvio server FastAPI locale sulla porta 8000...
echo [INFO] Premi CTRL+C per arrestare.
echo.
uvicorn app.main:app --reload --port 8000
