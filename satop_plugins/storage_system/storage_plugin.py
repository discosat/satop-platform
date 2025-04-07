import os
import logging
import requests
from fastapi import APIRouter, Request, HTTPException
from satop_platform.plugin_engine.plugin import Plugin

logger = logging.getLogger("plugin.storage")

class StoragePlugin(Plugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        if not self.check_required_capabilities(["http.add_routes"]):
            raise RuntimeError

        self.api_router = APIRouter()

        @self.api_router.get(
            "/storage/images",
            summary="Fetch image metadata from storage system",
            description="Calls the external DAM system to fetch image metadata.",
            response_description="List of images"
        )
        async def get_images(request: Request):
            headers = {}
            if "authorization" in request.headers:
                headers["Authorization"] = request.headers["authorization"]

            try:
                #Change the URL to your storage system's endpoint
                #This is just a placeholder
                response = requests.get("http://localhost:8080/api/images", headers=headers)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.error(f"Error contacting storage system: {e}")
                raise HTTPException(status_code=500, detail="Storage system unavailable")

    def startup(self):
        super().startup()
        logger.info("Storage plugin started")

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")
