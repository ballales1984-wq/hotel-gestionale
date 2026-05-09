import csv
import random
from decimal import Decimal

def generate_accounting_csv(filename="accounting_sample.csv"):
    """Genera file CSV per i costi contabili (bilancio di verifica)"""
    cost_centers = ['CC-REC', 'CC-HSK', 'CC-FNB', 'CC-MNT', 'CC-COM', 'CC-CON', 'CC-DIR', 'CC-ADM']
    cost_types = ['personale', 'utilities', 'materiali', 'servizi_esterni', 'manutenzione', 'affitti', 'marketing']
    
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['conto', 'descrizione', 'centro_di_costo', 'tipo_costo', 'importo'])
        
        # Generiamo circa 50 righe di costi
        for i in range(1, 51):
            conto = f"60{random.randint(10, 99)}"
            cc = random.choice(cost_centers)
            ctype = random.choice(cost_types)
            
            # Importi realistici a seconda del tipo
            if ctype == 'personale':
                importo = random.uniform(15000, 45000)
            elif ctype == 'utilities':
                importo = random.uniform(2000, 8000)
            else:
                importo = random.uniform(500, 5000)
                
            writer.writerow([
                conto, 
                f"Spesa {ctype} per {cc}", 
                cc, 
                ctype, 
                round(importo, 2)
            ])
    print(f"Generato: {filename}")

def generate_payroll_csv(filename="payroll_sample.csv"):
    """Genera file CSV per le ore del personale (timesheet)"""
    employees = [
        {"matr": "001", "nome": "Mario Rossi", "costo_orario": 18.50, "activities": ["REC-001", "REC-002"]},
        {"matr": "002", "nome": "Luigi Verdi", "costo_orario": 19.00, "activities": ["REC-003", "REC-004"]},
        {"matr": "003", "nome": "Anna Neri", "costo_orario": 16.50, "activities": ["HSK-001", "HSK-002", "HSK-003"]},
        {"matr": "004", "nome": "Sofia Gialli", "costo_orario": 16.50, "activities": ["HSK-001", "HSK-002"]},
        {"matr": "005", "nome": "Carlo Blu", "costo_orario": 22.00, "activities": ["FNB-001", "FNB-002"]},
        {"matr": "006", "nome": "Elena Bianchi", "costo_orario": 21.50, "activities": ["FNB-003", "FNB-004"]},
        {"matr": "007", "nome": "Marco Viola", "costo_orario": 20.00, "activities": ["MNT-001", "MNT-002"]},
    ]
    
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['matricola', 'nome', 'attivita', 'ore', 'costo_orario', 'percentuale'])
        
        for emp in employees:
            total_hours = random.randint(140, 160) # Ore mensili
            
            # Distribuiamo le ore sulle attività del dipendente
            activities = emp["activities"]
            splits = [random.random() for _ in activities]
            total_split = sum(splits)
            percents = [s/total_split for s in splits]
            
            for idx, act in enumerate(activities):
                ore_act = total_hours * percents[idx]
                writer.writerow([
                    emp["matr"],
                    emp["nome"],
                    act,
                    round(ore_act, 1),
                    emp["costo_orario"],
                    round(percents[idx], 2)
                ])
    print(f"Generato: {filename}")

def generate_revenues_csv(filename="revenues_sample.csv"):
    """Genera file CSV per i ricavi (da PMS o similari)"""
    services = [
        {"code": "SVC-PNT", "rev_range": (150000, 250000), "vol_range": (1200, 1800)},
        {"code": "SVC-COL", "rev_range": (20000, 40000), "vol_range": (1500, 2500)},
        {"code": "SVC-RST", "rev_range": (50000, 90000), "vol_range": (2000, 3000)},
        {"code": "SVC-BAR", "rev_range": (10000, 25000), "vol_range": (800, 1500)},
        {"code": "SVC-CON", "rev_range": (30000, 60000), "vol_range": (10, 25)},
        {"code": "SVC-PRK", "rev_range": (5000, 12000), "vol_range": (400, 800)},
    ]
    
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['servizio', 'ricavo', 'volume'])
        
        for svc in services:
            ricavo = random.uniform(*svc["rev_range"])
            volume = random.uniform(*svc["vol_range"])
            
            writer.writerow([
                svc["code"],
                round(ricavo, 2),
                int(volume)
            ])
    print(f"Generato: {filename}")

if __name__ == "__main__":
    print("Generazione file CSV di test in corso...")
    generate_accounting_csv()
    generate_payroll_csv()
    generate_revenues_csv()
    print("Tutti i file CSV sono stati generati con successo nella cartella corrente!")
