
from dataclasses import dataclass
import json
from typing import Annotated, Iterable
from uuid import UUID
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


class UUIDJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, UUID):
            return str(o)
        else:
            return super().default(o)

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
    identity_hint: str

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
        SQLModel.metadata.create_all(self.engine, [models.Entity.__table__, models.AuthenticationIdentifiers.__table__, models.RoleScopes.__table__]) # type: ignore
        self.used_scopes = set()

        secret_key_path = config.get_root_data_folder() / 'token_secret'
        if not secret_key_path.exists():
            logger.info('Creating new token secret')
            new_secret = os.urandom(32)
            with open(secret_key_path, 'wb') as f:
                f.write(new_secret)
                os.chmod(f.fileno(), 0o600)
            self.__token_secret = new_secret
        else:
            with open(secret_key_path, 'rb') as f:
                status = os.stat(f.fileno())
                if not oct(status.st_mode)[-2:] == '00':
                    logger.warning(f'Access to the token secret is too permissive: {oct(status.st_mode)[-3:]}. Only the owner should be able view it (600)!')
                self.__token_secret = f.read()
    
    def mint_token(self, data: models.TokenBase, expires_delta: timedelta | None = None):
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        elif data.exp:
            expire = data.exp
        else:
            match data.typ:
                case models.TokenType.access:
                    delta = timedelta(minutes=15)
                case models.TokenType.refresh:
                    delta = timedelta(minutes=60)
                case _:
                    delta = timedelta(minutes=5)
            expire = datetime.now(timezone.utc) + delta

        to_encode = models.Token( **data.model_dump(exclude_none=True, exclude_defaults=True, exclude_unset=True) )
        to_encode.iat = datetime.now( timezone.utc )
        to_encode.exp = expire

        encoded_jwt = jwt.encode(to_encode.model_dump(), self.__token_secret, algorithm=ALGORITHM, json_encoder=UUIDJSONEncoder)
        return encoded_jwt

    def validate_token(self, token:str, require_typ: models.TokenType|None = models.TokenType.access):
        try:
            payload = jwt.decode(token, self.__token_secret, algorithms=[ALGORITHM], require=["sub", "exp", "iat", "nbf"])
            username = payload.get('sub')
            if username is None:
                raise exceptions.InvalidToken()
            
            exp_time = payload.get('exp')
            if datetime.fromtimestamp(exp_time, timezone.utc) < datetime.now(timezone.utc):
                raise exceptions.ExpiredToken()
            
            validated = models.Token.model_validate(payload)
            
            if require_typ and require_typ != validated.typ:
                raise ValueError('Unexpected token type')

            return validated
        
        except jwt.ExpiredSignatureError:
            raise exceptions.ExpiredToken()
        except (jwt.InvalidTokenError, jwt.MissingRequiredClaimError, ValueError) as e:
            logger.warning(f'Failed validating token: {e}')
            if os.environ.get('SATOP_ENABLE_TEST_AUTH'):
                split = token.split(';')
                name = split[0]
                roles = [] if len(split) == 1 else split[1].split(',')

                test_token = models.TestToken(
                    sub = UUID('00000000-7e57-4000-a000-000000000000'),
                    iat = datetime.now(),
                    nbf = datetime.now(),
                    exp = datetime.now() + timedelta(minutes=10),
                    typ = models.TokenType.access if require_typ is None else require_typ,
                    test_name = name,
                    test_scopes = roles
                )
                
                logger.warning(f'Validating test token {token}. Remove "SATOP_ENABLE_TEST_AUTH" from env to disable this. SHOULD NOT BE USED IN PRODUCTION!')
                return test_token
            raise exceptions.InvalidToken(detail=str(e))

    def register_provider(self, provider_key: str, identity_hint: str):
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

    def create_token(self, uuid: UUID, typ = models.TokenType.access, expires_delta: timedelta | None = None):
        token = models.TokenBase(
            sub = uuid,
            typ = typ
        )

        return self.mint_token(token, expires_delta=expires_delta)
    
    def create_refresh_token(self, uuid: UUID, expires_delta: timedelta | None = None):
        return self.create_token(uuid, models.TokenType.refresh, expires_delta=expires_delta)
    
    # def validate_token(self, token: str):
    #     try:
    #         return self._validate_token(token)
    #     except jwt.ExpiredSignatureError:
    #         raise exceptions.ExpiredToken()
    #     except jwt.InvalidTokenError:
    #         raise exceptions.InvalidToken()

    def require_login(self, credentials: Annotated[HTTPAuthorizationCredentials|None, Depends(auth_scheme)], request: Request):
        if credentials is None:
            raise exceptions.MissingCredentials
        token = credentials.credentials
        # Validate Token
        payload = self.validate_token(token)
        _uuid = payload.sub
        if not _uuid:
            raise exceptions.InvalidToken
        request.state.userid = _uuid
        request.state.token_payload = payload

        return payload

    def require_refresh(self, credentials: Annotated[HTTPAuthorizationCredentials|None, Depends(auth_scheme)], request: Request):
        if credentials is None:
            raise exceptions.MissingCredentials
        token = credentials.credentials
        # Validate Token
        payload = self.validate_token(token, models.TokenType.refresh)
        _uuid = payload.sub
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
            validated_scopes = token_payload.get('test_scopes')

            if validated_scopes is None:
                validated_scopes = self.get_entity_scopes(UUID(request.state.userid))

            def matches(scope:str|Iterable[str], validated:str):
                if isinstance(scope, str):
                    if validated.endswith('*'):
                        prefix = validated[:-1]
                        return scope.startswith(prefix)
                    return scope == validated

                else:
                    return all(matches(s, validated) for s in scope)

            if not any(matches(needed_scopes, vs) for vs in validated_scopes):
                raise exceptions.InsufficientPermissions()

            return True
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
            roles=entity.roles
        )

        with sqlmodel.Session(self.engine) as session:
            session.add(new_entity)
            session.commit()
            session.refresh(new_entity)

            return new_entity
    
    def update_entity(self, entity: models.Entity):
        with sqlmodel.Session(self.engine) as session:
            ent = session.exec(
                sqlmodel.select(models.Entity)
                        .where(models.Entity.id == entity.id)
            ).one()
            ent.sqlmodel_update(entity)
            session.add(ent)
            session.commit()
            session.refresh(ent)

            return ent

    def get_entity_details(self, _uuid: str):
        with sqlmodel.Session(self.engine) as session:
            statement = sqlmodel.select(models.Entity).where(models.Entity.id == UUID(_uuid))
            entity = session.exec(statement).first()

            if not entity:
                raise exceptions.NotFound(f"Entity {_uuid} not found")

            return entity

    def connect_entity_idp(self, _uuid: str, provider: models.ProviderIdentityBase):
        aidp = models.AuthenticationIdentifiers(
            entity_id=UUID(_uuid),
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

            return models.IdentityProviderDetails(provider_hint=provider.identity_hint, registered_users=list(entitites))
        
    def get_roles(self):
        with sqlmodel.Session(self.engine) as session:
            statement = sqlmodel.select(models.RoleScopes)
            results = session.exec(statement)
            roles:dict[str,list[str]] = dict()

            for res in results:
                if res.role not in roles:
                    roles[res.role] = list()
                roles[res.role].append(res.scope)
            
            for k,v in roles.items():
                roles[k] = sorted(v)

            return roles
    

    def create_new_role(self, name:str, scopes:list[str]):
        new_roles = [
            models.RoleScopes(role=name, scope=s)
            for s in scopes
        ]

        with sqlmodel.Session(self.engine) as session:
            session.add_all(new_roles)
            session.commit()
        
        return
    
    def update_role(self, name:str, scopes:list[str]):
        with sqlmodel.Session(self.engine) as session:
            result = session.exec(sqlmodel.select(models.RoleScopes).where(models.RoleScopes.role == name)).all()
            current_scopes = {s.scope for s in result}
            new_scopes = set(scopes)

            to_delete = current_scopes - new_scopes
            to_add = new_scopes - current_scopes

            for res in result:
                if res.scope in to_delete:
                    session.delete(res)

            session.add_all([models.RoleScopes(role=name, scope=s) for s in to_add])
            session.commit()
        
        return {
            'deleted': len(to_delete),
            'added': len(to_add)
        }

    def get_entity_scopes(self, entity_id:UUID):
        with sqlmodel.Session(self.engine) as session:
            statement = sqlmodel.select(models.Entity).where(models.Entity.id == entity_id)
            entity = session.exec(statement).first()
            
            if not entity:
                raise exceptions.InvalidUser
            
            roles = entity.roles.split(',')

            statement = sqlmodel.select(models.RoleScopes).where(models.RoleScopes.role.in_(roles)) # type: ignore
            result = session.exec(statement).all()
        
            return {x.scope for x in result}

    def refresh_tokens(self, refresh_token: str|models.Token):
        match refresh_token:
            case str():
                t = self.validate_token(refresh_token)
            case models.Token():
                t = refresh_token
            case _:
                raise exceptions.InvalidToken

        if t.typ != models.TokenType.refresh:
            raise exceptions.InvalidToken

        return models.TokenPair(
            access_token  = self.create_token(t.sub),
            refresh_token = self.create_refresh_token(t.sub)
        )