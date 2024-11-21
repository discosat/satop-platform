import uuid
from enum import Enum
from typing import Optional

from sqlmodel import Column, Integer, String, Boolean, SQLModel, Field

from database import Base, engine

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


class EntityType(str, Enum):
    person = 'person'
    system = 'system'

class Entity(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: EntityType
    scopes: list[str]
    name: str

# Map entity IDs to identity provider provided identities. That way one user could be authenticated using either e.g. "email" or "au-azure"
class AuthenticationIdentifiers(SQLModel, table=True):
    entity_id: Entity = Field(default=None, foreign_key="entity.id", primary_key=True)
    provider: str
    identity: str


SQLModel.metadata.create_all(bind=engine)