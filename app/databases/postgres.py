from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.settings import settings


def create_engine() -> AsyncEngine:
    return create_async_engine(settings.sqlalchemy_database_uri)


def create_postgres_session_pool() -> async_sessionmaker:
    engine = create_engine()
    session_pool = async_sessionmaker(bind=engine, expire_on_commit=False)

    return session_pool


SessionPool = create_postgres_session_pool()
