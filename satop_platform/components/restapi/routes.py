from fastapi import APIRouter, Depends

from .auth import auth_scope

from .restapi import APIApplication

def load_routes(api_app: APIApplication):

    router = APIRouter(prefix=api_app._root_path, tags=['Platform Core'])

    @router.get('/hello', dependencies=[Depends(auth_scope(['test']))])
    async def route_hello():
        return {"message": "Hello from main"}

    api_app.include_router(router)





