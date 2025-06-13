from sqlalchemy import Column, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    meta = Column(JSONB, nullable=False)
    embedding = Column(Vector(1536))