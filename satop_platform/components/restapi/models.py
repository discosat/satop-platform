from sqlmodel import Column, Integer, String, Boolean, SQLModel, Field
from database import Base, engine

from typing import Optional

SQLModel.metadata = Base.metadata

class User(SQLModel, table=True):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    email = Column(String, index=True)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)

class User2(SQLModel, table=True):
    __tablename__ = "users2"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    username: str = Field(unique=True, index=True)
    full_name: str
    email: str = Field(index=True)
    hashed_password: str
    disabled: bool = Field(default=False)

SQLModel.metadata.create_all(bind=engine)