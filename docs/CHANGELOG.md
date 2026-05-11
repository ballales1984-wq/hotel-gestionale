# Changelog

Tutte le modifiche importanti a questo progetto saranno documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
e questo progetto mantiene il [Versionamento Semantico](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Aggiunto
- Documentazione completa per GitHub (`README.md` aggiornato)
- Cartella `docs/` con guide dettagliate:
  - Installazione e configurazione
  - Guida utente
  - API Reference
  - Architettura tecnica
  - Manutenzione e troubleshooting
  - Schema database
  - FAQ

---

## [0.1.0] - 2025-01-15

### Aggiunto
- Motore ABC a 3 livelli (costi → attività → servizi)
- API FastAPI con autenticazione JWT
- Frontend React con dashboard interattiva
- Import CSV per contabilità, payroll e ricavi
- Supporto AI/ML:
  - Driver discovery con Random Forest + SHAP
  - Forecasting con Prophet
  - Anomaly detection con Isolation Forest
- Apache Superset per BI avanzato
- ETL worker con Prefect
- Supporto Docker Compose per sviluppo e produzione

### Tecnologie
- Python 3.11+, FastAPI, SQLAlchemy async
- React 18, Vite, Material UI, Recharts
- PostgreSQL 16, Redis 7
- LightGBM, Prophet, SHAP