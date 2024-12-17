import logging
import hashlib
import os
import shutil
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request, status
from fastapi.responses import FileResponse
import sqlalchemy
import sqlmodel
import re
from ..restapi import APIApplication
from . import models

ARTIFACT_DIR = './artifact_data/'

logger = logging.getLogger(__name__)


def log_event(event: models.Event):
    logger.info(f'Logged event: {event.model_dump_json()}')

def create_artifact(file, filename):
    pass


def init(rest_app: APIApplication):
    logger.info('Setting up system logger')
    
    db = sqlmodel.create_engine('sqlite:///artifacts.db')
    sqlmodel.SQLModel.metadata.create_all(db, [models.ArtifactStore.__table__])

    router = APIRouter(
        prefix='/log',
        tags=['Logging']
    )

    @router.post('/events')
    async def new_log_event(event: models.Event):
        log_event(event)
        return 'OK'

    @router.post('/artifacts', status_code=201)
    def upload_artifact(file: Optional[UploadFile]):
        sha1 = hashlib.sha1(file.file.read()).hexdigest()

        file_model = models.ArtifactStore(sha1=sha1, name=file.filename, size=file.size)
        logger.debug(f'Received new artefact {file_model.model_dump()}')
        dump = file_model.model_dump_json()
        
        try:
            with sqlmodel.Session(db) as session:
                session.add(file_model)
                session.commit()
        except sqlalchemy.exc.IntegrityError: 
            raise HTTPException(status_code=status.HTTP_200_OK, detail='Artifact already exists. Reupload not neccessary')
        
        if not os.path.exists(ARTIFACT_DIR):
            os.mkdir(ARTIFACT_DIR)
        
        with open(os.path.join(ARTIFACT_DIR, sha1.lower()), 'wb+') as out_file:
            file.file.seek(0)
            shutil.copyfileobj(file.file, out_file)
            out_file.close()

        return dump

    @router.get('/artifacts/{hash}')
    def get_artifact(hash: str):
        file = os.path.join(ARTIFACT_DIR, re.sub(r'[^0-9a-z]', '_', hash.lower()))
        logger.debug(f'Getting artifact file at "{file}"')

        if not os.path.exists(file):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Artifact not found')

        return FileResponse(file)

    rest_app.include_router(router)
