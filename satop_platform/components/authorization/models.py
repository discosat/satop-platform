from typing import Annotated, List, Literal, Optional
import uuid
from enum import Enum
import datetime as dt

from pydantic import BaseModel, field_validator
from sqlmodel import SQLModel, Field

def _utc_now():
    return dt.datetime.now(dt.timezone.utc)

class EntityType(str, Enum):
    person = 'person'
    system = 'system'

class EntityBase(SQLModel):
    name: str
    type: EntityType
    roles: str = Field(default="") # Comma-seperated list of scopes

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "John Doe",
                    "type": "person",
                    "roles": "admin,operator"
                }
            ]
        }
    } # type: ignore

class Entity(EntityBase, table=True):
    __table_args__ = {'extend_existing': True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

# Map entity IDs to identity provider provided identities. That way one user could be authenticated using either e.g. "email" or "au-azure"
class ProviderIdentityBase(SQLModel):
    provider: str = Field(primary_key=True)
    identity: str = Field(primary_key=True)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "provider": "email_password",
                    "identity": "test@example.com"
                }
            ]
        }
    } # type: ignore

class AuthenticationIdentifiers(ProviderIdentityBase, table=True):
    __table_args__ = {'extend_existing': True}
    entity_id: uuid.UUID = Field(default=None, foreign_key="entity.id")


class IdentityProviderDetails(BaseModel):
    provider_hint: str
    registered_users: list[AuthenticationIdentifiers]

class RoleScopes(SQLModel, table=True):
    role: str = Field(primary_key=True, nullable=False)
    scope: str = Field(primary_key=True, nullable=False)

    
class NewRole(BaseModel):
    name:str
    scopes:list[str]


class TokenType(str, Enum):
    access = 'access'
    refresh = 'refresh'
    # id = 'id'

class TokenBase(BaseModel):
    sub: uuid.UUID
    typ: TokenType
    nbf: Optional[dt.datetime] = Field(None)
    exp: Optional[dt.datetime] = None

    @field_validator('sub', mode='before')
    def uuid_str(cls, v):
        if isinstance(v, str):
            return uuid.UUID(v)
        return v

class Token(TokenBase):
    nbf: Optional[dt.datetime] = Field(default_factory=_utc_now)
    iat: dt.datetime = Field(default_factory=_utc_now)

class TestToken(Token):
    test_name: str
    test_scopes: List[str]

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str