# Guida Utente

## Primo accesso

1. Apri il browser e vai su `http://localhost:3000`
2. Accedi con le credenziali:
   - Email: `admin@hotel-abc.it`
   - Password: `HotelABC2025!`

## Menu principale

| Sezione | Descrizione |
|---------|-------------|
| **Dashboard** | KPI e metriche globali |
| **Periodi** | Gestione periodi contabili |
| **Import** | Caricamento file CSV |
| **Allocazioni** | Regole di allocazione ABC |
| **Calcolo ABC** | Esegui il calcolo |
| **Report** | Visualizza risultati |
| **AI Insights** | Analisi predittive |

## Flusso di lavoro tipico

### 1. Configura un periodo contabile

- Vai su **Periodi** → **Nuovo Periodo**
- Inserisci nome, data inizio, data fine
- Salva

### 2. Importa i dati

- **Importa file CSV** in ordine:
  1. Contabilità (`costs.csv`)
  2. Payroll (`payroll.csv`)
  3. Ricavi (`revenue.csv`)

- Ogni file deve seguire lo schema definito

### 3. Definisci le regole di allocazione

- Vai su **Allocazioni**
- Per ogni centro di costo, definisci:
  - Attività target
  - Driver di allocazione
  - Percentuali

### 4. Esegui il calcolo ABC

- Vai su **Calcolo ABC**
- Seleziona il periodo
- Clicca **Esegui calcolo**
- Attendi il completamento

### 5. Analizza i risultati

- Vai su **Dashboard** per:
  - Margine lordo per servizio
  - Incidenza costi
  - Performance rispetto al budget

## Interpretazione dei risultati

### Indicatori chiave (KPI)

| KPI | Descrizione | Valori positivi |
|-----|-------------|-----------------|
| **Ricavi Totali** | Fatturato periodo | Più alto è meglio |
| **Costi Totali** | Spesa operativa | Più basso è meglio |
| **Margine Lordo** | Ricavi - Costi | > 0 è profitto |
| **Margine %** | Margine/Ricavi × 100 | > 20% è buono |
| **Incidenza Personale** | % costi sui ricavi | < 35% è sano |

### Esempi di analisi

**Servizio in perdita**
- Margine negativo = costi > ricavi
- Azioni: aumentare prezzi, ridurre costi, o riconsiderare l'offerta

**Margine basso (< 10%)**
- Servizio poco redditizio
- Analizzare breakdown costi per individuare optimization

## AI Insights

### Driver Discovery

Mostra quale driver influenza di più i costi:
- ore lavorate
- notti vendute
- coperti
- mq (metri quadri)
- eventi

### Forecasting

Previsione per i prossimi 6 mesi di:
- Notti vendute
- Coperti ristorante

### Anomaly Detection

Periodi con anomalie costi/volume:
- Rosso = anomalia critica
- Giallo = da verificare