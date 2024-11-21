from dataclasses import dataclass
import uuid
from enum import Enum
from sqlmodel import Relationship, SQLModel, Field

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