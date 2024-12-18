from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as sqlField
from typing import Literal, Optional, Union
from datetime import datetime
from enum import Enum
import time

class EntityType(str, Enum):
    user = 'user'
    system = 'system'
    artifact = 'artifact'

class Entity(BaseModel):
    type: EntityType
    id: str

class Predicate(BaseModel):
    descriptor: str

class Artifact(BaseModel):
    sha1: str

class Event(BaseModel):
    subject: Entity
    predicate: Predicate
    object: Union[Entity, str]
    timestamp: int = Field(default_factory=time.time)


class ArtifactStore(SQLModel, table=True):
    sha1: str = sqlField(primary_key=True)
    name: str
    size: int
