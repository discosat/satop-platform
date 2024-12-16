import asyncio
import uuid
import websockets
import json

import csh_wrapper as csh
 
async def main():
    async with websockets.connect('ws://localhost:7890/api/gs/ws') as ws:

        await ws.send(json.dumps({
            'type': 'hello',
            'name': 'CSH Client'
        }))
        print('Connected')

        csh.run('csp init -m "CSH Client"')
        csh.run('ident')
        csh.run('ping 0')

        while True:
            msg = json.loads(await ws.recv())
            print('>' + str(msg))
            req_id = msg.get('request_id')
            data = msg.get('data')
            dtype = data.get('type')

            if dtype == "echo":
                out = json.dumps({
                    'message_id': str(uuid.uuid4()),
                    'in_response_to': req_id,
                    'data': data
                })
                print('<' + out)
                await ws.send(out)

            elif dtype == "csh":
                script = data.get('script', [])
                out, ret = csh.execute_script(script)
                response = json.dumps({
                    'message_id': str(uuid.uuid4()),
                    'in_response_to': req_id,
                    'data': {
                        'return_code': {
                            'name': ret.name,
                            'value': ret.value
                        },
                        'command_output': out.decode()
                    }
                })

                print(response)
                await ws.send(response)

asyncio.run(main())