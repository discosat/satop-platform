from pydantic import BaseModel
from typing import Literal, Union
from datetime import datetime

class Actor(BaseModel):
    uri: str

class User(Actor):
    name: str
    user_id: str
    role: str

class System(Actor):
    name: str
    version: str
    system_id: str

class Action(BaseModel):
    uri: str
    timestamp: int

# TODO: Look inti RFC6920 Naming Things with Hashes (The ni uri specification)
class Artifact(BaseModel):
    name: str
    url: str
    media_type: str

class Triplet(BaseModel):
    subject: Union[User, System]
    action: Action
    object: Union[User, System, Artifact]
