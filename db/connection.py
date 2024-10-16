import os

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


MAIN_DB_STRING = os.environ.get("MAIN_DB")
db = create_async_engine(MAIN_DB_STRING)
meta = MetaData()

main_async_session_maker = async_sessionmaker(
    bind=db,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False
)
