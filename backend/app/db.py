import os
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# -----------------------------------
# LOAD ENV FIRST
# -----------------------------------
load_dotenv()

# -----------------------------------
# DATABASE URL (DEFINE BEFORE USE)
# -----------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set. Check your environment.")

# -----------------------------------
# SQLAlchemy Base
# -----------------------------------
Base = declarative_base()

# -----------------------------------
# ASYNC ENGINE + SESSION
# -----------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
    bind=engine,
)

# -----------------------------------
# DEPENDENCY
# -----------------------------------
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# -----------------------------------
# CONNECT / DISCONNECT
# -----------------------------------
async def connect_to_db():
    try:
        # 🔥 IMPORT ORDER MATTERS
        from app.models import project
        from app.models import activity_log
        from modules.vendors.models import vendor

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("📌 Connected to database + ensured tables")

    except Exception as e:
        print("❌ DB Connection Failed:", e)
        raise

async def close_db_connection():
    await engine.dispose()
    print("🔌 Database connection closed")