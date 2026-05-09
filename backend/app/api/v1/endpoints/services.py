"""CRUD Services."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.models import Service, ServiceType

router = APIRouter()

class ServiceSchema(BaseModel):
    id: UUID
    code: str
    name: str
    service_type: str
    output_unit: Optional[str]
    is_active: bool
    class Config: from_attributes = True

class ServiceCreate(BaseModel):
    code: str
    name: str
    service_type: str
    output_unit: Optional[str] = None
    revenue_center: Optional[str] = None
    description: Optional[str] = None

@router.get("/", response_model=List[ServiceSchema])
async def list_services(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Service).where(Service.is_active == True))
    return q.scalars().all()

@router.post("/", response_model=ServiceSchema, status_code=201)
async def create_service(data: ServiceCreate, db: AsyncSession = Depends(get_db)):
    svc = Service(**data.model_dump())
    db.add(svc)
    await db.commit()
    await db.refresh(svc)
    return svc
