import os
import logging
from hashlib import scrypt
import datetime as dt
from base64 import b64encode
from uuid import uuid4, UUID

import sqlmodel
import sqlalchemy.exc 
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from satop_platform.plugin_engine.plugin import AuthenticationProviderPlugin
from satop_platform.components.restapi import exceptions
from satop_platform.core import config

# from .password_authentication_provider import models
from pydantic import BaseModel

class HashedAPIKeys(sqlmodel.SQLModel, table=True):
    application_id: UUID = sqlmodel.Field(primary_key=True)
    system_id: str
    key_hint: str
    key_hash: bytes
    salt: bytes
    expiry: dt.datetime | None

class KeyCredentials(BaseModel):
    application_id: UUID
    api_key: str

class CreateKeyModel(BaseModel):
    system_id: str
    key_hint: str
    expiry: dt.datetime | None = sqlmodel.Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365))

class Token(BaseModel):
    access_token: str
    refresh_token: str

class CreatedKeyModel(BaseModel):
    system_id: str
    application_id: UUID
    api_key: str
    key_hint: str
    expiry: dt.datetime|None

logger = logging.getLogger('plugin.api_key_auth')

class APIKeyAuth(AuthenticationProviderPlugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)
        
        engine_path = self.data_dir / 'api_keys.db'
        engine_path.parent.mkdir(exist_ok=True, parents=True)
        self.sql_engine = sqlmodel.create_engine('sqlite:///'+str(engine_path))
        
        # sqlmodel.SQLModel.metadata.create_all(self.sql_engine)
        # if not inspect(self.sql_engine).has_table(HashedCredentials.__tablename__):
        HashedAPIKeys.__table__.create(self.sql_engine, checkfirst=True)

        self.api_router = APIRouter(prefix='/api_key', tags=['Authentication'])

        @self.api_router.post('/token',
                              response_model=Token,
                              summary='Request an access and refresh token.',
                              description='Obtain a new access token by providing valid user credentials.',
                              response_description='A fresh JWT token.',
                              responses= {
                                  **exceptions.InvalidCredentials().response
                              })
        async def __create_token(credentials: KeyCredentials):
            if self.validate(credentials):
                with sqlmodel.Session(self.sql_engine) as session:
                    statement = sqlmodel.select(HashedAPIKeys).where(HashedAPIKeys.application_id == credentials.application_id)
                    key = session.exec(statement).one()
                    system_id = key.system_id

                return Token(access_token = self.create_auth_token(uuid=system_id),
                             refresh_token = self.create_refresh_token(uuid=system_id))
            
            raise exceptions.InvalidCredentials

        @self.api_router.post(
                "/refresh_tokens",
                response_model=Token,
                summary="Refresh access token and refresh token",
                description="Obtain a new access token and refresh token using a valid refresh token.",
                response_description="Returns a new access token and refresh token."
        )
        async def __refresh_access_token(refresh_token: str):
            # Validate token is correct and not expired
            try:
                payload = self.validate_token(refresh_token)
                if not payload:
                    raise exceptions.InvalidToken("Invalid refresh token.")
                
                uuid = payload.get('sub')
                if not uuid:
                    raise exceptions.InvalidUser("Invalid refresh token payload.")
                
                return Token(access_token = self.create_auth_token(uuid=uuid), refresh_token = self.create_refresh_token(uuid=uuid))
            except exceptions.InvalidCredentials as e:
                logger.error(f"Token refresh has failed: {e}")
                raise


        @self.api_router.post('/create_key',
                              status_code=status.HTTP_201_CREATED,
                              summary='Create new key.',
                              description='Register a new application and create an API key.',
                              response_model=CreatedKeyModel,
                              responses= {
                                #   status.HTTP_409_CONFLICT: {
                                #       'description': 'User already exists',
                                #   },
                              },
                            #   dependencies=[
                            #       Depends(auth_scope(['users.create']))
                            #   ]
                             )
        async def __create_key(credentials: CreateKeyModel):
            with sqlmodel.Session(self.sql_engine) as session:

                salt = os.urandom(16)
                key = b64encode(os.urandom(64)).decode()
                app_id = uuid4()

                hashed_key = self.hash_function(key, salt)
                entry = HashedAPIKeys(
                    system_id=credentials.system_id,
                    application_id=app_id,
                    key_hint=credentials.key_hint,
                    key_hash=hashed_key,
                    salt=salt,
                    expiry=credentials.expiry
                )

                try:
                    session.add(entry)

                    session.commit()
                    return CreatedKeyModel(
                        system_id=credentials.system_id,
                        application_id=app_id,
                        key_hint=credentials.key_hint,
                        api_key=key,
                        expiry=credentials.expiry
                    )
                except sqlalchemy.exc.IntegrityError:
                    raise HTTPException(status.HTTP_409_CONFLICT, 'User already exists')

    def validate(self, credentials: KeyCredentials) -> bool: 
        with sqlmodel.Session(self.sql_engine) as session:
            statement = sqlmodel.select(HashedAPIKeys).where(HashedAPIKeys.application_id == credentials.application_id)
            key = session.exec(statement).first()

        salt = b'\0'*16
        if key:
            salt = key.salt

        calculated_hash = self.hash_function(credentials.api_key, salt)

        if key and calculated_hash == key.key_hash:
            return key.expiry is None or key.expiry > dt.datetime.now()
        
        return False
    
    @AuthenticationProviderPlugin.register_function
    def validate_api_key(self, application_id:UUID|str, api_key: str):
        if isinstance(application_id, str):
            application_id = UUID(application_id)
            
        if self.validate(KeyCredentials(application_id=application_id, api_key=api_key)):
            with sqlmodel.Session(self.sql_engine) as session:
                statement = sqlmodel.select(HashedAPIKeys).where(HashedAPIKeys.application_id == application_id)
                key = session.exec(statement).one()
                return key.system_id

        else:
            return None
        

    def hash_function(self, password: bytes | str, salt: bytes | str):
        # OWASP recommendation: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
        #   scrypt is selected, as it is in the standard library.
        if isinstance(password, str):
            password = password.encode()
        if isinstance(salt, str):
            salt = salt.encode()
        
        n = 2**17
        r = 8
        p = 1
        maxmem = n * 2 * r * 65
        dklen = 64

        return scrypt(password, salt=salt, n=n, r=r, p=p, maxmem=maxmem, dklen=dklen)
