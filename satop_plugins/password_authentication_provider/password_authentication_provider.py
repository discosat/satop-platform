import os
import logging
from hashlib import scrypt

import sqlmodel
import sqlalchemy.exc 
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from satop_platform.plugin_engine.plugin import AuthenticationProviderPlugin
from satop_platform.components.restapi import exceptions
from satop_platform.core import config

# from .password_authentication_provider import models
from pydantic import BaseModel

class HashedCredentials(sqlmodel.SQLModel, table=True):
    email: str = sqlmodel.Field(unique=True, primary_key=True)
    password_hash: bytes
    salt: bytes

class PasswordCredentials(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str

class PasswordUser(BaseModel):
    email: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "hello@example.com"
                }
            ]
        }
    }

logger = logging.getLogger('plugin.password_authentication_provider')

class PasswordAuthenticationProvider(AuthenticationProviderPlugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)
        
        engine_path = self.data_dir / 'users.db'
        engine_path.parent.mkdir(exist_ok=True, parents=True)
        self.sql_engine = sqlmodel.create_engine('sqlite:///'+str(engine_path))
        
        # sqlmodel.SQLModel.metadata.create_all(self.sql_engine)
        # if not inspect(self.sql_engine).has_table(HashedCredentials.__tablename__):
        HashedCredentials.__table__.create(self.sql_engine, checkfirst=True)

        self.api_router = APIRouter(prefix='/login', tags=['Authentication'])

        @self.api_router.post('/token',
                              response_model=Token,
                              summary='Request an access and refresh token.',
                              description='Obtain a new access token by providing valid user credentials (email and password).',
                              response_description='A fresh JWT token.',
                              responses= {
                                  **exceptions.InvalidCredentials().response
                              })
        async def __create_token(credentials: PasswordCredentials):
            if self.validate(credentials.email, credentials.password):
                return Token(access_token = self.create_auth_token(user_id=credentials.email),
                             refresh_token = self.create_refresh_token(user_id=credentials.email))
            
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


        @self.api_router.post('/user',
                              status_code=status.HTTP_201_CREATED,
                              summary='Create a new user.',
                              description='Create a new user with the provided credentials, provided that the email is not already registered.',
                              response_model=PasswordUser,
                              responses= {
                                  status.HTTP_409_CONFLICT: {
                                      'description': 'User already exists',
                                  },
                              },
                            #   dependencies=[
                            #       Depends(auth_scope(['users.create']))
                            #   ]
                             )
        async def __create_user(credentials: PasswordCredentials):
            with sqlmodel.Session(self.sql_engine) as session:
                salt = os.urandom(16)
                hashed_pass = self.hash_function(credentials.password, salt)
                entry = HashedCredentials(email=credentials.email, password_hash=hashed_pass, salt=salt)
                try:
                    session.add(entry)

                    session.commit()
                    return PasswordUser(email=credentials.email)
                except sqlalchemy.exc.IntegrityError:
                    raise HTTPException(status.HTTP_409_CONFLICT, 'User already exists')
        
        @self.api_router.get(
                '/users', 
                response_model=list[PasswordUser],
                summary='List all users',
                description='List all registered user emails.',
                response_description="List of all users that have been registered with the email-password authentication provider.",
            )
        async def __get_all_users():
            return self.get_users()

    def get_user(self, email: str):
        with sqlmodel.Session(self.sql_engine) as session:
            statement = sqlmodel.select(HashedCredentials).where(HashedCredentials.email == email)
            user = session.exec(statement).first()
            return user

    def get_users(self):
        with sqlmodel.Session(self.sql_engine) as session:
            statement = sqlmodel.select(HashedCredentials)
            users = session.exec(statement).all()
            return list(map(lambda u: PasswordUser(email=u.email) , users))

    def validate(self, email: str, password: str) -> bool: 
        user = self.get_user(email)
        if not user: 
            return False
        
        calculated_hash = self.hash_function(password, user.salt)

        if calculated_hash == user.password_hash:
            return True
        
        return False

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
