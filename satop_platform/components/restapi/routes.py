from fastapi import APIRouter

from .restapi import app, _api_config, _root_path
from core import config
from fastapi.responses import RedirectResponse

def include_route(router:APIRouter,  *args, **kwargs):
    app.include_router(router, prefix=_root_path, *args, **kwargs)

def load_routes():
    router = APIRouter(prefix=_root_path, tags=['Platform Core'])

    @router.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}

    app.include_router(router)

    well_known_router = APIRouter(prefix='/.well-known', tags=['.well-known'])

    @well_known_router.get('/ni/')
    async def well_known_ni_base():
        return RedirectResponse(f'/api/log/artifacts/ni/')

    @well_known_router.get('/ni/{ni}')
    async def well_known_ni_redirect(ni):
        return RedirectResponse(f'/api/log/artifacts/ni/{ni}')
    
    app.include_router(well_known_router)

