import logging
import hashlib
from uuid import uuid4
from fastapi import APIRouter, File, UploadFile
from ..restapi import APIApplication
from . import models

logger = logging.getLogger(__name__)


def init(rest_app: APIApplication):
    logger.info('Setting up system logger')

    router = APIRouter(
        prefix='/log',
        tags=['Logging']
    )

    @router.post('/events', status_code=201)
    def log_event(event_triplet: models.Triplet):
        logger.info(event_triplet)
        return 'Created'
    
    @router.post('/artifacts', status_code=201)
    def new_artifact(file: UploadFile):
        logger.debug(f'Received new artefact "{file.filename}" ({file.size})')
        hash = {
            'md5': hashlib.md5(file.file.read()).hexdigest(),
            'sha1': hashlib.sha1(file.file.read()).hexdigest(),
            'sha256': hashlib.sha256(file.file.read()).hexdigest()
        }
        uuid = uuid4()

        # TODO: save artifact
        # TODO: track in a database

        return {
            'hash': hash,
            'uuid': uuid,
            'ni': f'ni:///sha-256;{hash.get('sha256')}'
        }


    @router.get('/artifacts/{uuid}')
    def get_artifact(uuid: str):
        pass
    
    @router.get('/artifacts/ni/{alg}/{hash}')
    def get_artifact_ni(alg:str, hash:str):
        pass

    rest_app.include_router(router)
