from __future__ import annotations
import logging
import hashlib
import os
import shutil
from typing import IO
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
import sqlalchemy
import sqlmodel
from sqlalchemy.engine import Engine
import re
from satop_platform.components.restapi import exceptions
from satop_platform.core import config

from satop_platform.components.syslog import models

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from satop_platform.core.satop_application import SatOPApplication

ARTIFACT_DIR = config.get_root_data_folder() / 'artifact_data'

logger = logging.getLogger(__name__)

class Syslog:
    db: Engine
    def __init__(self, app: SatOPApplication):
        logger.info('Setting up system logger')

        engine_path = config.get_root_data_folder() / 'database/artifacts.db'
        engine_path.parent.mkdir(exist_ok=True)
        self.db = sqlmodel.create_engine('sqlite:///'+str(engine_path))
        
        sqlmodel.SQLModel.metadata.create_all(self.db, [models.ArtifactStore.__table__])

        router = APIRouter(
            prefix='/log',
            tags=['Logging']
        )

        @router.post('/events',
                dependencies=[Depends(app.auth.require_scope('satop.log.write'))],
                summary="Add an event to the log",
                description="Add a new event to the system log. Events consist of relationships of RDF triples. If the predicate or object is omitted in a triple, the event action itself will referenced here.\n\nIf omitted, 'id' and 'timestamp' wil be automatically generated.",
                response_description="The full event with timestamp and ID added if they were omitted in the original request.",
            )
        async def new_log_event(event: models.Event):
            self.log_event(event)
            return event
        
        @router.get('/events',
                dependencies=[Depends(app.auth.require_scope('satop.log.read'))],
                summary="Read events from the log",
                description="Not implemented",
            )
        async def get_log_events():
            raise exceptions.NotImplemented

        @router.post('/artifacts', 
                dependencies=[Depends(app.auth.require_scope('satop.log.write'))],
                summary="Upload new artifact",
                description="Upload a file as an artifact for referencing in the logging system.",
                response_description="Successful upload. Contains calculated SHA1-hash of the artifact to use in log events.",
                status_code=status.HTTP_201_CREATED,
                response_model=models.ArtifactStore,
                responses={
                    status.HTTP_200_OK: {
                        'description': 'Artifact already exists. Content "detail" includes file SHA1 after last period.',
                        'content': {
                            'application/json': {
                                'example': {"detail": "Artifact already exists. Reupload not neccessary. 5372ef2198557450d7424ba9c36151d932fb45f0"}
                            }
                        }
                    }
                }
            )
        def upload_artifact(file: UploadFile):
            try:
                artifact = self.create_artifact(file.file, file.filename)
                return JSONResponse(
                    status_code=status.HTTP_201_CREATED,
                    content=artifact.model_dump(),
                    headers={ 'Location': './artifacts/'+artifact.sha1}
                )
            except sqlalchemy.exc.IntegrityError as e: 
                raise HTTPException(status_code=status.HTTP_200_OK, detail=f'Artifact already exists. Reupload not neccessary. {e.params[0]}')

        @router.get('/artifacts/{hash}',
                dependencies=[Depends(app.auth.require_scope('satop.log.read'))],
                summary='Download an artifact',
                description='Get a previously uploaded artifact by its SHA1 hash.',
                response_class=FileResponse,
                response_description="(Binary) content of the requested artifact",
                responses={**exceptions.NotFound("Artifact not found").response}

            )
        def get_artifact(hash: str):
            file = self.get_file_path(hash)
            logger.debug(f'Getting artifact file at "{file}"')

            if not os.path.exists(file):
                raise exceptions.NotFound("Artifact not found")

            return FileResponse(file)
        
        @router.get("/artifacts",
            dependencies=[Depends(app.auth.require_scope('satop.log.read'))])
        def get_artifacts():
            with sqlmodel.Session(self.db) as session:
                statement = sqlmodel.select(models.ArtifactStore)
                return session.exec(statement).all()


        app.api.include_router(router)

    def log_event(self, event: models.Event):
        # TODO: check that the subjects and objects exists (user, system, artifact)
        ev = event.descriptor
        ts = event.timestamp
        rs = event.relationships
        action = models.Action(descriptor=ev)

        triples: list[models.Triple] = list()

        triples.append(models.Triple(subject=action, predicate=models.Predicate(descriptor='loggedAt'), object=ts))

        for r in rs:
            match r:
                case models.EventSubjectRelationship():
                    triples.append(models.Triple(subject=r.subject, predicate=r.predicate, object=action))
                case models.EventObjectRelationship():
                    triples.append(models.Triple(subject=action, predicate=r.predicate, object=r.object))
                case models.Triple():
                    triples.append(r)
                case _:
                    logger.warning(f'Unkown relationship for event: {r}')

        for t in triples:
            logger.info(f'Logged Event relation: {t.model_dump_json()}')
    
    def get_file_path(self, hash):
        return os.path.join(ARTIFACT_DIR, re.sub(r'[^0-9a-z]', '_', hash.lower()))

    def create_artifact(self, file:IO[bytes], filename:str):
        sha1 = hashlib.sha1(file.read()).hexdigest()

        size = file.seek(0,2)

        file_model = models.ArtifactStore(sha1 = sha1, name = filename, size = size)
        logger.debug(f'Received new artefact {file_model.model_dump()}')

        with sqlmodel.Session(self.db) as session:
            session.add(file_model)
            session.commit()
            session.refresh(file_model)

        if not os.path.exists(ARTIFACT_DIR):
            os.mkdir(ARTIFACT_DIR)
        
        with open(os.path.join(ARTIFACT_DIR, sha1.lower()), 'wb+') as out_file:
            file.seek(0)
            shutil.copyfileobj(file, out_file)
            out_file.close()
        
        return file_model

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
