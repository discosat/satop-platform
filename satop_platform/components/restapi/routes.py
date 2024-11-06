from fastapi import APIRouter

from .restapi import app
from core import config

_api_config = config.load_config('api.yml')
_root_path = _api_config.get('root_path', '/api')


def include_route(router:APIRouter,  *args, **kwargs):
    app.include_router(router, prefix=_root_path, *args, **kwargs)

def load_routes():
    router = APIRouter(prefix=_root_path, tags=['Platform Core'])

    @router.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}


    app.include_router(router)





