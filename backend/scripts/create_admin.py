"""Create initial admin user for development."""
import asyncio
import sys
from pathlib import Path

# Add backend root to path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.config import get_settings
from app.db.database import AsyncSessionFactory, create_tables
from app.models.models import User, UserRole
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def create_admin():
    """Create default admin user."""
    # Ensure tables exist
    await create_tables()
    print("[OK] Database tables ensured")

    async with AsyncSessionFactory() as db:
        from sqlalchemy import select

        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == "admin@hotelabc.com"))
        if result.scalar_one_or_none():
            print("Admin user already exists")
            return

        # Create admin
        admin = User(
            email="admin@hotelabc.com",
            full_name="Administrator",
            hashed_password=hash_password("admin123"),
            role=UserRole.ADMIN,
            department=None,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        print(f"[OK] Admin user created: {admin.email} (id: {admin.id})")
        print("    Password: admin123")
        print("    Role: admin")


if __name__ == "__main__":
    asyncio.run(create_admin())
