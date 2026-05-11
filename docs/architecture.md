# Architettura Tecnica

## Stack tecnologico

### Backend

| Tecnologia | Versione | Scopo |
|------------|----------|-------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.111 | Framework API |
| SQLAlchemy | 2.0 | ORM |
| PostgreSQL | 16 | Database |
| Redis | 7 | Cache |
| Polars | 1.0+ | Elaborazione dati |
| LightGBM | 4.3+ | ML engine |
| Prophet | 1.1+ | Forecasting |

### Frontend

| Tecnologia | Versione | Scopo |
|------------|----------|-------|
| React | 18 | UI Library |
| Vite | 5 | Build tool |
| Material UI | 5 | Componenti |
| Recharts | 2.12 | Grafici |
| Zustand | 4.5 | State management |
| React Query | 5 | Data fetching |

### Infrastruttura

| Tecnologia | Scopo |
|------------|-------|
| Docker | Containerizzazione |
| Docker Compose | Orchestrazione |
| Nginx | Reverse proxy |
| Apache Superset | BI & Analytics |
| Prefect | ETL orchestration |

## Diagramma architettura

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
│                      (React + Vite)                           │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────────────────┐
│                      Nginx Reverse Proxy                       │
│                   (Port 80/443)                              │
└─────────────┬──────────────┬───────────────┬─────────────────┘
              │              │               │
     ┌────────▼─┐    ┌───────▼───┐   ┌───────▼────────┐
     │ Frontend │    │  Backend  │   │   Superset     │
     │  :3000   │    │   :8000   │   │    :8088       │
     └──────────┘    └───────┬───┘   └────────────────┘
                             │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
  ┌─────▼─────┐        ┌─────▼─────┐        ┌───────▼──────┐
  │ Postgres  │        │   Redis   │        │ ETL Worker   │
  │   :5432   │        │   :6379   │        │ (Prefect)    │
  └───────────┘        └───────────┘        └──────────────┘
```

## Componenti principali

### ABCEngine (backend/app/core/abc_engine.py)

Motore principale per il calcolo ABC. Implementa 3 fasi:

1. **Phase 1 - Costi diretti**
   - `CostRecord` → allocazione su `ActivityCost`
   - `LaborRecord` → costi orari diretti

2. **Phase 2 - Ribaltamento supporto**
   - Attività di supporto → attività primarie
   - Algoritmo iterativo con convergenza

3. **Phase 3 - Allocazione a servizi**
   - `ActivityCost` → `ServiceResult`
   - Driver-based allocation

### AI Engine (backend/app/core/ai/)

| Modulo | Funzione |
|--------|----------|
| `driver_discovery.py` | Random Forest + SHAP per feature importance |
| `forecasting.py` | Prophet per previsioni con stagionalità |
| `anomaly_detection.py` | Isolation Forest per outlier detection |
| `data_fetcher.py` | Estrazione dati dal database |

### Modelli database

Entità principali:
- `Period` - Periodo contabile
- `CostCenter` - Centro di costo
- `Activity` - Attività
- `Service` - Servizio
- `CostRecord` - Registro costi
- `AllocationRule` - Regola di allocazione
- `ABCResult` - Risultato calcolo

## Flusso dati

```
CSV Upload
    ↓
Parser & Validazione
    ↓
PostgreSQL
    ↓
ABC Engine (3 fasi)
    ↓
ABCResult
    ↓
┌────────────┴────────────┐
│                         │
▼                         ▼
Dashboard              Superset
React                  BI Reports
```

## Sicurezza

- **Autenticazione**: JWT con refresh token
- **Autorizzazione**: RBAC (Role-Based Access Control)
- **CORS**: Configurabile via environment
- **HTTPS**: Obbligatorio in produzione

## Performance

- **Database pooling**: SQLAlchemy async
- **Cache**: Redis per rate limiting e sessioni
- **Query optimization**: Polars per elaborazione dati
- **Background tasks**: Prefect per ETL

## Monitoring

- **Health check**: `/health` endpoint
- **Metrics**: Prometheus su `/metrics`
- **Logging**: JSON structured via structlog