from ..authorization.auth import auth_scope
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from .restapi import APIApplication
from ..authorization import models

def load_routes(api_app: APIApplication):

    root_router = APIRouter(include_in_schema=False)
    @root_router.get('/')
    async def docs_redirect():
        return RedirectResponse('/docs')
    
    api_app.include_router(root_router)



    router = APIRouter(prefix=api_app._root_path, tags=['Platform Core'])

    @router.get('/hello', dependencies=[Depends(api_app.authorization.require_scope(['test']))])
    async def route_hello():
        return {"message": "Hello from main"}
    
    api_app.include_router(router)



    auth_router = APIRouter(prefix=api_app._root_path+'/auth', tags=["Authorization"])

    @auth_router.get('/entities')
    async def get_entities():
        return api_app.authorization.get_all_entities()

    @auth_router.post('/entities')
    async def add_entity(entity: models.EntityBase):
        return api_app.authorization.add_entity(entity)
    
    @auth_router.get('/entities/{uuid}')
    async def get_entity_details(uuid: str):
        return api_app.authorization.get_entity_details(uuid)
    
    @auth_router.post('/entities/{uuid}/provider')
    async def connect_entity_idp(uuid: str, provider: models.ProviderIdentityBase):
        return api_app.authorization.connect_entity_idp(uuid, provider)
    
    @auth_router.get('/providers')
    async def get_identity_providers():
        return api_app.authorization.get_identity_providers()
    
    @auth_router.get('/providers/{name}')
    async def get_idp_details(name: str):
        return api_app.authorization.get_idp_details(name)

    api_app.include_router(auth_router)
