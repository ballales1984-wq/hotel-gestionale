"""
Functional Test Suite for Hotel ABC Dashboard
Tests the full data pipeline: database → API → frontend data loading
"""
import asyncio
import httpx
import sys
from datetime import datetime
from sqlalchemy import select, func
from app.db.database import AsyncSessionFactory
from app.models.models import AccountingPeriod, ABCResult, ServiceRevenue, CostItem, LaborAllocation, Service, Activity
from app.core.abc_engine import ABCEngine
from app.models.models import CostType

# ─────────────────────────────────────────────────────────────────────────────
# Test Configuration
# ─────────────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"
AUTH_TOKEN = "test-token"  # Will be ignored for now, endpoints fallback gracefully

# ─────────────────────────────────────────────────────────────────────────────
# Test Results Collector
# ─────────────────────────────────────────────────────────────────────────────
tests_passed = 0
tests_failed = 0
failures = []

def log(msg, status="INFO"):
    symbol = {"PASS": "[PASS]", "FAIL": "[FAIL]", "INFO": "[INFO]"}.get(status, "[*]")
    print(f"{symbol} {msg}")
    sys.stdout.flush()

def test(name, condition, details=""):
    global tests_passed, tests_failed, failures
    if condition:
        tests_passed += 1
        log(f"PASS: {name}", "PASS")
    else:
        tests_failed += 1
        failures.append({"test": name, "details": details})
        log(f"FAIL: {name} - {details}", "FAIL")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Database Health Checks
# ─────────────────────────────────────────────────────────────────────────────
async def test_database_health():
    log("=== DATABASE HEALTH CHECKS ===", "INFO")
    async with AsyncSessionFactory() as db:
        # Check periods exist
        periods_count = (await db.execute(select(func.count(AccountingPeriod.id)))).scalar()
        test("Periodi esistenti > 0", periods_count > 0, f"Trovati {periods_count} periodi")
        
        if periods_count > 0:
            latest_period = (await db.execute(
                select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()).limit(1)
            )).scalar_one()
            log(f"Periodo più recente: {latest_period.name} ({latest_period.year}/{latest_period.month})")
        
        # Check reference data
        services_count = (await db.execute(select(func.count(Service.id)))).scalar()
        test("Servizi configurati", services_count >= 6, f"Trovati {services_count} servizi")
        
        activities_count = (await db.execute(select(func.count(Activity.id)))).scalar()
        test("Attività configurate", activities_count > 0, f"Trovate {activities_count} attività")
        
        # Check financial data
        revenue_count = (await db.execute(select(func.count(ServiceRevenue.id)))).scalar()
        test("Dati ricavi presenti", revenue_count > 0, f"Trovati {revenue_count} record ricavi")
        
        cost_count = (await db.execute(select(func.count(CostItem.id)))).scalar()
        test("Dati costi presenti", cost_count > 0, f"Trovati {cost_count} record costi")
        
        labor_count = (await db.execute(select(func.count(LaborAllocation.id)))).scalar()
        test("Dati manodopera presenti", labor_count > 0, f"Trovati {labor_count} allocazioni")

# ─────────────────────────────────────────────────────────────────────────────
# 2. ABC Calculation Verification
# ─────────────────────────────────────────────────────────────────────────────
async def test_abc_calculation():
    log("=== ABC CALCULATION CHECKS ===", "INFO")
    async with AsyncSessionFactory() as db:
        abc_count = (await db.execute(select(func.count(ABCResult.id)))).scalar()
        test("Risultati ABC esistenti", abc_count > 0, f"Trovati {abc_count} risultati")
        
        if abc_count > 0:
            # Check that ABC results have proper data
            sample = (await db.execute(
                select(ABCResult).where(ABCResult.total_cost > 0).limit(1)
            )).scalar_one_or_none()
            test("ABC results con costi > 0", sample is not None, "Nessun risultato con costi positivi")

# ─────────────────────────────────────────────────────────────────────────────
# 3. API Endpoint Health
# ─────────────────────────────────────────────────────────────────────────────
async def test_api_endpoints():
    log("=== API ENDPOINT CHECKS ===", "INFO")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Health check
        try:
            r = await client.get(f"{API_BASE}/health")
            test("Health endpoint", r.status_code == 200, f"Status {r.status_code}")
        except Exception as e:
            test("Health endpoint", False, str(e))
        
        # Periods API
        try:
            r = await client.get(f"{API_BASE}/api/v1/periods/")
            test("Periods list API", r.status_code == 200, f"Status {r.status_code}")
            if r.status_code == 200:
                periods = r.json()
                test("Periodi non vuoti", len(periods) > 0, f"Trovati {len(periods)} periodi")
        except Exception as e:
            test("Periods list API", False, str(e))
        
        # KPI API (critical for dashboard)
        try:
            periods = (await client.get(f"{API_BASE}/api/v1/periods/")).json()
            if periods:
                period_id = periods[0]['id']
                r = await client.get(f"{API_BASE}/api/v1/reports/kpi/summary", params={"period_id": period_id})
                test("KPI summary API", r.status_code == 200, f"Status {r.status_code}")
                if r.status_code == 200:
                    kpi = r.json()
                    test("KPI ha ricavi totali", kpi.get('total_revenue', 0) > 0, f"Ricavi: {kpi.get('total_revenue')}")
                    test("KPI ha costi totali", kpi.get('total_cost', 0) > 0, f"Costi: {kpi.get('total_cost')}")
        except Exception as e:
            test("KPI summary API", False, str(e))
        
        # AI Endpoints (should work even with mock data)
        ai_endpoints = [
            ("/api/v1/ai/driver-discovery", "driver-discovery"),
            ("/api/v1/ai/anomalies", "anomalies"),
            ("/api/v1/ai/forecast?metric=notti_vendute&periods=6", "forecast"),
        ]
        for path, name in ai_endpoints:
            try:
                r = await client.get(f"{API_BASE}{path}")
                test(f"AI {name} endpoint", r.status_code in [200, 401], f"Status {r.status_code}")
            except Exception as e:
                test(f"AI {name} endpoint", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# 4. Data Pipeline Integrity
# ─────────────────────────────────────────────────────────────────────────────
async def test_data_integrity():
    log("=== DATA INTEGRITY CHECKS ===", "INFO")
    async with AsyncSessionFactory() as db:
        # Check that ABC results match service revenues
        services = (await db.execute(select(Service))).scalars().all()
        for svc in services[:3]:  # Sample first 3
            abc = (await db.execute(
                select(ABCResult).where(ABCResult.service_id == svc.id).limit(1)
            )).scalar_one_or_none()
            if abc:
                test(f"ABC result per {svc.name}", abc.total_cost is not None, "Manca costo totale")
                test(f"ABC margin per {svc.name}", abc.gross_margin is not None, "Manca margine")

# ─────────────────────────────────────────────────────────────────────────────
# Main Test Runner
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("    HOTEL ABC DASHBOARD FUNCTIONAL TEST SUITE")
    print("=" * 60)
    print()
    
    await test_database_health()
    print()
    await test_abc_calculation()
    print()
    await test_api_endpoints()
    print()
    await test_data_integrity()
    
    # Summary
    print()
    print("=" * 60)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    
    if failures:
        print("\nFailure details:")
        for f in failures:
            print(f"  • {f['test']}: {f['details']}")
    
    # Return exit code
    return 0 if tests_failed == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
