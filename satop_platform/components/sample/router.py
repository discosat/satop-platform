from fastapi import APIRouter
from .sample import test
from ..restapi import include_route

def create_router():
    router = APIRouter(
        prefix='/sample',
        tags=['Sample component with API']
    )

    @router.get('/hw')
    def hello():
        '''
        Description of hello function
        '''
        return {'message': test()}

    return router


def init():
    include_route(create_router())