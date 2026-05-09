# Hotel ABC Platform

Piattaforma decisionale Activity-Based Costing (ABC/ABS) per hotel multiservizio.

## Quick Start

### Prerequisiti
- Docker Desktop
- Docker Compose v2

### 1. Configurazione ambiente

```bash
cp .env.example .env
# Modifica le password in .env
```

### 2. Avvio stack completo

```bash
docker-compose up -d
```

### 3. Seed dati iniziali (prima volta)

```bash
docker-compose exec backend python -m app.db.seed
```

### 4. Accesso

| Servizio | URL | Credenziali default |
|---|---|---|
| Frontend React | http://localhost:3000 | admin@hotel-abc.it / HotelABC2025! |
| API Docs (Swagger) | http://localhost:8000/api/docs | — |
| Apache Superset BI | http://localhost:8088 | admin / admin |

---

## Struttura progetto

```
hotel-abc-platform/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # Router FastAPI
│   │   ├── core/abc_engine.py  # Motore ABC
│   │   ├── db/                 # Database + seed
│   │   └── models/models.py    # SQLAlchemy models
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/              # Pagine React
│       ├── lib/api.js          # Client API
│       └── store/authStore.js  # Auth state
├── infra/
│   └── postgres/init.sql
├── docker-compose.yml
└── .env.example
```

---

## Flusso dati ABC

```
Import CSV (contabilità + payroll + ricavi)
    → Database PostgreSQL
    → Motore ABC (Fase 1: Costi→Attività | Fase 2: Supporto→Primarie | Fase 3: Attività→Servizi)
    → ABCResult (costi, ricavi, margini per servizio)
    → Dashboard React + Apache Superset
```

---

## Formato file CSV

### Contabilità
```
conto,descrizione,centro_di_costo,tipo_costo,importo
6010,Stipendi Reception,CC-REC,personale,45000
```

### Payroll
```
matricola,nome,attivita,ore,costo_orario,percentuale
001,Mario Rossi,REC-001,120,18.50,0.60
```

### Ricavi
```
servizio,ricavo,volume
SVC-PNT,280000,1450
```

---

## Credenziali default (cambiare in produzione)

- **Admin**: admin@hotel-abc.it / HotelABC2025!
- **Direzione**: direzione@hotel-abc.it / Direzione2025!
