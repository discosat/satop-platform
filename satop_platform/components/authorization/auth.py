
from dataclasses import dataclass
from typing import Annotated, Iterable
import uuid
import os
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import Engine
from sqlmodel import SQLModel
import sqlmodel
from datetime import datetime, timedelta, timezone

import logging

from satop_platform.core import config
from satop_platform.components.restapi import exceptions
from satop_platform.components.authorization import models

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

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

@dataclass
class ProviderDictItem:
    identity_hint: str | None = None

class PlatformAuthorization:
    providers: dict[str, ProviderDictItem]
    engine: Engine
    used_scopes: set

    def __init__(self):
        self.providers = dict()

        engine_path = config.get_root_data_folder() / 'database/authorization.db'
        engine_path.parent.mkdir(exist_ok=True)
        engine_url = 'sqlite:///'+str(engine_path)
        self.engine = sqlmodel.create_engine(engine_url)
        SQLModel.metadata.create_all(self.engine, [models.Entity.__table__, models.AuthenticationIdentifiers.__table__])
        self.used_scopes = set()

        secret_key_path = config.get_root_data_folder() / 'token_secret'
        if not secret_key_path.exists():
            logger.info('Creating new token secret')
            new_secret = os.urandom(32)
            with open(secret_key_path, 'wb') as f:
                f.write(new_secret)
                os.chmod(f.fileno(), 600)
            self.__token_secret = new_secret
        else:
            with open(secret_key_path, 'rb') as f:
                status = os.stat(f.fileno())
                if not oct(status.st_mode)[-2:] == '00':
                    logger.warning(f'Access to the token secret is too permissive: {oct(status.st_mode)[-3:]}. Only the owner should be able view it (600)!')
                self.__token_secret = f.read()
    
    def mint_token(self, data: dict, expires_delta: timedelta | None = None):
        required_keys = ['sub', 'typ']
        for k in required_keys:
            if k not in data:
                raise ValueError(f'Cannot mint token without key "{k}"')
        to_encode = data.copy()
        to_encode['iat'] = datetime.now(timezone.utc)
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.__token_secret, algorithm=ALGORITHM)
        return encoded_jwt

    def validate_token(self, token:str):
        try:
            payload = jwt.decode(token, self.__token_secret, algorithms=[ALGORITHM])
            username = payload.get('sub')
            if username is None:
                raise exceptions.InvalidToken()
            
            # TODO - Make it fail if token is expired the below does not work for that
            exp_time = payload.get('exp')
            if datetime.fromtimestamp(exp_time, timezone.utc) < datetime.now(timezone.utc):
                raise exceptions.ExpiredToken()

            return payload
        except jwt.ExpiredSignatureError:
            raise exceptions.ExpiredToken()
        except jwt.InvalidTokenError:
            if os.environ.get('SATOP_ENABLE_TEST_AUTH'):
                split = token.split(';')
                name = split[0]
                roles = list() if len(split) == 1 else split[1].split(',')
                payload = {
                    'sub': '00000000-7e57-4000-a000-000000000000',
                    'test_name': name,
                    'test_scopes': roles
                }
                logger.warning(f'Validating test token {token}. Remove "SATOP_ENABLE_TEST_AUTH" from env to disable this. SHOULD NOT BE USED IN PRODUCTION!')
                return payload
            raise exceptions.InvalidToken()

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
        return self.mint_token(data, expires_delta=expires_delta)
    
    def create_refresh_token(self, uuid: uuid.UUID, typ = 'refresh', expires_delta: timedelta | None = None):
        if expires_delta is None:
            expires_delta = timedelta(minutes=60)
        data = {
            'sub': str(uuid),
            'typ': typ
        }
        return self.mint_token(data, expires_delta=expires_delta)
    
    def validate_tokens(self, token: str):
        try:
            return self.validate_token(token)
        except jwt.ExpiredSignatureError:
            raise exceptions.ExpiredToken()
        except jwt.InvalidTokenError:
            raise exceptions.InvalidToken()

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
        if isinstance(needed_scopes, str):
            self.used_scopes.add(needed_scopes)
        elif isinstance(needed_scopes, Iterable):
            self.used_scopes |= set(needed_scopes)

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
        
