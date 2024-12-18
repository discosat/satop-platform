from __future__ import annotations
import logging
import hashlib
import os
import shutil
from typing import IO
from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
import sqlalchemy
import sqlmodel
from sqlalchemy.engine import Engine
import re

from . import models

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.component_initializer import SatOPComponents

ARTIFACT_DIR = './artifact_data/'

logger = logging.getLogger(__name__)

class Syslog:
    db: Engine
    def __init__(self, components: SatOPComponents):
        logger.info('Setting up system logger')
        
        self.db = sqlmodel.create_engine('sqlite:///artifacts.db')
        sqlmodel.SQLModel.metadata.create_all(self.db, [models.ArtifactStore.__table__])

        router = APIRouter(
            prefix='/log',
            tags=['Logging']
        )

        @router.post('/events')
        async def new_log_event(event: models.Event):
            self.log_event(event)
            return 'OK'

        @router.post('/artifacts', status_code=201)
        def upload_artifact(file: UploadFile):
            try:
                return self.create_artifact(file.file, file.filename)
            except sqlalchemy.exc.IntegrityError: 
                raise HTTPException(status_code=status.HTTP_200_OK, detail='Artifact already exists. Reupload not neccessary')

        @router.get('/artifacts/{hash}')
        def get_artifact(hash: str):
            file = self.get_file_path(hash)
            logger.debug(f'Getting artifact file at "{file}"')

            if not os.path.exists(file):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Artifact not found')

            return FileResponse(file)
        
        @router.get("/artifacts")
        def get_artifacts():
            with sqlmodel.Session(self.db) as session:
                statement = sqlmodel.select(models.ArtifactStore)
                return session.exec(statement).all()


        components.api.include_router(router)

    def log_event(self, event: models.Event):
        # TODO: check that the subject and object exists (user, system, artifact)
        logger.info(f'Logged event: {event.model_dump_json()}')
    
    def get_file_path(self, hash):
        return os.path.join(ARTIFACT_DIR, re.sub(r'[^0-9a-z]', '_', hash.lower()))

    def create_artifact(self, file:IO[bytes], filename:str):
        sha1 = hashlib.sha1(file.read()).hexdigest()

        size = file.seek(0,2)

        file_model = models.ArtifactStore(sha1 = sha1, name = filename, size = size)
        logger.debug(f'Received new artefact {file_model.model_dump()}')
        model_copy = file_model.model_copy()

        with sqlmodel.Session(self.db) as session:
            session.add(file_model)
            session.commit()

        if not os.path.exists(ARTIFACT_DIR):
            os.mkdir(ARTIFACT_DIR)
        
        with open(os.path.join(ARTIFACT_DIR, sha1.lower()), 'wb+') as out_file:
            file.seek(0)
            shutil.copyfileobj(file, out_file)
            out_file.close()
        
        return model_copy

    def get_artifact(self, hash):
        with sqlmodel.Session(self.db) as session:
            statement = sqlmodel.select(models.ArtifactStore)\
                .where(models.ArtifactStore.sha1 == hash)
            file_model = session.exec(statement).first()
            if not file_model:
                return None, None

        with open(self.get_file_path(hash), 'rb') as f:
            data = f.read()
        
        return file_model, data
