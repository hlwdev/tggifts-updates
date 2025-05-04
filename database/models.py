from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy import Integer, String, Column

engine = create_async_engine("sqlite+aiosqlite:///db.sqlite3", echo=False)

async_session = async_sessionmaker(bind=engine, expire_on_commit=True)

session = async_session()

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Gift(Base):
    __tablename__ = 'gifts'
    id = Column(Integer, primary_key=True, index=True)
    gift_id = Column(String, unique=True)
    is_upgradable = Column(Integer)
    sold_out = Column(Integer)
    alert_10 = Column(Integer)
    alert_1 = Column(Integer)

async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)