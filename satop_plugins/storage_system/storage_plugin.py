import os
import logging
import requests
from fastapi import APIRouter, Request, HTTPException, File, UploadFile
from satop_platform.plugin_engine.plugin import Plugin
import httpx

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
                response = requests.get("http://localhost:8080/search-images", headers=headers)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.error(f"Error contacting storage system: {e}")
                raise HTTPException(status_code=500, detail="Storage system unavailable")


        @self.api_router.post(
            "/measurement",
            summary="Uploads a measurement file related to specified observation request",
            description="Calls DIM to upload file to be persisted and related to a certain request",
            response_description="Id of uploaded measurement"

        )
        async def post_measurement(requestid: int ,file: UploadFile):
            headers = {}
            # if "authorization" in request.headers:
            #     headers["Authorization"] = request.headers["authorization"]
            try:

                async with httpx.AsyncClient() as client:
                    # Stream the file content directly
                    response = await client.post(
                        "http://localhost:8080/file",
                        files={"file": (file.filename, file.file, file.content_type)}, data={"requestId": requestid}
                    )
                    return response.json()
                # response = requests.post("http://localhost:8080/file", files={"file": file}, headers={"Content-Type": "multipart/form-data"})
            except requests.RequestException as e:
                logger.error(f"Error contacting storage system: {e}")
                raise HTTPException(status_code=500, detail="Storage system unavailable")


    def startup(self):
        super().startup()
        logger.info("Storage plugin started")

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")
