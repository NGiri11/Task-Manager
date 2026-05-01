import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+mysqlconnector://")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True   # 🔥 IMPORTANT (Railway DB fix)
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()