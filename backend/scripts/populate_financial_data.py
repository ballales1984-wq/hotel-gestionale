"""
Populate comprehensive historical data for all existing periods.
Generates ServiceRevenue, CostItems, and LaborAllocations with realistic values.
"""
import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from app.db.database import AsyncSessionFactory
from app.models.models import AccountingPeriod, ServiceRevenue, CostItem, LaborAllocation, CostType, Service, Activity, Employee, CostCenter

async def populate_financial_data():
    async with AsyncSessionFactory() as db:
        # Get all periods
        periods = (await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year, AccountingPeriod.month))).scalars().all()
        print(f"Trovati {len(periods)} periodi")
        
        if not periods:
            print("Nessun periodo trovato. Creazione periodi di fallback...")
            # Create some periods if none exist
            today = datetime.now().replace(day=1)
            for i in range(6):
                first_day = today - timedelta(days=30 * (i + 1))
                period = AccountingPeriod(
                    id=__import__('uuid').uuid4(),
                    year=first_day.year,
                    month=first_day.month,
                    name=first_day.strftime('%B %Y'),
                    is_closed=True,
                    closed_at=datetime.now()
                )
                db.add(period)
            await db.commit()
            periods = (await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year, AccountingPeriod.month))).scalars().all()
        
        # Get reference data
        services = (await db.execute(select(Service))).scalars().all()
        activities = (await db.execute(select(Activity).where(Activity.is_active == True))).scalars().all()
        
        # Check for employees, create if needed
        employees = (await db.execute(select(Employee))).scalars().all()
        if not employees:
            emp = Employee(
                employee_code="EMP001",
                full_name="Mario Rossi",
                role="Receptionist",
                department="reception",
                hourly_cost=Decimal("20.00")
            )
            db.add(emp)
            await db.flush()
            employees = [emp]
            print("Creato dipendente di test")
        
        # Revenue mapping per servizio
        service_revenue_map = {
            "SVC-PNT": {"base": 200000, "var": 0.15},   # Pernottamento
            "SVC-COL": {"base": 35000, "var": 0.20},    # Colazione
            "SVC-RST": {"base": 80000, "var": 0.18},    # Ristorazione
            "SVC-BAR": {"base": 15000, "var": 0.25},    # Bar
            "SVC-CON": {"base": 45000, "var": 0.30},    # Congressi
            "SVC-PRK": {"base": 8000, "var": 0.10},     # Parcheggio
        }
        
        # Activity cost mapping
        activity_cost_map = {
            "REC-001": {"base": 8000, "var": 0.10},
            "REC-002": {"base": 5000, "var": 0.10},
            "REC-003": {"base": 3000, "var": 0.10},
            "REC-004": {"base": 4000, "var": 0.10},
            "HSK-001": {"base": 6000, "var": 0.10},
            "HSK-002": {"base": 7000, "var": 0.10},
            "HSK-003": {"base": 2500, "var": 0.10},
            "HSK-004": {"base": 2000, "var": 0.10},
            "FNB-001": {"base": 4000, "var": 0.10},
            "FNB-002": {"base": 6000, "var": 0.10},
            "FNB-003": {"base": 3500, "var": 0.10},
            "FNB-004": {"base": 2000, "var": 0.10},
            "FNB-005": {"base": 1500, "var": 0.10},
            "CON-001": {"base": 3000, "var": 0.15},
            "CON-002": {"base": 5000, "var": 0.15},
            "CON-003": {"base": 2000, "var": 0.15},
            "MNT-001": {"base": 4000, "var": 0.10},
            "MNT-002": {"base": 3500, "var": 0.10},
            "MNT-003": {"base": 1500, "var": 0.10},
            "COM-001": {"base": 5000, "var": 0.10},
            "COM-002": {"base": 3000, "var": 0.10},
            "DIR-001": {"base": 10000, "var": 0.05},
            "ADM-001": {"base": 6000, "var": 0.05},
            "ADM-002": {"base": 4000, "var": 0.05},
        }
        
        # Labor hour distribution per employee per activity (percentages)
        employee_activity_dist = [
            (0, ["REC-001", "REC-002", "REC-003"], [0.5, 0.3, 0.2]),
            (1, ["HSK-001", "HSK-002", "HSK-003"], [0.4, 0.4, 0.2]),
            (2, ["FNB-001", "FNB-002", "FNB-003"], [0.3, 0.5, 0.2]),
        ]
        
        total_revenue_added = 0
        total_cost_added = 0
        total_labor_added = 0
        
        for period in periods:
            print(f"\nElaborazione periodo: {period.name}...")
            
            # Check if data already exists for this period
            existing_rev = (await db.execute(
                select(func.count(ServiceRevenue.id)).where(ServiceRevenue.period_id == period.id)
            )).scalar()
            
            if existing_rev > 0:
                print(f"  Periodo {period.name} già popolato, salto")
                continue
            
            # Seasonality factor (higher in summer/winter)
            month = period.month
            season_factor = 1.0
            if month in [6, 7, 8]:  # Summer
                season_factor = 1.2
            elif month in [12, 1, 2]:  # Winter holidays
                season_factor = 1.15
            elif month in [3, 4, 5, 9, 10, 11]:  # Shoulder seasons
                season_factor = 0.9
            
            # ── 1. Add Service Revenues ────────────────────────────────────────
            for svc in services:
                if svc.code in service_revenue_map:
                    config = service_revenue_map[svc.code]
                    # Random variation around base
                    variation = random.uniform(-config["var"], config["var"])
                    base_amount = config["base"] * season_factor
                    revenue = Decimal(str(round(base_amount * (1 + variation), 2)))
                    
                    # Output volume correlated to revenue
                    if svc.code == "SVC-PNT":
                        volume = Decimal(str(int(revenue / 150)))  # Avg room rate ~150
                    elif svc.code == "SVC-COL":
                        volume = Decimal(str(int(revenue / 22)))
                    elif svc.code == "SVC-RST":
                        volume = Decimal(str(int(revenue / 35)))
                    elif svc.code == "SVC-BAR":
                        volume = Decimal(str(int(revenue / 12)))
                    elif svc.code == "SVC-CON":
                        volume = Decimal(str(int(revenue / 4500)))
                    else:
                        volume = Decimal(str(int(revenue / 10)))
                    
                    rev = ServiceRevenue(
                        period_id=period.id,
                        service_id=svc.id,
                        revenue=revenue,
                        output_volume=volume,
                        source_system="test_seed"
                    )
                    db.add(rev)
                    total_revenue_added += float(revenue)
            
            # ── 2. Add Cost Items ─────────────────────────────────────────────
            for act in activities:
                if act.code in activity_cost_map:
                    config = activity_cost_map[act.code]
                    variation = random.uniform(-config["var"], config["var"])
                    base_amount = config["base"] * season_factor
                    amount = Decimal(str(round(base_amount * (1 + variation), 2)))
                    
                    cost = CostItem(
                        period_id=period.id,
                        cost_center_id=act.cost_center_id,
                        account_name=f"Operativo {act.name}",
                        cost_type=CostType.DIRECT,
                        amount=amount,
                        source_system="test_seed"
                    )
                    db.add(cost)
                    total_cost_added += float(amount)
            
            # ── 3. Add Labor Allocations ─────────────────────────────────────
            if employees and activities:
                for emp_idx, act_codes, percs in employee_activity_dist:
                    if emp_idx < len(employees):
                        emp = employees[emp_idx]
                        total_hours = Decimal("160.00")  # Monthly hours
                        for idx, act_code in enumerate(act_codes):
                            act = next((a for a in activities if a.code == act_code), None)
                            if act:
                                # percs are already as decimals (0-1)
                                pct = Decimal(str(percs[idx]))
                                hours = (total_hours * pct).quantize(Decimal('0.01'))
                                labor = LaborAllocation(
                                    period_id=period.id,
                                    employee_id=emp.id,
                                    activity_id=act.id,
                                    hours=hours,
                                    hourly_cost=emp.hourly_cost,
                                    allocation_pct=pct,  # Store as 0-1 decimal
                                    source="test_seed"
                                )
                                db.add(labor)
                                total_labor_added += 1
            
            await db.flush()
            print(f"  Aggiunti dati per {period.name}")
        
        await db.commit()
        
        print(f"\n[OK] Popolamento completato!")
        print(f"   Ricavi totali aggiunti: €{total_revenue_added:,.2f}")
        print(f"   Costi totali aggiunti: €{total_cost_added:,.2f}")
        print(f"   Allocazioni manodopera: {total_labor_added} record")

if __name__ == "__main__":
    asyncio.run(populate_financial_data())