"""CRUD Activities endpoint."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.models import Activity, Department

router = APIRouter()

class ActivitySchema(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str]
    department: str
    is_support_activity: bool
    is_active: bool
    class Config: from_attributes = True

class ActivityCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    department: str
    cost_center_id: Optional[UUID] = None
    is_support_activity: bool = False

@router.get("/", response_model=List[ActivitySchema])
async def list_activities(
    department: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Activity).where(Activity.is_active == True)
    if department:
        q = q.where(Activity.department == Department(department))
    result = await db.execute(q)
    return result.scalars().all()

@router.post("/", response_model=ActivitySchema, status_code=201)
async def create_activity(data: ActivityCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Activity).where(Activity.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Codice attività già esistente")
    activity = Activity(**data.model_dump())
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity

@router.get("/{activity_id}", response_model=ActivitySchema)
async def get_activity(activity_id: UUID, db: AsyncSession = Depends(get_db)):
    a = await db.get(Activity, activity_id)
    if not a:
        raise HTTPException(status_code=404, detail="Attività non trovata")
    return a

@router.delete("/{activity_id}", status_code=204)
async def delete_activity(activity_id: UUID, db: AsyncSession = Depends(get_db)):
    a = await db.get(Activity, activity_id)
    if not a:
        raise HTTPException(status_code=404, detail="Attività non trovata")
    a.is_active = False
    await db.commit()
