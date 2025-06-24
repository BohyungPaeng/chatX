from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URL

print(DATABASE_URL)
engine = create_async_engine(DATABASE_URL, echo=False)

# AsyncSessionLocal = sessionmaker(
#     engine, class_=AsyncSession, expire_on_commit=False
# )

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def save_to_db(db: AsyncSession, item):
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

async def get_by_id(db: AsyncSession, model_class, item_id):
    from sqlalchemy import select
    result = await db.execute(select(model_class).where(model_class.id == item_id))
    return result.scalar_one_or_none()

async def get_by_field(db: AsyncSession, model_class, field_name, field_value):
    from sqlalchemy import select
    field = getattr(model_class, field_name)
    result = await db.execute(select(model_class).where(field == field_value))
    return result.scalar_one_or_none()