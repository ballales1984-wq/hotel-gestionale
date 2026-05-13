# 🚀 Avvio Applicazione — Hotel Gestionale ABC

## Prerequisiti
- Docker Desktop installato e in esecuzione
- Git (per clonare il repository)
- Node.js 20+ (solo per sviluppo frontend locale senza Docker)

---

## 1. Avvio con Docker Compose (consigliato)

Da **PowerShell** nella radice del progetto:

```powershell
# Assicurati che Docker Desktop sia in esecuzione (icona nella system tray)
# Poi avvia tutti i servizi in background:
docker-compose up -d

# Verifica che i container siano attivi:
docker-compose ps

# Log in tempo reale (opzionale):
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Servizi avviati:
| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| `backend` | `http://localhost:8000` | API FastAPI (docs: `/docs`) |
| `frontend` | `http://localhost:3000` | React App |
| `postgres` | `localhost:5432` | Database |
| `redis` | `localhost:6379` | Cache/Queue |
| `superset` | `http://localhost:8088` | BI (admin/admin) |
| `prometheus` | `http://localhost:9090` | Metrics |
| `grafana` | `http://localhost:3001` | Dashboards (admin/admin) |
| `nginx` | `http://localhost:80` | Reverse proxy |

---

## 2. Stop / Reset

```powershell
# Stop tutti i servizi
docker-compose down

# Stop + rimuove volumi (database verrà cancellato!)
docker-compose down -v

# Ricostruisci immagini (dopo modifiche a Dockerfile/requirements)
docker-compose build --no-cache
docker-compose up -d
```

---

## 3. Avvio Sviluppo (senza Docker, solo backend + frontend separati)

### Backend ( Python + Uvicorn )
```powershell
cd backend

# Crea ambiente virtuale
python -m venv venv
.\venv\Scripts\Activate.ps1  # PowerShell
# oppure: venv\Scripts\Activate.bat  # CMD

# Installa dipendenze
pip install -r requirements.txt -r requirements_ai.txt

# Variabili d'ambiente (crea .env da .env.example)
copy .env.example .env
# Modifica .env se necessario (soprattutto ENCRYPTION_KEY, DATABASE_URL)

# Avvia DB PostgreSQL locale (opzionale, se non usi Docker)
# Usa docker-compose per il DB: docker-compose up postgres -d

# Esegui migrazioni (se presenti)
# python -m alembic upgrade head

# Avvia backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Docs disponibili: http://localhost:8000/docs
```

### Frontend ( Node.js + Vite )
```powershell
cd frontend

# Installa dipendenze
npm install

# Variabili d'ambiente (crea .env se non esiste)
# VITE_API_URL=http://localhost:8000/api/v1

# Avvia dev server
npm run dev
# Accesso: http://localhost:5173 (o 3000 se configurato)
```

---

## 4. Esecuzione Test

```powershell
cd backend

# Installa pytest
pip install pytest pytest-asyncio

# Esegui tutti i test
pytest -v

# Test specifici
pytest tests/test_pms_sync.py -v
pytest tests/test_data_fetcher_multitenancy.py -v
pytest tests/test_monitoring_config.py -v

# Con coverage (opzionale)
pip install pytest-cov
pytest --cov=app --cov-report=html
```

---

## 5. Script Utilità

```powershell
# Backup database (SQLite)
python scripts/backup_db.py

# Popola dati di esempio (seed)
python backend/scripts/generate_sample_data.py

# Verifica connessione DB
python backend/scripts/check_db.py
```

---

## 6. Risoluzione Problemi Comuni

| Problema | Soluzione |
|----------|-----------|
| `docker-compose up` fallisce su Windows | Verifica che Docker Desktop sia in esecuzione e che WSL2 sia installato |
| Porta 8000/3000 già in uso | Cambia porte in `docker-compose.yml` o ferma il processo che occupa la porta (`netstat -ano \| findstr :8000`) |
| Errore `ENCRYPTION_KEY` mancante | Genera con `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` e copia in `.env` |
| Frontend non raggiunge backend | Imposta `VITE_API_URL=http://localhost:8000/api/v1` in `frontend/.env` |
| Database vuoto | Esegui lo script seed: `python backend/scripts/generate_sample_data.py` o usa l'endpoint `/api/v1/imports/accounting` con file di esempio |

---

## 7. Verifica Installazione

Una volta avviato:
1. **Backend API**: http://localhost:8000/docs (Swagger UI)
2. **Frontend**: http://localhost:3000
3. **Login**: admin@hotel-abc.it / admin123 (o il seed generato)
4. **Database**: connettiti a `postgres:5432` con user/password da `.env`

---

## 🎯 Checklist post-avvio
- [ ] Docker Desktop in esecuzione
- [ ] `docker-compose up -d` completato senza errori
- [ ] Contenitori `backend` e `frontend` in stato `Up`
- [ ] Backend risponde a `/docs`
- [ ] Frontend caricato presso `http://localhost:3000`
- [ ] Login funzionante
- [ ] Pagina **Cost Centers** e **Cost Drivers** accessibili
- [ ] AI Insights carica grafici (con `hotel_id` selezionato— attualmente manca il selettore hotel nella UI, da aggiungere in futuro)

---

**Nota**: Alcune feature (PMS sync, import CSV) richiedono file di configurazione aggiuntivi o dati seed. Vedi documentazione in `FULL_DOCUMENTATION.md`.
