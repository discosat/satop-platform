
from typing import Annotated, Iterable
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from . import exceptions

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from sqlmodel.orm import Session
from models import User2 as User
import logging

from passlib.context import CryptContext

SECRET_KEY = "INSERT_SECRET_KEY_HERE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MIMUTES = 30

class UserCreate(BaseModel):
  username: str
  email: str
  password: str
  full_name: str = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

auth_scheme = HTTPBearer(
    scheme_name='jwt_token',
    description='JWT Token',
)

# Missing:
# - Token creation
# - Token validation
# - Token scopes (User Scopes)
# - Token expiration/refresh
# - Make sure Token can decode (So we can validate it)

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

def create_refresh(token):
    pass

#@app.get("/verify-token/{token}")
#async def verify_token(token: str):
#    verify_token(token=token)
#    return {"message": "Token is valid"}

def validate_token(token:str):
    pass

def auth_scope(needed_scopes: Iterable[str] | str):
    def f(credentials: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)]):
        token = credentials.credentials
        print(token)

        # Verify Token

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

def create_user(db: Session, user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, email=user.email, full_name=user.full_name, hashed_password=hashed_password)
    try :
      db.add(db_user)
      db.commit()
    except Exception as e:
        logging.error(e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating user")