import reflex as rx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(rx.config.get_config().async_db_url)
Session = async_sessionmaker(engine, expire_on_commit=False)
