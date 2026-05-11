# Hotel ABC Platform — Runbook Operativo

## Stato attuale (dopo setup completo)

- **Backend**: FastAPI in ascolto su `http://localhost:8000`
- **Database**: SQLite (`backend/hotel_abc.db`) con dati reali
- **Frontend**: React (Vite) su `http://localhost:3000` (da avviare)
- **Dati**: 11 periodi contabili (mag 2025 – apr 2026), 66 risultati ABC, 99 driver values per AI

## Avvio rapido (senza Docker)

### 1. Backend
```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Verifica: `http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`

### 2. Frontend (in un altro terminale)
```powershell
cd frontend
npm install  # la prima volta
npm run dev
```
Apri `http://localhost:3000`

### 3. API Endpoints principali

| Endpoint | Descrizione |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/periods/` | Lista periodi contabili |
| `GET /api/v1/services/` | Lista servizi |
| `GET /api/v1/activities/` | Lista attività |
| `GET /api/v1/costs/{period_id}` | Voci di costo per periodo |
| `GET /api/v1/labor/{period_id}` | Allocazioni personale |
| `POST /api/v1/reports/calculate/{period_id}` | Calcola ABC per periodo (salva in background) |
| `GET /api/v1/reports/abc/{period_id}` | Risultati ABC per periodo |
| `GET /api/v1/ai/driver-discovery` | Driver discovery (raccomandazioni) |
| `GET /api/v1/ai/forecast?metric=notti_vendute&periods=6` | Forecasting metriche |
| `GET /api/v1/ai/anomalies` | Anomaly detection |
| `GET /api/v1/imports/accounting` | Import contabilità (CSV/Excel) |
| `GET /api/v1/mapping/rules` | CRUD mapping rules |

### 4. Script di utilità (da cartella `backend/scripts/`)

| Script | Descrizione |
|--------|-------------|
| `setup_all.py` | Inizializzazione completa DB (migrazione, seed, storico, driver values, calcoli ABC) |
| `migrate_to_multitenancy.py` | Aggiunge schema multi-tenant (tabelle hotels) |
| `populate_min_history.py` | Genera 12 mesi di dati contabili (costi, lavoro, ricavi) |
| `populate_presumed_costs.py` | Aggiunge costi presunti e regole Costo→Attività per ultimo periodo |
| `populate_driver_values.py` | Genera valori driver (notti, coperti, ore, camere) per AI |
| `calculate_all_periods.py` | Ricalcola ABC per tutti i periodi (dopo modifiche) |
| `run_abc_calculation.py` | Calcola ABC per il periodo più recente (singolo) |

**Esempio: setup completo da zero (SQLite)**
```powershell
cd backend
python -m scripts.setup_all
```

## Docker (stack completo)

```bash
# Build e avvio
docker-compose up -d

# Verifica servizi
docker-compose ps

# Logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop
docker-compose down
```

Servizi esposti:
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Superset (BI): http://localhost:8088
- PostgreSQL: localhost:5432 (user: `hotel_user`, password: da `.env`)

## Database

### Schema principali
- `hotels` – tenant (multi-tenancy)
- `accounting_periods` – periodi contabili (chiusura)
- `cost_centers` – centri di costo
- `activities` – attività operative
- `services` – servizi offerti
- `cost_items` – voci di costo (da contabilità)
- `labor_allocations` – ore/dipendent per attività
- `service_revenues` – ricavi per servizio
- `allocation_rules` – regole di ribaltamento ABC
- `abc_results` – risultati calcoli ABC
- `driver_values` – valori driver per AI
- `mapping_rules` – regole mapping codici esterni
- `data_import_logs` – storico import

### Query utili

```sql
-- Periodi e risultati ABC
SELECT p.name, COUNT(a.id) as num_results
FROM accounting_periods p
LEFT JOIN abc_results a ON a.period_id = p.id
GROUP BY p.id ORDER BY p.year DESC, p.month DESC;

-- Driver values per periodo
SELECT d.name, SUM(dv.value) as total
FROM driver_values dv
JOIN cost_drivers d ON dv.driver_id = d.id
WHERE dv.period_id = '<period_id>'
GROUP BY dv.driver_id;
```

## AI & Forecasting

- **Driver Discovery**: `GET /api/v1/ai/driver-discovery` – suggerisce driver per attività/servizi basandosi su correlazione storica.
- **Forecasting**: `GET /api/v1/ai/forecast?metric=notti_vendute&periods=6` – previsione metriche (LightGBM).
- **Anomaly Detection**: `GET /api/v1/ai/anomalies` – rileva outlier nei dati storici.

Dati necessari: `driver_values` (almeno 10 periodi). Attualmente: 11 periodi → OK.

## Troubleshooting

### Backend non parte
- Verifica `.env` presente in `backend/` con `DATABASE_URL` (opzionale, default SQLite)
- Installa dipendenze: `pip install -r requirements.txt`
- Assicurati che la porta 8000 sia libera

### Frontend build fallisce
- `rm -rf node_modules package-lock.json && npm install`
- Verifica `VITE_API_URL` in `.env` (frontend) punti a `http://localhost:8000`

### Errori ABC (risultati vuoti)
- Esegui `scripts/setup_all.py` per rigenerare dati
- Verifica che esistano `cost_items`, `labor_allocations`, `service_revenues` per il periodo
- controlla regole `allocation_rules` attive

### Multi-tenancy
- Hotel default: `DEMO` (creato da migrate_to_multitenancy.py)
- Tutte le query devono filtrare per `hotel_id` (incluso negli import)

## Note sviluppo

- **Python**: 3.11+ (consigliato 3.12)
- **Node**: 18+ LTS
- **Database**: SQLite per sviluppo, PostgreSQL per produzione
- **AI Models**: LightGBM, Prophet, IsolationForest (installare con `pip install lightgbm prophet scikit-learn`)

## Prossimi step

- [ ] Docker: far girare stack completo (Postgres, Redis, Backend, Frontend, Superset)
- [ ] Test suite completa (pytest)
- [ ] Documentazione API Swagger interattiva: http://localhost:8000/docs
- [ ] Integrazione PMS reale (CSV/API)
- [ ] Export report Excel/PDF

---

**Ultimo aggiornamento**: 2026-05-11  
**Versione**: 0.4.0-dev
