from fastapi import APIRouter
from .sample import test
from ..restapi import include_route, mount_plugin_router

def create_router():
    router = APIRouter(
        prefix='/sample',
        tags=['Sample component with API']
    )

    @router.get('/hw', name='Hello Function')
    def hello():
        '''
        Description of hello function
        '''
        return {'message': test()}

    return router


def init():
    include_route(create_router())

    r2 = APIRouter()

    @r2.get('/hw', name='Hell Function')
    def hell():
        '''
        Description of hello function
        '''
        return {'message': test()}

    mount_plugin_router('sample', r2)