import os
from plugin_engine.plugin import Plugin
from fastapi import APIRouter
from components.restapi.restapi import app

class Dummy(Plugin):
    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)
    

    def pre_init(self):
        # Doesn't work
        self.register_my_test_router()

        # ---
        # Works
        # router = APIRouter()

        # @router.get('/test')
        # async def route_test():
        #     return {"message": "Hello from Dummy - test"}


        # app.include_router(router)
        # ---

    def init(self):
        super().register_function('run', self.run)
        super().register_function('return_hello', self.return_hello)
        super().register_router(self.my_router())
        router = APIRouter()
        @router.get("/dummy")
        async def dummy():
            return {"message": "Hello from Dummy plugin"}
        super().register_router(router)


        # ---
        # Works but I don't need it right now as I have now tested that it works but kept it for reference
        
        # router2 = APIRouter()

        # @router2.get('/test2')
        # async def route_test2():
        #     return {"message": "Hello from Dummy - test2"}


        # app.include_router(router2)
        # ---
        pass

    def post_init(self):
        super().call_function('Dummy', 'run')

    def run(self):
        print("Dummy plugin running")
    
    def return_hello(self):
        return "Hello from Dummy plugin"
    
    def my_router(self):
        router = APIRouter()
        @router.get("/dummy")
        async def dummy():
            return {"message": "Hello from Dummy plugin"}
        return router
    
    def register_my_test_router():
        router = APIRouter()

        @router.get('/test')
        async def route_test():
            return {"message": "Hello from Dummy - test"}


        app.include_router(router)