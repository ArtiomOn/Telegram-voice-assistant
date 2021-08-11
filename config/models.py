from sqlalchemy import create_engine, MetaData, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

from config.settings import user, password, host, port, database

database_dsn = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')
meta = MetaData()

Base = declarative_base()


class PullData(Base):
    __tablename__ = "pull"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    pull_question = Column(String)
    pull_choice = Column(String)
    created_at = Column(DateTime)
