from fastapi import APIRouter

from .restapi import APIApplication

def load_routes(api_app: APIApplication):

    router = APIRouter(prefix=api_app._root_path, tags=['Platform Core'])

    @router.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}

    api_app.include_router(router)





