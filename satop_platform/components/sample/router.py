from fastapi import APIRouter

from ..restapi import APIApplication
from .sample import test


def create_router():
    router = APIRouter(prefix="/sample", tags=["Sample component with API"])

    @router.get("/hw", name="Hello Function")
    def hello():
        """
        Description of hello function
        """
        return {"message": test()}

    return router


def init(api_app: APIApplication):
    api_app.include_route(create_router())
