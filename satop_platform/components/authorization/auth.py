
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Iterable
import uuid
import os
from fastapi import Depends, HTTPException, APIRouter, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import Engine
from sqlmodel import SQLModel
import sqlmodel

from ..restapi import exceptions

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from sqlmodel import Session
import logging

from satop_platform.core import config

logger = logging.getLogger(__name__)

#from passlib.context import CryptContext

SECRET_KEY = "INSERT_SECRET_KEY_HERE"
REFRESH_SECRET_KEY = "INSERT_REFRESH_SECRET_KEY_HERE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 1

auth_scheme = HTTPBearer(
    scheme_name='jwt_token',
    description='JWT Token',
    auto_error=False
)

# Missing:
# - Token scopes (User Scopes) (Dependency called in auth_scope)
# - Match Authentication Plugin Token with User, so different plugins can be used for different users (Depends() function?) Already Done in satop_plugins' password_authentication_provider.py - Done
# - Make sure Token can decode (So we can validate it) - Done
# - Make Token Reneval (Update Access Token) (If new access token hasent been requested in 15 minutes, user has to log in again)
# - Make Token Reneval (Update Refresh Token) (Get logged out after 1 day of not using the platform/Stay logged in for 1 day after last use (unless logged out))
# - Make User
# - Make User Scopes
# - Make possible to add new Scopes to User
# - Make possible to remove Scopes from User

router = APIRouter(prefix='/tokens', tags=['Token Authorization'])

#pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def decode_token(token):
    return jwt.decode(token)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.get("/verify-token/{token}")
async def verify_token(token: str):
    verify_token(token=token)
    return {"message": "Token is valid"}

def validate_token(token:str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise exceptions.InvalidToken()
        return payload
    except jwt.ExpiredSignatureError:
        raise exceptions.ExpiredToken()
    except jwt.InvalidTokenError:
        if os.environ['SATOP_ENABLE_TEST_AUTH']:
            split = token.split(';')
            name = split[0]
            scopes = list() if len(split) == 1 else split[1].split(',')
            payload = {
                'sub': '00000000-7e57-4000-a000-000000000000',
                'test_name': name,
                'test_scopes': scopes
            }
            logger.warning(f'Validating test token {token}. Remove "SATOP_ENABLE_TEST_AUTH" from env to disable this. SHOULD NOT BE USED IN PRODUCTION!')
            return payload
        raise exceptions.InvalidToken()

async def get_user(token: Annotated[str, Depends(auth_scheme)]):
    decoded = decode_token(token)

    if not decoded:
        raise exceptions.InvalidCredentials()

    return decoded

from . import models

# Checks what scopes the user needs to access something, and checks if the user has them
def auth_scope(needed_scopes: Iterable[str] | str):
    def f(credentials: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)]):
        token = credentials.credentials
        print(token)
        # Validate Token
        payload = validate_token(token)
        token_scopes = set(payload.get("scopes", [])) # TODO: fetch user/token scopes (Make a set of scopes from the token that the user (uuid) has access to)
        if (isinstance(needed_scopes, str) and needed_scopes in token_scopes) \
            or (set(needed_scopes).issubset(token_scopes)):
            return True
        
        raise exceptions.InsufficientPermissions()
    return f

@dataclass
class ProviderDictItem:
    identity_hint: str | None = None

class PlatformAuthorization:
    providers: dict[str, ProviderDictItem]
    engine: Engine

    def __init__(self):
        self.providers = dict()

        engine_path = config.get_root_data_folder() / 'database/authorization.db'
        engine_path.parent.mkdir(exist_ok=True)
        engine_url = 'sqlite:///'+str(engine_path)
        self.engine = sqlmodel.create_engine(engine_url)
        SQLModel.metadata.create_all(self.engine, [models.Entity.__table__, models.AuthenticationIdentifiers.__table__])

    def register_provider(self, provider_key: str, identity_hint: str|None = None):
        if provider_key in self.providers:
            raise RuntimeError('Provider name already registered')

        self.providers[provider_key] = ProviderDictItem(identity_hint=identity_hint)
    
    def get_uuid(self, provider: str, entity_identifier: str):
        with sqlmodel.Session(self.engine) as session:
            statement = sqlmodel.select(models.AuthenticationIdentifiers)\
                .where(models.AuthenticationIdentifiers.provider == provider)\
                .where(models.AuthenticationIdentifiers.identity == entity_identifier)
            entity = session.exec(statement).first()
            if entity:
                return entity.entity_id

        return None

    def create_token(self, uuid: uuid.UUID, typ = 'access', expires_delta: timedelta | None = None):
        data = {
            'sub': str(uuid),
            'typ': typ
        }
        return create_access_token(data, expires_delta=expires_delta)
    
    def create_refresh_token(self, uuid: uuid.UUID, typ = 'refresh', expires_delta: timedelta | None = None):
        data = {
            'sub': str(uuid),
            'typ': typ
        }
        return create_refresh_token(data, expires_delta=expires_delta)

    def require_login(self, credentials: Annotated[HTTPAuthorizationCredentials|None, Depends(auth_scheme)], request: Request):
        if credentials is None:
            raise exceptions.MissingCredentials
        token = credentials.credentials
        # Validate Token
        payload = validate_token(token)
        _uuid = payload.get('sub')
        if not _uuid:
            raise exceptions.InvalidToken
        request.state.userid = _uuid
        request.state.token_payload = payload

        return payload

    def require_scope(self, needed_scopes: Iterable[str] | str):
        def f(token_payload: Annotated[dict, Depends(self.require_login)], request: Request):
            with sqlmodel.Session(self.engine) as session:
                validated_scopes = token_payload.get('test_scopes')

                if validated_scopes is None:
                    statement = sqlmodel.select(models.Entity).where(models.Entity.id == uuid.UUID(request.state.userid))
                    entity = session.exec(statement).first()
                    
                    if not entity:
                        raise exceptions.InvalidUser
                
                    validated_scopes = entity.scopes.split(',')

                if (isinstance(needed_scopes, str) and needed_scopes in validated_scopes) \
                    or (set(needed_scopes).issubset(validated_scopes)):
                    return True
            
            raise exceptions.InsufficientPermissions()

        return f

    def get_all_entities(self):
        statement = sqlmodel.select(models.Entity)
        with sqlmodel.Session(self.engine) as session:
            entities = session.exec(statement)
            return list(entities)

    def add_entity(self, entity: models.EntityBase):
        new_entity = models.Entity(
            name=entity.name,
            type=entity.type,
            scopes=entity.scopes
        )

        with sqlmodel.Session(self.engine) as session:
            session.add(new_entity)
            session.commit()
            session.refresh(new_entity)

            return new_entity

    def get_entity_details(self, _uuid: str):
        with sqlmodel.Session(self.engine) as session:
            statement = sqlmodel.select(models.Entity).where(models.Entity.id == uuid.UUID(_uuid))
            entity = session.exec(statement).first()

            if not entity:
                raise exceptions.NotFound(f"Entity {_uuid} not found")

            return entity

    def connect_entity_idp(self, _uuid: str, provider: models.ProviderIdentityBase):
        aidp = models.AuthenticationIdentifiers(
            entity_id=uuid.UUID(_uuid),
            provider=provider.provider,
            identity=provider.identity
        )

        with sqlmodel.Session(self.engine) as session:
            session.add(aidp)
            session.commit()
            session.refresh(aidp)
        
            return aidp

    def get_identity_providers(self):
        return self.providers
        # with sqlmodel.Session(self.engine) as session:
        #     statement = sqlmodel.select(models.AuthenticationIdentifiers)
        #     providers = session.exec(statement).all()
        #     return providers

    def get_idp_details(self, provider_name: str):
        with sqlmodel.Session(self.engine) as session:
            statement = sqlmodel.select(models.AuthenticationIdentifiers).where(models.AuthenticationIdentifiers.provider == provider_name)
            entitites = session.exec(statement).all()

            provider = self.providers.get(provider_name)

            if not provider:
                raise exceptions.NotFound(f"Provider {provider_name} not found")

            return models.IdentityProviderDetails(provider_hint=provider.identity_hint, registered_users=entitites)