import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🔐 Get DB URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

# 🔧 Fix MySQL URL (Railway / Render issue)
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "mysql://", "mysql+mysqlconnector://"
    )

# 🚀 Create Engine (optimized for cloud deployment)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # avoids stale connections
    pool_recycle=280,        # avoids timeout disconnects
    pool_size=5,             # limit connections
    max_overflow=10,         # extra burst connections
    connect_args={
        "connect_timeout": 10
    }
)

# 🧠 Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 🧱 Base Model
Base = declarative_base()


# ===================== DEPENDENCY =====================

def get_db():
    """
    FastAPI dependency for DB session
    (prevents connection leaks)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()