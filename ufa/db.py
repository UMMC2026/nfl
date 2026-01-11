from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from ufa.config import settings

engine = create_engine(settings.db_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def init_db() -> None:
    # Import ORM models so metadata is populated
    from ufa.models import orm  # noqa: F401
    Base.metadata.create_all(bind=engine)
