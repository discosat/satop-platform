
from typing import Annotated, Iterable
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from . import exceptions

auth_scheme = HTTPBearer(
    scheme_name='jwt_token',
    description='JWT Token',
)

def decode_token(token):
    return jwt.decode(token)

def create_access_token(token):
    pass

def create_refresh(token):
    pass

def validate_token(token:str):
    pass

def auth_scope(needed_scopes: Iterable[str] | str):
    def f(credentials: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)]):
        token = credentials.credentials
        print(token)

        token_scopes = set() # TODO: fetch user/token scopes

        if (isinstance(needed_scopes, str) and needed_scopes in token_scopes) \
            or (set(needed_scopes).issubset(token_scopes)):
            return True
        
        raise exceptions.InsufficientPermissions()

    return f

async def get_user(token: Annotated[str, Depends(auth_scheme)]):
    decoded = decode_token(token)

    if not decoded:
        raise exceptions.InvalidCredentials()

    return decoded