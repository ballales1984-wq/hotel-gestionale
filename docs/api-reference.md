# API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Autenticazione

Tutti gli endpoint (eccetto `/auth/login`) richiedono l'autenticazione tramite token Bearer JWT.

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin@hotel-abc.it",
  "password": "HotelABC2025!"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Headers richiesti

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

## Endpoints

### Periodi contabili

#### Lista periodi

```http
GET /periods
```

**Response:**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "2025-Q1",
    "start_date": "2025-01-01",
    "end_date": "2025-03-31",
    "status": "active"
  }
]
```

#### Crea periodo

```http
POST /periods
{
  "name": "2025-Q2",
  "start_date": "2025-04-01",
  "end_date": "2025-06-30"
}
```

#### Dettaglio periodo

```http
GET /periods/{period_id}
```

### Costi

#### Lista costi

```http
GET /costs?period_id={period_id}
```

#### Crea costo

```http
POST /costs
{
  "period_id": "uuid",
  "cost_center_id": "uuid",
  "cost_type": "personale",
  "amount": 45000.00,
  "description": "Stipendi Reception"
}
```

### Allocazioni

#### Lista allocazioni

```http
GET /allocations?period_id={period_id}
```

#### Crea allocazione

```http
POST /allocations
{
  "period_id": "uuid",
  "level": "costo_ad_attivita",
  "source_cost_center_id": "uuid",
  "target_activity_id": "uuid",
  "driver_values": {"activity_id": 1000},
  "allocation_pct": 0.5
}
```

### Simulazione ABC

#### Esegui calcolo

```http
POST /simulation/run
{
  "period_id": "uuid"
}
```

**Response:**

```json
{
  "period_id": "uuid",
  "status": "completed",
  "total_cost": 1250000.00,
  "total_revenue": 1850000.00,
  "total_margin": 600000.00,
  "service_results": [
    {
      "service_id": "uuid",
      "service_name": "Camera Doppia",
      "revenue": 500000.00,
      "total_cost": 350000.00,
      "gross_margin": 150000.00,
      "margin_pct": 30.0
    }
  ]
}
```

### Report

#### KPI dashboard

```http
GET /reports/kpi?period_id={period_id}
```

**Response:**

```json
{
  "total_revenue": 1850000.00,
  "total_cost": 1250000.00,
  "total_margin": 600000.00,
  "total_margin_pct": 32.43,
  "labor_cost_incidence_pct": 45.2
}
```

#### Report completo

```http
GET /reports?period_id={period_id}
```

### AI Endpoints

#### Driver Discovery

```http
GET /ai/driver-discovery
```

**Response:**

```json
[
  {
    "driver_name": "ore_lavorate",
    "importance_pct": 45.5,
    "confidence_score": "Alta",
    "explanation": "Correlazione forte con i costi overhead"
  }
]
```

#### Forecast

```http
GET /ai/forecast?metric=notti_vendute&periods=6
```

**Response:**

```json
[
  {
    "date": "2025-06-01",
    "predicted_value": 125.5,
    "lower_bound": 110.0,
    "upper_bound": 140.0
  }
]
```

#### Anomaly Detection

```http
GET /ai/anomalies
```

**Response:**

```json
[
  {
    "record_id": "P-10",
    "anomaly_score": 0.95,
    "root_cause_driver": "costo_lavoro",
    "explanation": "Costo lavoro anomalo per il volume"
  }
]
```

## Codici di errore

| Codice | Descrizione |
|--------|-------------|
| 400 | Bad Request - Dati non validi |
| 401 | Unauthorized - Token mancante o scaduto |
| 403 | Forbidden - Permessi insufficienti |
| 404 | Not Found - Risorsa non trovata |
| 500 | Internal Server Error |

## Rate Limiting

- 100 richieste/minuto per IP
- 1000 richieste/minuto per utente autenticato

## Schema OpenAPI

Lo schema OpenAPI è disponibile all'indirizzo:
```
http://localhost:8000/api/openapi.json
```

La documentazione Swagger interattiva è disponibile all'indirizzo:
```
http://localhost:8000/api/docs
```