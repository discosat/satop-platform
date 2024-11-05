from fastapi import APIRouter

from .restapi import app

def include_route(router:APIRouter,  *args, **kwargs):
    app.include_router(router, prefix='/api', *args, **kwargs)

def load_routes():
    @app.get('/hello')
    async def route_hello():
        return {"message": "Hello from main"}


