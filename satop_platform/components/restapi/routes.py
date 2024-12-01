from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from .restapi import APIApplication

def load_routes(api_app: APIApplication):

    root_router = APIRouter(include_in_schema=False)
    @root_router.get('/')
    async def docs_redirect():
        return RedirectResponse('/docs')
    
    api_app.include_router(root_router)

    router = APIRouter(tags=['Platform Core'])

    @router.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}

    api_app.include_router(router)





