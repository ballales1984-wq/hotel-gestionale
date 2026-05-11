# Schema Database

## Entità principali

### Period (Periodi contabili)

```sql
CREATE TABLE periods (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### CostCenter (Centri di costo)

```sql
CREATE TABLE cost_centers (
    id UUID PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50), -- personale, struttura, ammortamento
    description TEXT
);
```

### Activity (Attività)

```sql
CREATE TABLE activities (
    id UUID PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_primary BOOLEAN DEFAULT false,
    cost_center_id UUID REFERENCES cost_centers(id)
);
```

### Service (Servizi)

```sql
CREATE TABLE services (
    id UUID PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50),
    output_unit VARCHAR(20) -- notte, coperto, evento
);
```

### CostRecord (Voci costi)

```sql
CREATE TABLE cost_records (
    id UUID PRIMARY KEY,
    period_id UUID REFERENCES periods(id),
    cost_center_id UUID REFERENCES cost_centers(id),
    cost_type VARCHAR(50), -- personale, struttura, ammortamento, utilities
    amount DECIMAL(12,2),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### AllocationRule (Regole di allocazione)

```sql
CREATE TABLE allocation_rules (
    id UUID PRIMARY KEY,
    period_id UUID REFERENCES periods(id),
    level VARCHAR(50), -- costo_ad_attivita, attivita_ad_attivita, attivita_a_servizio
    source_cost_center_id UUID REFERENCES cost_centers(id),
    source_activity_id UUID REFERENCES activities(id),
    target_activity_id UUID REFERENCES activities(id),
    target_service_id UUID REFERENCES services(id),
    driver_type VARCHAR(50), -- ore, mq, notti, coperti, eventi
    allocation_pct DECIMAL(5,4),
    priority INTEGER DEFAULT 0
);
```

### ABCResult (Risultati ABC)

```sql
CREATE TABLE abc_results (
    id UUID PRIMARY KEY,
    period_id UUID REFERENCES periods(id),
    calculation_date TIMESTAMP DEFAULT NOW(),
    total_cost DECIMAL(14,2),
    total_revenue DECIMAL(14,2),
    total_margin DECIMAL(14,2),
    unallocated_amount DECIMAL(14,2),
    iterations_used INTEGER,
    status VARCHAR(20)
);
```

## Relazioni

```
Period
  ├── CostRecords (N:1)
  ├── AllocationRules (N:1)
  └── ABCResults (1:1)

CostCenter
  ├── CostRecords (N:1)
  ├── Activities (N:1)
  └── AllocationRules (source N:1)

Activity
  └── AllocationRules (source/target N:1)

Service
  └── AllocationRules (target N:1)
```

## Indici consigliati

```sql
CREATE INDEX idx_cost_records_period ON cost_records(period_id);
CREATE INDEX idx_allocation_rules_period ON allocation_rules(period_id);
CREATE INDEX idx_cost_records_costcenter ON cost_records(cost_center_id);
```