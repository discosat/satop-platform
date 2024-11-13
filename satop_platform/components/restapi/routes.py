from fastapi import APIRouter

from .restapi import api_app, _api_config, _root_path
from core import config

def include_route(router:APIRouter,  *args, **kwargs):
    api_app.include_router(router, prefix=_root_path, *args, **kwargs)

def load_routes():
    # router = APIRouter(prefix=_root_path, tags=['Platform Core'])
    router = APIRouter()

    @router.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}


    api_app.include_router(router)





