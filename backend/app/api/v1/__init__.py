"""API v1 — Router aggregato."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    activities,
    services,
    costs,
    cost_centers,
    cost_drivers,
    employees,
    periods,
    allocations,
    reports,
    imports,
    simulation,
    ai,
    mapping,
    pms_integrations,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(periods.router, prefix="/periods", tags=["periodi"])
router.include_router(activities.router, prefix="/activities", tags=["attività"])
router.include_router(services.router, prefix="/services", tags=["servizi"])
router.include_router(costs.router, prefix="/costs", tags=["costi"])
router.include_router(cost_centers.router, prefix="/cost-centers", tags=["centri-di-costo"])
router.include_router(cost_drivers.router, prefix="/cost-drivers", tags=["driver-di-allocazione"])
router.include_router(employees.router, prefix="/employees", tags=["personale"])
router.include_router(allocations.router, prefix="/allocations", tags=["allocazioni"])
router.include_router(reports.router, prefix="/reports", tags=["report ABC"])
router.include_router(imports.router, prefix="/imports", tags=["import dati"])
router.include_router(mapping.router, prefix="/mapping", tags=["mapping"])
router.include_router(pms_integrations.router, prefix="/pms-integrations", tags=["PMS/ERP Integrations"])
router.include_router(simulation.router, prefix="/simulation", tags=["simulazioni"])
router.include_router(ai.router, prefix="/ai", tags=["intelligenza artificiale"])
