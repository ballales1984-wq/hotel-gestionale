@echo off
echo.
echo ==============================================
echo     Popolamento Dati Iniziali (Seed)
echo ==============================================
echo.

cd backend

echo [INFO] Attivazione ambiente virtuale...
call venv\Scripts\activate

echo [INFO] Esecuzione script di inserimento dati base...
python -m app.db.seed

echo.
echo [INFO] Finito! Ora puoi accedere con:
echo Email: admin@hotel-abc.it
echo Password: HotelABC2025!
echo.
pause
