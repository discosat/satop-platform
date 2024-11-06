from fastapi import APIRouter

from .restapi import app, _api_config, _root_path
from core import config

def include_route(router:APIRouter,  *args, **kwargs):
    app.include_router(router, prefix=_root_path, *args, **kwargs)

def load_routes():
    router = APIRouter(prefix=_root_path, tags=['Platform Core'])

    @router.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}


    app.include_router(router)





