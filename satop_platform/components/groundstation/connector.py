from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import uuid

from dataclasses import dataclass, field
from asyncio import Event, Queue

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.websockets import WebSocketState
from pydantic import BaseModel

from satop_platform.components.restapi.restapi import APIApplication

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from satop_platform.core.component_initializer import SatOPComponents

logger = logging.getLogger(__name__)

@dataclass
class GroundstationRegistrationItem:
    name: str
    websocket: WebSocket
    busy: bool = False
    out_queue: Queue[tuple[uuid.UUID, dict]] = field(default_factory=Queue)
    waiting_responses: dict[uuid.UUID, any] = field(default_factory=dict)

@dataclass
class GroundstationsListItem:
    id: uuid.UUID
    name: str

@dataclass
class ResponseError:
    status: int
    details: str

@dataclass
class ResponseQueueItem:
    event: Event
    data: dict | None = None
    error: ResponseError | None = None

class GroundstationConnector:
    registered_groundstations: dict[uuid.UUID, GroundstationRegistrationItem]

    def __init__(self, components: SatOPComponents):
        self.registered_groundstations = dict()
        self.__setup_routes(components.api)

    async def __websocket_send(self, gs_id:uuid.UUID, data:dict):
        request_id = uuid.uuid4()

        gs = self.registered_groundstations.get(gs_id)
        if not gs:
            raise RuntimeError

        await gs.out_queue.put((request_id, data))
        logger.debug(f'Added request {request_id} to queue')

        return request_id

    async def __websocket_receive_response(self, gs_id:uuid.UUID, request_id:uuid.UUID):
        gs = self.registered_groundstations.get(gs_id)
        if not gs:
            raise RuntimeError
        
        ev = asyncio.Event()

        gs.waiting_responses[request_id] = ResponseQueueItem(event=ev)

        logger.debug(f'Waiting for response to {request_id}')

        await ev.wait()
        data:dict = gs.waiting_responses[request_id].data
        error:ResponseError = gs.waiting_responses[request_id].error

        # Remove waiting
        del gs.waiting_responses[request_id]

        # Return response
        return data, error




    def __setup_routes(self, api: APIApplication):
        router = APIRouter(prefix='/gs', tags=['Groundstation'])

        @router.websocket('/ws')
        async def ws_connect_gs(websocket: WebSocket):
            """Groundstation registeres itself on the platform

            Args:
                websocket (WebSocket): _description_
            """
            await websocket.accept()
            logger.info('Incoming websocket')

            # Get groundstation connection message
            data_raw = await websocket.receive_text()
            logger.info(f'RAW data > {data_raw}')
            data = json.loads(data_raw)
            assert isinstance(data,dict)

            name = data.get('name')
            msg_type = data.get('type')

            assert (msg_type == "hello" 
                and name is not None
            )

            gs_id = uuid.uuid4()

            self.registered_groundstations[gs_id] = GroundstationRegistrationItem(name, websocket)
            logger.info(f"Connected to GS '{name}' with UUID {gs_id}")
            
            async def read_task():
                while True:
                    message = await websocket.receive_json()
                    in_response_to = uuid.UUID(message.get('in_response_to'))

                    if in_response_to:
                        logger.debug(f'Got response message to {in_response_to}: {message}')
                        res:ResponseQueueItem = self.registered_groundstations[gs_id].waiting_responses.get(in_response_to)
                        if res is None:
                            logger.debug(f'Noone is waiting for response {in_response_to}')
                            logger.debug(f'Current waiting: {self.registered_groundstations[gs_id].waiting_responses}')
                            continue
                        logger.debug(str(res))

                        data = message.get('data', dict())
                        error = message.get('error', None)
                        res.data = data
                        res.error = error
                        res.event.set()
                        logger.debug(f'Response set to {res}')
                    else:
                        logger.debug(f'Got message: {message}')
                        pass # route to handler
            
            async def write_task():
                while True:
                    q = self.registered_groundstations[gs_id].out_queue
                    req_id, data = await q.get()
                    msg = {
                        'request_id': str(req_id),
                        'data': data
                    }
                    logger.debug(f'Transmitting to GS: {msg}')
                    await websocket.send_json(msg)

            try:
                t1 = asyncio.create_task(read_task())
                t2 = asyncio.create_task(write_task())

                await t1
                await t2
                    
            except WebSocketDisconnect:
                logger.info(f"GS Client {name} ({gs_id}) disconnected")
            finally:
                del self.registered_groundstations[gs_id]
            
            logger.info(f"Removed WS for GS {name} ({gs_id})")

        @router.get('/stations')
        async def get_groundstations():
            """Other clients can get a list of groundstations/URLs to connect to them
            """
            stations: list[GroundstationsListItem] = []
            for id,item in self.registered_groundstations.items():
                stations.append(
                    GroundstationsListItem(
                        id=id,
                        name=item.name
                    ))

            return stations

        @router.post('/stations/{gs_uuid}/control')
        async def control_groundstation(gs_uuid: uuid.UUID, data:dict, req:Request):
            gs = self.registered_groundstations.get(gs_uuid)
            if not gs:
                raise HTTPException(status.HTTP_404_NOT_FOUND)
            
            # TODO: Maybe add a delay to see if resource is freed after a bit before raising the error
            if gs.busy:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail='Groundstation is busy. Try again later')
            gs.busy = True

            try:
                data = await req.json()

                logger.debug(f"Received control data: {data}")

                req_id = await self.__websocket_send(gs_uuid, data)
                logger.debug(f"Created request with ID: {req_id}")
                response, error = await self.__websocket_receive_response(gs_uuid, req_id)
                if error:
                    logger.warning(f'Received error from ground station: {dataclasses.asdict(error)}')
                else:
                    logger.debug(f"Received response: {response}")
            except Exception as e:
                response = e
            finally:
                gs.busy = False

            if error:
                raise HTTPException(502, detail=error)
            return response

        api.include_router(router)

"""

groundstation -> platform : connect through websocket

webbrowser -> platform : send control to groundstation {id}
platform -> groundstation : forward control message to gs over ws

"""