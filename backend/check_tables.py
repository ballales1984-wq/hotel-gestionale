import asyncio
import sys
sys.path.insert(0, '.')
from app.db.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        # Get table names
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        rows = result.fetchall()
        print('Tables in database:')
        for row in rows:
            print(f'  {row[0]}')

if __name__ == '__main__':
    asyncio.run(main())