import uuid
from enum import Enum

from sqlmodel import SQLModel, Field

from .database import Base, engine

SQLModel.metadata = Base.metadata

class EntityType(str, Enum):
    person = 'person'
    system = 'system'

class EntityBase(SQLModel):
    name: str
    type: EntityType
    scopes: str | None = Field(default=None) # Comma-seperated list of scopes

class Entity(EntityBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

# Map entity IDs to identity provider provided identities. That way one user could be authenticated using either e.g. "email" or "au-azure"
class ProviderIdentityBase(SQLModel):
    provider: str
    identity: str

class AuthenticationIdentifiers(ProviderIdentityBase, table=True):
    entity_id: uuid.UUID = Field(default=None, foreign_key="entity.id", primary_key=True)



SQLModel.metadata.create_all(bind=engine)