from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as sqlField
from typing import Literal, Optional, Union
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
import time


class EntityType(str, Enum):
    user = 'user'
    system = 'system'

class Entity(BaseModel):
    type: EntityType
    id: str

class Predicate(BaseModel):
    descriptor: str

class Artifact(BaseModel):
    sha1: str

class Action(BaseModel):
    id: str = Field(default_factory=(lambda:str(uuid4())))
    descriptor: str

Value = Union[str, int, float]
Subject = Union[Entity, Artifact, Action]
Object = Union[Entity, Artifact, Action, Value]

class Triple(BaseModel):
    subject: Subject
    predicate: Predicate
    object: Object

class EventRelationshipBase(BaseModel):
    predicate: Predicate

class EventSubjectRelationship(EventRelationshipBase):
    subject: Subject

class EventObjectRelationship(EventRelationshipBase):
    object: Object

class Event(BaseModel):
    descriptor: str
    id: str = Field(default_factory=lambda:str(uuid4()))
    timestamp: int = Field(default_factory=time.time)
    relationships: list[Union[EventSubjectRelationship, EventObjectRelationship, Triple]]

class ArtifactStore(SQLModel, table=True):
    sha1: str = sqlField(primary_key=True)
    name: str
    size: int
