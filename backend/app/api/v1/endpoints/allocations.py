"""Allocations endpoint."""
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.models import AllocationRule, AllocationLevel

router = APIRouter()

class AllocationRuleSchema(BaseModel):
    id: UUID
    name: str
    level: str
    allocation_pct: Optional[Decimal]
    is_active: bool
    class Config: from_attributes = True

class AllocationRuleCreate(BaseModel):
    name: str
    level: str
    source_cost_center_id: Optional[UUID] = None
    source_activity_id: Optional[UUID] = None
    target_activity_id: Optional[UUID] = None
    target_service_id: Optional[UUID] = None
    driver_id: Optional[UUID] = None
    allocation_pct: Optional[Decimal] = None
    priority: int = 1
    description: Optional[str] = None

@router.get("/", response_model=List[AllocationRuleSchema])
async def list_rules(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(AllocationRule).where(AllocationRule.is_active == True))
    return q.scalars().all()

@router.post("/", response_model=AllocationRuleSchema, status_code=201)
async def create_rule(data: AllocationRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AllocationRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)):
    r = await db.get(AllocationRule, rule_id)
    if not r:
        raise HTTPException(404, "Regola non trovata")
    r.is_active = False
    await db.commit()
