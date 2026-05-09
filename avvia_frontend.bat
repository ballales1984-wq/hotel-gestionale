@echo off
echo.
echo ==============================================
echo     Avvio Frontend Hotel ABC Platform (No Docker)
echo ==============================================
echo.

cd frontend

if not exist "node_modules\" (
    echo [INFO] Prima installazione moduli Node in corso...
    npm install
)

echo.
echo [INFO] Avvio interfaccia React sulla porta 3000...
echo [INFO] Premi CTRL+C per arrestare.
echo.
npm run dev
