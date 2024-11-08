import logging
from fastapi import APIRouter
from ..restapi import routes
from . import models

logger = logging.getLogger(__name__)


def init():
    logger.info('Setting up system logger')

    router = APIRouter(
        prefix='/log',
        tags=['Logging']
    )

    @router.post('/events', status_code=201)
    def log_event(event_triplet: models.Triplet):
        logger.info(event_triplet)
        return 'Created'
    
    routes.include_route(router)
