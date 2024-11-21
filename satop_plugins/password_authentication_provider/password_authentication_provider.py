import os
import logging
from collections.abc import Callable

from fastapi import APIRouter

from satop_platform.plugin_engine.plugin import Plugin
from satop_platform.components.restapi import exceptions

# from .password_authentication_provider import models
from pydantic import BaseModel

class Credentials(BaseModel):
    username: str
    password: str

logger = logging.getLogger('plugin.password_authentication_provider')

class PasswordAuthenticationProvider(Plugin):
    create_auth_token: Callable[[str, str], str] = lambda identifier_key, identifier_value: 'create_auth_token has not been initialized'

    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)
    
    def pre_init(self):
        pass

    def init(self):
        self.api_router = APIRouter()

        @self.api_router.post('/token')
        async def __create_token(credentials: Credentials):
            if self.validate(credentials.username, credentials.password):
                return {'token': self.create_auth_token('username', credentials.username)}
            
            raise exceptions.InvalidCredentials

    def post_init(self):
        pass


    def db_connect(self):
        pass

    def get_user(self, username: str):
        fake_users = {
            'test': {'name': 'Test user', 'password': '1234'},
            'demo': {'name': 'Demo account', 'password': 'omed'}
        }
        return fake_users.get(username, None)

    def validate(self, username: str, password: str) -> bool: 
        user = self.get_user(username)
        if not user: 
            return False
        
        if not user.get('password') == password:
            return False
        
        return True
