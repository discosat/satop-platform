from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import datetime

from satop_platform.components.authorization.auth import ProviderDictItem

from .restapi import APIApplication
from . import exceptions
from satop_platform.components.authorization import models

from typing import TYPE_CHECKING, Annotated
if TYPE_CHECKING:
    from satop_platform.core.component_initializer import SatOPComponents

def load_routes(components: SatOPComponents):
    api_app = components.api
    auth = components.auth


    root_router = APIRouter(include_in_schema=False)
    @root_router.get('/')
    async def docs_redirect():
        """Redirect to the API documentation
        """
        return RedirectResponse('/docs')
    
    api_app.api_app.include_router(root_router)



    router = APIRouter(prefix=api_app._root_path, tags=['Platform Core'])

    # @router.get('/hello', dependencies=[Depends(api_app.authorization.require_scope(['test']))])
    # async def route_hello():
    #     """Test route for the API

    #     Returns:
    #         dict: A simple message
    #     """
    #     return {"message": "Hello from main"}
    
    # api_app.include_router(router)

    # well_known_router = APIRouter(prefix='/.well-known', tags=['.well-known'])

    # @well_known_router.get('/ni/')
    # async def well_known_ni_base():
    #     return RedirectResponse(f'/api/log/artifacts/ni/')

    # @well_known_router.get('/ni/{ni}')
    # async def well_known_ni_redirect(ni):
    #     return RedirectResponse(f'/api/log/artifacts/ni/{ni}')
    
    # api_app.api_app.include_router(well_known_router)
    auth_router = APIRouter(prefix='/auth', tags=["Authorization"])

    @auth_router.get(
        '/entities',
        summary="List all registered entities",
        description="Get a list of all entities in the authorization system.",
        response_description="A list of entities.")
    async def get_entities() -> list[models.Entity]:
        return api_app.authorization.get_all_entities() 

    @auth_router.post(
        '/entities',
        response_model=models.Entity,  
        summary="Add a new entity",
        description="Register a new entity in the authorization system, including the scopes the new entity should have access to.",
        response_description="The details of the added entity, including the assigned UUID."
    )
    async def add_entity(entity: models.EntityBase) -> models.Entity:
        return api_app.authorization.add_entity(entity)
                
    @auth_router.get(
        '/entities/{uuid}',
        summary="Get entity details",
        description="Get details for a specific entity.",
        response_description="The details of the specified entity.",
        responses={**exceptions.NotFound("Entity not found").response}
    )
    async def get_entity_details(uuid: str) -> models.Entity:
        return api_app.authorization.get_entity_details(uuid)
    
    @auth_router.post(
            '/entities/{uuid}/provider',
            summary="Connect an entity to an identity provider",
            description="""\
Connect an entity to an identity provider given a identifier that is authenticated by the provider.

Two entities must not have the same identity with the same provider. 

E.g. a user identified by their email address can afterwards be authenticated by proving they have the corresponding password in the 'email_password' provider.\
""",
            response_description="The authentication identifiers for the entity."
            )
    async def connect_entity_idp(uuid: str, provider: models.ProviderIdentityBase) -> models.AuthenticationIdentifiers:
        return api_app.authorization.connect_entity_idp(uuid, provider)
    
    @auth_router.get(
            '/providers',
            summary="Get identity providers",
            description="Get a list of all identity providers and hints for the identity field associated with the IdP.",
            responses={
                200: {
                    "description": "A dictionary of identity providers. Depends on which authentication provider plugins have been added to the platform.",
                    "content": {
                        "application/json": {
                            "example": {
                                "email_password": { "identity_hint": "Email address of the user" },
                                "api_key": { "identity_hint": "API key of the system" },
                                "AUID": { "identity_hint": "AUID for AU SSO (auXXXXXX@uni.au.dk)" },
                            }
                        }
                    }
                }
            }
        )
    async def get_identity_providers() -> dict[str, ProviderDictItem]:
        return api_app.authorization.get_identity_providers()
    
    @auth_router.get(
            '/providers/{name}',
            summary="Get identity provider details",
            description="Get details for a specific identity provider.",
            response_description="The authentication identifiers for the identity provider.",
            responses={**exceptions.NotFound("Provider not found").response}
        )
    async def get_idp_details(name: str) -> models.IdentityProviderDetails:
        return api_app.authorization.get_idp_details(name)

    @auth_router.get(
            '/test', 
            summary="Test the authentication system",
            description="Test the authentication system by returning the state of the request for which an Entity is required to have been assigned the 'test' scope.",
            response_description="The state of the request.",
            responses={
                **exceptions.MissingCredentials().response, 
                **exceptions.InsufficientPermissions().response
            },
            dependencies=[Depends(auth.require_scope(['test']))]    # use auth.require_login instead to allow any logged in entity
        ) 
    async def test_auth(request: Request) -> dict:

        return {
            "request.state": request.state._state
        }

    # TODO: Add Refresh Token to scope or somewhere else we can store it
    # TODO: Update access token refresher \/
    """
    @auth_router.get('/refresh_token')
    async def get_new_access_token(token_details:dict = Depends(...))
        expiry_timestamp = token_details['exp']

        if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
            new_access_token = create_access_token(
                user_data=token_details['user']
            )

            return JSONResponse(content={
                "access_token": new_access_token
            })
        
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, details="Invalid Or Expired Token")
    """

    @auth_router.get('/refresh_token')
    async def refresh_access_token(request: Request):
        """Refresh access token using a valid refresh token"""
        """
        try:
            token = request
        
        if not user_data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
            
        new_access_token = create_access_token()

        new_refresh_token = create_refresh_token()

        return JSONResponse(content={
        "access_token": new_access_token, 
        "refresh_token": new_refresh_token
        }) 
        """
    
    @auth_router.get('/all_scopes', response_model=list[str])
    async def list_all_scopes():
        return auth.used_scopes

    api_app.include_router(auth_router)
