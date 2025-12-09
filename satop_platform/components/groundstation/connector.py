from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from asyncio import Event, Queue
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from satop_platform.components.restapi import exceptions
from satop_platform.components.restapi.restapi import APIApplication

if TYPE_CHECKING:
    from satop_platform.core.satop_application import SatOPApplication

logger = logging.getLogger(__name__)


@dataclass
class FramedContent:
    frames: list[dict | str | bytes]
    header_data: dict[str, any] | None = None


@dataclass
class GroundstationRegistrationItem:
    name: str
    websocket: WebSocket
    busy: bool = False
    out_queue: Queue[tuple[UUID, dict | FramedContent, ProxyHeader | None]] = field(
        default_factory=Queue
    )
    waiting_responses: dict[UUID, ResponseQueueItem] = field(default_factory=dict)


@dataclass
class GroundstationsListItem:
    id: UUID
    name: str


@dataclass
class ResponseQueueItem:
    event: Event
    data: dict | None = None
    error: dict | None = None


@dataclass
class TerminalRegistrationItem:
    name: str
    read_only: bool = False
    rw_client: WebSocket | None = None
    r_clients: list[WebSocket] = field(default_factory=list)

    def get_all_clients(self):
        clients: list[WebSocket] = list()
        if self.rw_client:
            clients.append(self.rw_client)
        for c in self.r_clients:
            clients.append(c)
        return clients


@dataclass
class ProxyHeader:
    origin: str
    authenticated_user: str


class GroundstationConnector:
    registered_groundstations: dict[UUID, GroundstationRegistrationItem]
    registered_terminals: dict[tuple[UUID, str], TerminalRegistrationItem]

    def __init__(self, app: SatOPApplication):
        self.app = app
        self.registered_groundstations = dict()
        self.registered_terminals = dict()
        self.__setup_routes(app.api)

    async def __websocket_send(
        self,
        gs_id: UUID,
        data: dict | FramedContent,
        proxy_header: ProxyHeader | None = None,
    ):
        request_id = uuid4()

        gs = self.registered_groundstations.get(gs_id)
        if not gs:
            raise RuntimeError

        await gs.out_queue.put((request_id, data, proxy_header))
        logger.debug(f"Added request {request_id} to queue")

        return request_id

    async def __websocket_receive_response(self, gs_id: UUID, request_id: UUID):
        gs = self.registered_groundstations.get(gs_id)
        if not gs:
            raise RuntimeError

        ev = asyncio.Event()

        gs.waiting_responses[request_id] = ResponseQueueItem(event=ev)

        logger.debug(f"Waiting for response to {request_id}")

        async with asyncio.timeout(60):
            await ev.wait()
            data = gs.waiting_responses[request_id].data
            error = gs.waiting_responses[request_id].error

        # Remove waiting
        del gs.waiting_responses[request_id]

        # Return response
        return data, error

    def __setup_routes(self, api: APIApplication):
        router = APIRouter(prefix="/gs", tags=["Groundstation"])

        @router.websocket("/ws")
        async def ws_connect_gs(websocket: WebSocket):
            """Groundstation registeres itself on the platform

            Args:
                websocket (WebSocket): _description_
            """
            await websocket.accept()
            logger.debug("Incoming websocket")

            # Get groundstation connection message
            data_raw = await websocket.receive_text()
            logger.debug(f"RAW data > {data_raw}")
            hello_data = json.loads(data_raw)
            assert isinstance(hello_data, dict)

            name = hello_data.get("name")
            msg_type = hello_data.get("type")
            access_token = hello_data.get("token")

            assert msg_type == "hello" and name is not None and access_token is not None

            try:
                token_payload = api.authorization.validate_token(access_token)

            except (exceptions.ExpiredToken, exceptions.InvalidToken) as e:
                logger.warning(f"GS Client authorization error: {e}")
                await websocket.send_json({"message": "authorization error"})
                await websocket.close(code=3000)
                return

            gs_id = token_payload.sub
            if gs_id:
                gs_id = UUID(str(gs_id))
            else:
                logger.warning("GS Client token missing 'sub':")
                await websocket.send_json({"message": "token missing sub"})
                await websocket.close(code=1002)
                return

            self.registered_groundstations[gs_id] = GroundstationRegistrationItem(
                name, websocket
            )

            await websocket.send_json({"message": "OK", "id": str(gs_id)})

            logger.info(f"Connected to GS '{name}' with UUID {gs_id}")

            async def read_task():
                while True:
                    message = await websocket.receive_json()
                    in_response_to = message.get("in_response_to")

                    if in_response_to:
                        in_response_to = UUID(str(in_response_to))
                        logger.debug(
                            f"Got response message to {in_response_to}: {message}"
                        )
                        res = self.registered_groundstations[
                            gs_id
                        ].waiting_responses.get(in_response_to)
                        if res is None:
                            logger.debug(
                                f"No one is waiting for response {in_response_to}"
                            )
                            logger.debug(
                                f"Current waiting: {self.registered_groundstations[gs_id].waiting_responses}"
                            )
                            continue
                        logger.debug(str(res))

                        data = message.get("data", dict())
                        error = message.get("error", None)
                        res.data = data
                        res.error = error
                        res.event.set()
                        logger.debug(f"Response set to {res}")
                    else:
                        logger.debug(f"Got message: {message}")
                        await self.handle_read_message_from_gs(gs_id, message)

            async def write_task():
                while True:
                    q = self.registered_groundstations[gs_id].out_queue
                    req_id, content, proxy_header = await q.get()
                    logger.debug(f"Write Task handling new message {req_id}")
                    match content:
                        case dict():
                            msg = {"request_id": str(req_id), "data": content}
                            if proxy_header:
                                msg["proxy_header"] = dataclasses.asdict(proxy_header)
                            logger.debug(f"Transmitting to GS ({gs_id}): {msg}")
                            await websocket.send_json(msg)
                        case FramedContent():
                            if content.header_data is None:
                                header_data = dict()
                            else:
                                header_data = content.header_data
                            header = {
                                "request_id": str(req_id),
                                "frames": len(content.frames),
                                "data": header_data,
                            }
                            if proxy_header:
                                header["proxy_header"] = dataclasses.asdict(
                                    proxy_header
                                )
                            logger.debug(f"[{req_id}] sending header frame")
                            await websocket.send_json(header)
                            logger.debug(f"[{req_id}] sent header frame")
                            for frame in content.frames:
                                match frame:
                                    case str():
                                        logger.debug(
                                            f"[{req_id}] sending content frame as text"
                                        )
                                        await websocket.send_text(frame)
                                    case bytes():
                                        logger.debug(
                                            f"[{req_id}] sending content frame as bytes"
                                        )
                                        await websocket.send_bytes(frame)
                                    case _:
                                        logger.debug(
                                            f"[{req_id}] sending content frame as JSON"
                                        )
                                        await websocket.send_json(frame)
                                logger.debug(f"[{req_id}] sent content frame")
                            logger.debug(f"[{req_id}] sent message")

            try:
                t1 = asyncio.create_task(read_task())
                t2 = asyncio.create_task(write_task())

                await asyncio.gather(t1, t2)

            except WebSocketDisconnect:
                logger.info(f"GS Client {name} ({gs_id}) disconnected")
            finally:
                del self.registered_groundstations[gs_id]
                terminals = []
                for k in self.registered_terminals.keys():
                    g, _ = k
                    if g == gs_id:
                        terminals.append(k)
                logger.debug(f"Closing {len(terminals)} terminals")
                for t in terminals:
                    await self.close_terminal(*t)

            logger.info(f"Removed WS for GS {name} ({gs_id})")

        @router.websocket("/terminal/{gs_id}/{term_id}")
        async def ws_connect_gs_term(websocket: WebSocket, gs_id: UUID, term_id: str):
            await websocket.accept()
            logger.debug("Incoming terminal websocket")

            # Get groundstation connection message
            data_raw = await websocket.receive_text()
            logger.debug(f"RAW data > {data_raw}")
            hello_data = json.loads(data_raw)
            assert isinstance(hello_data, dict)

            msg_type = hello_data.get("type")
            access_token = hello_data.get("token")

            assert msg_type == "connect_ro" or msg_type == "connect_rw"
            assert access_token is not None

            try:
                token_payload = api.authorization.validate_token(access_token)

            except (exceptions.ExpiredToken, exceptions.InvalidToken) as e:
                logger.warning(f"Terminal Client authorization error: {e}")
                await websocket.send_json({"error": "authorization error"})
                await websocket.close(code=3000)
                return

            user_id = token_payload.sub
            if user_id:
                user_id = UUID(str(user_id))
            else:
                logger.warning("Terminal Client token missing 'sub':")
                await websocket.send_json({"error": "token missing sub"})
                await websocket.close(code=1002)
                return

            reg_key = (gs_id, term_id)
            if reg_key not in self.registered_terminals:
                logger.warning(
                    "Terminal Client attempted connecting to non-existing terminal"
                )
                await websocket.send_json({"error": "non-existing terminal"})
                await websocket.close(code=1002)
                return

            can_write = False

            if msg_type == "connect_ro":
                self.registered_terminals[reg_key].r_clients.append(websocket)

            elif msg_type == "connect_rw":
                is_ro = self.registered_terminals[reg_key].read_only
                if not is_ro and self.registered_terminals[reg_key].rw_client is None:
                    self.registered_terminals[reg_key].rw_client = websocket
                    can_write = True

            try:
                while True:
                    command = await websocket.receive_text()

                    if can_write:
                        proxy_header = ProxyHeader(
                            "terminal client input", str(user_id)
                        )
                        data = {
                            "type": "terminal/stdin",
                            "terminal_id": term_id,
                            "command": command,
                        }
                        await self.send_to_gs(gs_id, data, proxy_header)

                        input_data = {
                            "direction": "input",
                            "author": str(user_id),
                            "content": command,
                        }

                        tasks = []
                        for c in self.registered_terminals[reg_key].get_all_clients():
                            tasks.append(asyncio.Task(c.send_json(input_data)))

                        if tasks:
                            await asyncio.wait(tasks)

                    else:
                        await websocket.send_json(
                            {"error": 401, "details": "Terminal is read-only"}
                        )

            except WebSocketDisconnect:
                logger.info("Terminal client disconnected")
            except:
                await websocket.close()
            finally:
                if self.registered_terminals[reg_key].rw_client == websocket:
                    self.registered_terminals[reg_key].rw_client = None

                try:
                    self.registered_terminals[reg_key].r_clients.remove(websocket)
                except:
                    pass

        @router.get(
            "/stations",
            response_model=list[GroundstationsListItem],
            summary="Get a list of registered groundstations",
            description="Returns a list of all registered and currently connected groundstations",
            response_description="List of groundstation names and UUIDs",
            dependencies=[Depends(api.authorization.require_login)],
        )
        async def get_groundstations():
            """Other clients can get a list of groundstations/URLs to connect to them"""
            stations: list[GroundstationsListItem] = []
            for id, item in self.registered_groundstations.items():
                stations.append(GroundstationsListItem(id=id, name=item.name))

            return stations

        @router.post(
            "/stations/{gs_uuid}/control",
            summary="Send control data to a groundstation",
            description="Send control data to a groundstation and wait for a response. The response will be returned to the client. \n"
            "\n"
            "The control data can be any JSON serializable object, but is expected to be written in a way that the groundstation can understand.\n",  # TODO: Unsure about the last bit
            response_description="Response from the groundstation",
            dependencies=[Depends(api.authorization.require_login)],
        )
        async def control_groundstation(gs_uuid: UUID, data: dict, request: Request):
            return await self.send_control(request, gs_uuid, data)

        @router.post(
            "/stations/{gs_uuid}/control_framed",
            summary="Send framed control data to a groundstation",
            description="Send control data to a groundstation and wait for a response. The response will be returned to the client. \n"
            "\n"
            "The control data can be any JSON serializable object, but is expected to be written in a way that the groundstation can understand.\n"
            "\n"
            "This is a test endpoint for sending framed data to the groundstation. The data is split into a header and multiple frames.\n"
            "The header contains metadata about the data and the frames contain the actual data. The groundstation is expected to reassemble the data and process it accordingly.\n"
            "\n"
            "The header data is expected to be a dictionary and the frames are expected to be a list of strings, bytes or dictionaries.\n",
            response_description="Response from the groundstation",
            dependencies=[Depends(api.authorization.require_login)],
        )
        async def control_groundstation_framed(
            gs_uuid: UUID, header_data: dict, request: Request
        ):
            frames = header_data.pop("frames")
            await self.send_control(
                request, gs_uuid, FramedContent(header_data=header_data, frames=frames)
            )

        @router.get(
            "/stations/{gs_uuid}/methods",
            summary="Get available methods on groundstation",
            response_description="Response from the groundstation",
            dependencies=[Depends(api.authorization.require_login)],
        )
        async def get_groundstation_methods(gs_uuid: UUID, request: Request):
            data = {"type": "/methods"}
            return await self.send_control(request, gs_uuid, data)

        @router.get(
            "/terminals", dependencies=[Depends(api.authorization.require_login)]
        )
        async def get_all_terminals(request: Request):

            terms = []
            for (gs, tid), item in self.registered_terminals.items():
                terms.append(
                    {
                        "groundstation": gs,
                        "terminal_id": tid,
                        "read_only": item.read_only,
                        "write_locked": item.rw_client is not None,
                        "ws_url": self.app.api.api_app.url_path_for(
                            "ws_connect_gs_term", gs_id=gs, term_id=tid
                        ),
                    }
                )

            return terms

        api.include_router(router)

    async def gs_busy(self, gs_uuid: UUID, timeout=None):
        gs = self.registered_groundstations.get(gs_uuid)
        if not gs:
            raise HTTPException(status.HTTP_404_NOT_FOUND)

        # TODO: Maybe add a delay to see if resource is freed after a bit before raising the error
        if gs.busy:
            return False

        gs.busy = True

        # TODO: Notify connected clients that GS is busy
        return True

    async def gs_free(self, gs_uuid: UUID):
        gs = self.registered_groundstations.get(gs_uuid)
        if not gs:
            raise HTTPException(status.HTTP_404_NOT_FOUND)

        # TODO: Maybe add a delay to see if resource is freed after a bit before raising the error
        if not gs.busy:
            return False

        gs.busy = False

        # TODO: Notify connected clients that GS is free
        return True

    async def send_control(
        self, request: Request, gs_uuid: UUID, data: dict | FramedContent
    ):
        # TODO: Create proxy header from request
        proxy_header = ProxyHeader(
            "control_frame", str(request.state.token_payload.sub)
        )
        return await self.send_to_gs(gs_uuid, data, proxy_header)

    async def send_to_gs(
        self, gs_uuid: UUID, data: dict | FramedContent, proxy_header: ProxyHeader
    ):
        available = await self.gs_busy(gs_uuid)
        if not available:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Groundstation is busy. Try again later",
            )

        error = None
        try:
            logger.debug(f"Received control data: {data}")

            req_id = await self.__websocket_send(gs_uuid, data, proxy_header)
            logger.debug(f"Created request with ID: {req_id}")
            response, error = await self.__websocket_receive_response(gs_uuid, req_id)
            if error:
                logger.warning(f"Received error from ground station: {error}")
            else:
                logger.debug(f"Received response: {response}")
        except Exception as e:
            logger.error(e)
            response = e
        finally:
            await self.gs_free(gs_uuid)

        if error:
            raise HTTPException(502, detail=error)
        return response

    async def handle_read_message_from_gs(self, gs_id: UUID, message):
        msg_type = message.get("type")
        error = message.get("error")

        if error:
            logger.error(f"Received error from groundstation ({gs_id}): {error}")
            return

        if msg_type is None:
            logger.warning("Message from groundstation missing type")
            # TODO respond with error
            return

        assert isinstance(msg_type, str)

        if msg_type.startswith("terminal/"):
            tt = msg_type.removeprefix("terminal/")
            await self.handle_terminal_messages(gs_id, message, tt)
            return

        logger.warning("Unsupported message type received from groundstation")

    async def handle_terminal_messages(self, gs_id: UUID, message: dict, command: str):
        term_id = message.get("terminal_id")

        if term_id is None:
            logger.warning("Received terminal command without an id")
            # TODO respond with error
            return

        reg_key = (gs_id, term_id)

        match command:
            case "open":
                if reg_key in self.registered_terminals:
                    logger.warning(f"Terminal {reg_key} already registered")
                    return
                term_name = message.get("terminal_name", "Terminal")
                ro = message.get("terminal_read_only", False)

                self.registered_terminals[reg_key] = TerminalRegistrationItem(
                    term_name, read_only=ro
                )
                logger.info(f"Registered terminal {reg_key}")
            case "close":
                await self.close_terminal(*reg_key)

                return

            case "stdout":
                term = self.registered_terminals.get(reg_key)

                if not term:
                    logger.warning(
                        f"Terminal {reg_key} does not exist. Cannot send response to clients"
                    )
                    return

                response = message.get("response")

                assert response is not None

                if "direction" not in response:
                    response["direction"] = "output"

                tasks = []
                for c in term.get_all_clients():
                    tasks.append(asyncio.Task(c.send_json(response)))

                if tasks:
                    await asyncio.wait(tasks)

    async def close_terminal(self, gs_id: UUID, term_id: str):
        reg_key = (gs_id, term_id)

        term = self.registered_terminals.get(reg_key)

        if not term:
            logger.warning(f"Terminal {reg_key} does not exist and cannot be closed")
            return

        tasks = []
        for c in term.get_all_clients():
            tasks.append(asyncio.Task(c.close()))

        if tasks:
            await asyncio.wait(tasks)

        del self.registered_terminals[reg_key]

        return


"""

groundstation -> platform : connect through websocket

webbrowser -> platform : send control to groundstation {id}
platform -> groundstation : forward control message to gs over ws

"""
