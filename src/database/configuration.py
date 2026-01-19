from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
sm = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Session:
    return sm()
