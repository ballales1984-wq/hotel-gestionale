# Hotel ABC — Standard di Importazione Dati

> **Versione**: 1.0  
> **Data**: 2026-05-11  
> **Piattaforma**: Hotel ABC Control — Multi-Tenancy & Integrazioni

---

## Panoramica

Questa guida definisce i template CSV standard per l'importazione dati da sistemi esterni (PMS, ERP, Payroll) nella piattaforma Hotel ABC. Ogni template include i campi obbligatori, facoltativi e le convenzioni di mapping.

---

## 1. Contabilità (Costi) — `accounting_import.csv`

**Scopo**: Importare le voci di costo dalla contabilità analitica del gestionale ERP.

### Template CSV

| Colonna | Obbligatoria | Descrizione | Esempio |
|---------|:---:|-------------|---------|
| `conto` | ✅ | Codice conto ERP | `6051` |
| `descrizione` | ❌ | Descrizione della voce contabile | `Spesa materiali per reception` |
| `centro_di_costo` | ✅ | Codice CDC (deve esistere nel sistema ABC) | `CC-REC` |
| `tipo_costo` | ✅ | Categoria: `personale`, `diretto`, `struttura`, `ammortamento`, `utilities`, `altro` | `personale` |
| `importo` | ✅ | Importo (decimale, separatore `.` per decimali) | `802.57` |

### Convenzioni
- **Codici centro di costo**: devono corrispondere esattamente ai codici ABC (`CC-REC`, `CC-HSK`, ecc.)
- **Tipo costo**: mappatura automatica tramite parole chiave (vedi Mapping Type)
- **Valuta**: EUR di default; non inserire simboli di valuta
- **Righe con importo 0**: vengono ignorate automaticamente
- **Duplicati**: consentiti (vengono sommati nel calcolo ABC)

### Esempio

```csv
conto,descrizione,centro_di_costo,tipo_costo,importo
6051,Spesa materiali reception,CC-REC,materiali,802.57
6097,Spesa marketing commerciale,CC-COM,marketing,4071.70
6078,Spesa personale housekeeping,CC-HSK,personale,17680.39
```

---

## 2. PMS (Ricavi / Volumi) — `revenues_import.csv`

**Scopo**: Importare i ricavi per servizio dal sistema di prenotazione (PMS) o da dati manuali.

### Template CSV

| Colonna | Obbligatoria | Descrizione | Esempio |
|---------|:---:|-------------|---------|
| `servizio` | ✅ | Codice servizio ABC (deve esistere nel sistema) | `SVC-PNT` |
| `ricavo` | ✅ | Importo ricavo (decimale) | `162778.09` |
| `volume` | ❌ | Volume operativo (notti, coperti, soste, ecc.) | `1214` |

### Convenzioni
- **Codici servizio**: devono corrispondere ai codici ABC (`SVC-PNT`, `SVC-COL`, ecc.)
- **Volume**: dipende dal tipo di servizio (notti per pernottamento, coperti per ristorante, ecc.)
- **Upsert**: se esistono già ricavi per lo stesso periodo/servizio, vengono sostituiti
- **Valuta**: EUR di default

### Esempio

```csv
servizio,ricavo,volume
SVC-PNT,162778.09,1214
SVC-COL,36176.38,1699
SVC-RST,81947.20,2718
SVC-BAR,18931.09,1299
SVC-CON,50348.10,17
SVC-PRK,11286.26,772
```

---

## 3. Payroll (Personale) — `payroll_import.csv`

**Scopo**: Importare le ore lavorate per dipendente e attività dal sistema gestione turni/HR.

### Template CSV

| Colonna | Obbligatoria | Descrizione | Esempio |
|---------|:---:|-------------|---------|
| `matricola` | ✅ | Codice dipendente (viene creato se inesistente) | `001` |
| `nome` | ❌ | Nome dipendente (usato solo per creazione automatica) | `Mario Rossi` |
| `attivita` | ✅ | Codice attività ABC (deve esistere) | `REC-001` |
| `ore` | ✅ | Ore lavorate (decimale) | `70.7` |
| `costo_orario` | ❌ | Costo orario lordo (usato quello del dipendente se omesso) | `18.5` |
| `percentuale` | ✅ | Quota di allocazione su quell'attività (0-1 o 0-100) | `0.45` |

### Convenzioni
- **Matricola**: identificatore univoco del dipendente
- **Attività**: deve corrispondere a un codice attività ABC esistente
- **Percentuale**: accettata sia in formato decimale (`0.45`) sia percentuale (`45`); la piattaforma converte automaticamente
- **Dipendenti nuovi**: vengono creati automaticamente con ruolo `N/D` e reparto `ADMIN` se non trovati
- **Costo orario**: se omesso, viene usato il costo orario registrato sul dipendente

### Esempio

```csv
matricola,nome,attivita,ore,costo_orario,percentuale
001,Mario Rossi,REC-001,70.7,18.5,0.45
001,Mario Rossi,REC-002,85.3,18.5,0.55
002,Luigi Verdi,REC-003,7.7,19.0,0.05
003,Anna Neri,HSK-001,70.4,16.5,0.45
```

---

## 4. Statistiche Operative — `operations_import.csv`

**Scopo**: Importare dati operativi (occupancy, ADR, driver values) dal sistema PMS/BI.

### Template CSV

| Colonna | Obbligatoria | Descrizione | Esempio |
|---------|:---:|-------------|---------|
| `periodo` | ✅ | Periodo in formato `YYYY-MM` | `2025-01` |
| `driver` | ✅ | Codice driver ABC | `DRV-NOT` |
| `entita_tipo` | ✅ | Tipo entità: `activity` o `service` | `service` |
| `entita_codice` | ✅ | Codice attività o servizio ABC | `SVC-PNT` |
| `valore` | ✅ | Valore numerico del driver | `1214` |

### Convenzioni
- **Periodo**: formato `YYYY-MM` (es. `2025-01` per gennaio 2025)
- **Driver**: deve esistere nel sistema ABC
- **Entità**: `activity` per attività operative, `service` per servizi
- **Valore**: numero decimale con punto come separatore

### Esempio

```csv
periodo,driver,entita_tipo,entita_codice,valore
2025-01,DRV-NOT,service,SVC-PNT,1214
2025-01,DRV-COP,service,SVC-COL,1699
2025-01,DRV-COP,service,SVC-RST,2718
2025-01,DRV-ORE,activity,REC-001,580.5
```

---

## 5. Regole di Mapping — `mapping_rules.csv`

**Scopo**: Importare in blocco le regole di mapping tra codici esterni e entità ABC.

### Template CSV

| Colonna | Obbligatoria | Descrizione | Esempio |
|---------|:---:|-------------|---------|
| `tipo_mapping` | ✅ | Tipo: `centro_di_costo`, `attivita`, `servizio`, `driver`, `conto_contabile` | `centro_di_costo` |
| `codice_esterno` | ✅ | Codice dal sistema esterno (PMS/ERP) | `PMS-RM01` |
| `descrizione_esterna` | ❌ | Descrizione del codice esterno | `Room Maintenance` |
| `codice_interno` | ✅ | Codice entità ABC di destinazione | `CC-MNT` |
| `attendibilita` | ❌ | Score di affidabilità (0.0 – 1.0) | `0.95` |

### Convenzioni
- **Tipo mapping**: determina quale entità ABC viene popolata
- **Codice interno**: deve esistere nel sistema ABC (CDC per centro_di_costo, ecc.)
- **Attendibilità**: valore decimale; usato dal motore AI per suggerimenti di mapping automatico

### Esempio

```csv
tipo_mapping,codice_esterno,descrizione_esterna,codice_interno,attendibilita
centro_di_costo,PMS-RM01,Room Maintenance,CC-MNT,0.95
centro_di_costo,PMS-FB01,Food & Beverage,CC-FNB,0.95
attivita,PMS-CKI,Check-In,REC-001,0.90
servizio,PMS-ROOM,Room Revenue,SVC-PNT,0.98
conto_contabile,6051,Spesa materiali,CC-REC,0.85
```

---

## 6. Gestione Multi-Hotel

Ogni import deve essere associato a uno specifico hotel (tenant). Il flusso è:

1. **Creare l'hotel** (se non esiste) tramite API
2. **Impostare il contesto hotel** nelle richieste di import
3. **Verificare** che i codici CDC/attività/servizio appartengano all'hotel corretto

### Header di contesto

Tutte le richieste di import accettano il parametro `hotel_id` per isolare i dati:
- Gli import di contabilità legano le voci al periodo (che ha già `hotel_id`)
- Gli import payroll legano le allocazioni al periodo
- Le verifiche pre-flight controllano solo i codici dell'hotel corrente

---

## 7. Formati File Supportati

| Formato | Estensioni | Note |
|---------|-----------|------|
| CSV | `.csv` | Separatore auto-rilevato (virgola predefinito) |
| Excel | `.xlsx`, `.xls` | Richiede `openpyxl` |

**Limiti**:
- Dimensione massima: 50 MB (configurabile)
- Encoding: UTF-8
- Prima riga: intestazioni (non viene trattata come dato)

---

## 8. Codici di Errore Import

| Codice | Significato | Azione Suggerita |
|--------|-------------|------------------|
| `INVALID_FILE` | Formato o estensione non supportata | Usare `.csv` o `.xlsx` |
| `MISSING_COLUMN` | Colonna obbligatoria assente | Verificare le intestazioni |
| `CDC_NOT_FOUND` | Centro di costo non censito | Creare il CDC o aggiungere mapping |
| `ACTIVITY_NOT_FOUND` | Attività non censita | Creare l'attività o aggiungere mapping |
| `SERVICE_NOT_FOUND` | Servizio non censito | Creare il servizio o aggiungere mapping |
| `ZERO_AMOUNT` | Importo nullo o zero | Riga ignorata (warning) |
| `INVALID_PERIOD` | Periodo non valido o non esistente | Creare il periodo contabile |