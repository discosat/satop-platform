import os
import logging
from hashlib import scrypt

import sqlmodel
import sqlalchemy.exc 
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from satop_platform.plugin_engine.plugin import AuthenticationProviderPlugin
from satop_platform.components.restapi import exceptions

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
    token: str

class PasswordUser(BaseModel):
    email: str

logger = logging.getLogger('plugin.password_authentication_provider')

class PasswordAuthenticationProvider(AuthenticationProviderPlugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        self.sql_engine = sqlmodel.create_engine('sqlite:///users.db')
        # sqlmodel.SQLModel.metadata.create_all(self.sql_engine)
        # if not inspect(self.sql_engine).has_table(HashedCredentials.__tablename__):
        HashedCredentials.__table__.create(self.sql_engine, checkfirst=True)

        self.api_router = APIRouter(prefix='/login', tags=['Password Authentication'])

        @self.api_router.post('/token',
                              response_model=Token,
                              responses= {
                                  status.HTTP_401_UNAUTHORIZED: {
                                      'detail': 'string'
                                  }
                              })
        async def __create_token(credentials: PasswordCredentials):
            if self.validate(credentials.email, credentials.password):
                return Token(token = self.create_auth_token(credentials.email))
            
            raise exceptions.InvalidCredentials

        @self.api_router.post('/user',
                              status_code=status.HTTP_201_CREATED,
                              responses= {
                                  status.HTTP_409_CONFLICT: {
                                      'detail': 'string'
                                  },
                                  status.HTTP_201_CREATED: {}
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
                    return Response(status_code=status.HTTP_201_CREATED)
                except sqlalchemy.exc.IntegrityError:
                    raise HTTPException(status.HTTP_409_CONFLICT, 'User already exists')
        
        @self.api_router.get('/users', response_model=list[PasswordUser])
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
