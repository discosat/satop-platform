import asyncio
import json
import uuid

import websockets


async def main():
    async with websockets.connect("ws://localhost:7890/api/gs/ws") as ws:

        await ws.send(json.dumps({"type": "hello", "name": "Echo TEST"}))
        print("Connected")

        while True:
            msg = json.loads(await ws.recv())
            print(">" + str(msg))
            req_id = msg.get("request_id")
            data = msg.get("data")

            out = json.dumps(
                {
                    "message_id": str(uuid.uuid4()),
                    "in_response_to": req_id,
                    "data": data,
                }
            )

            print("<" + str(out))

            await ws.send(out)


asyncio.run(main())
