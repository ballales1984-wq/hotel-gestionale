# Importare dati nella piattaforma

## File CSV supportati

La piattaforma accetta 3 tipi di file per il calcolo ABC:

### 1. Contabilità (costs.csv)

**Campi obbligatori:**

| Campo | Tipo | Descrizione | Esempio |
|-------|------|-------------|---------|
| `conto` | stringa | Codice conto | "6010" |
| `descrizione` | stringa | Descrizione | "Stipendi Reception" |
| `centro_di_costo` | stringa | Codice centro | "CC-REC" |
| `tipo_costo` | stringa | Tipo | "personale", "struttura", "utilities" |
| `importo` | decimale | Importo € | 45000.00 |

**Esempio completo:**

```csv
conto,descrizione,centro_di_costo,tipo_costo,importo
6010,Stipendi Reception,CC-REC,personale,45000.00
6020,Stipendi Housekeeping,CC-HSK,personale,38000.00
6030,Acqua e luce,CC-STR,utilities,8500.00
6040,Materiali pulizia,CC-HSK,materiali,3200.00
6050,Manutenzione strumentale,CC-MNT,manutenzione,5100.00
```

### 2. Payroll (payroll.csv)

**Campi obbligatori:**

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `matricola` | stringa | ID dipendente |
| `nome` | stringa | Nome completo |
| `attivita` | stringa | Codice attività |
| `ore` | decimale | Ore lavorate |
| `costo_orario` | decimale | €/ora |
| `percentuale` | decimale | % allocazione |

**Esempio:**

```csv
matricola,nome,attivita,ore,costo_orario,percentuale
001,Mario Rossi,REC-001,85.5,18.50,0.60
001,Mario Rossi,REC-002,56.3,18.50,0.40
002,Luigi Verdi,REC-003,120.0,19.00,1.00
```

### 3. Ricavi (revenue.csv)

**Campi obbligatori:**

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `servizio` | stringa | Codice servizio |
| `ricavo` | decimale | Totale € |
| `volume` | intero | Unità prodotte |

**Esempio:**

```csv
servizio,ricavo,volume
SVC-PNT,280000,1450
SVC-COL,32000,2100
SVC-RST,65000,2600
SVC-BAR,18000,1100
SVC-CON,42000,18
SVC-PRK,8500,620
```

## Generare dati di esempio

Per generare file CSV di esempio per test:

```bash
# Esegui lo script di generazione
cd backend/scripts
python generate_sample_data.py
```

I file generati saranno:
- `accounting_sample.csv`
- `payroll_sample.csv`
- `revenues_sample.csv`

## Processo di importazione

### Passo 1: Preparazione periodo

1. Vai su **Periodi** nel frontend
2. Crea un nuovo periodo con date valide

### Passo 2: Importazione file

1. Vai su **Import** nel frontend
2. Carica i 3 file CSV in sequenza
3. Verifica i messaggi di conferma

### Passo 3: Verifica importazione

Controlla che tutti i record siano stati importati:
- Numero costi → numero attività
- Numero ore → totale ore dichiarate
- Numero servizi → numero codici servizio

## Codici predefiniti

### Centri di costo (CC-*)

| Codice | Descrizione |
|--------|-------------|
| CC-REC | Reception |
| CC-HSK | Housekeeping |
| CC-FNB | Food & Beverage |
| CC-MNT | Manutenzione |
| CC-COM | Commerciale |
| CC-CON | Conventions |
| CC-DIR | Direzione |
| CC-ADM | Amministrazione |

### Attività (XXX-###)

| Codice | Descrizione | Tipo |
|--------|-------------|------|
| REC-001 | Check-in/out | Primaria |
| REC-002 | Concierge | Primaria |
| REC-003 | Telefonate | Supporto |
| HSK-001 | Camera pulita | Primaria |
| HSK-002 | Cambio biancheria | Supporto |
| FNB-001 | Cucina | Primaria |
| MNT-001 | Manutenzione strumentale | Supporto |

### Servizi (SVC-*)

| Codice | Descrizione | Unità |
|--------|-------------|-------|
| SVC-PNT | Pernottamento | notte |
| SVC-COL | Colazione | coperto |
| SVC-RST | Ristorante | coperto |
| SVC-BAR | Bar | conto |
| SVC-CON | Conventions | evento |
| SVC-PRK | Parcheggio | giorno |

## Errori comuni

### "Nessuna regola di allocazione per centro di costo"

**Causa:** Manca la regola di allocazione per quel centro.

**Soluzione:** Vai su **Allocazioni** e crea la regola per quel centro di costo.

### "Dati CSV non validi: campo mancante"

**Causa:** Intestazione o valori mancanti nel file.

**Soluzione:** Verifica che tutti i campi obbligatori siano presenti.

### "Totale ore non corrisponde"

**Causa:** Percentuali non sommano a 100%.

**Soluzione:** Controlla che le percentuali per ogni dipendente sommino a 1.00.