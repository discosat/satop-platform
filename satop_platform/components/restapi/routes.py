from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from .restapi import APIApplication
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

        Returns:
            RedirectResponse: Redirect to the API documentation
        """
        return RedirectResponse('/docs')
    
    api_app.api_app.include_router(root_router)



    router = APIRouter(prefix=api_app._root_path, tags=['Platform Core'])

    @router.get('/hello', dependencies=[Depends(api_app.authorization.require_scope(['test']))])
    async def route_hello():
        """Test route for the API

        Returns:
            dict: A simple message
        """
        return {"message": "Hello from main"}
    
    api_app.include_router(router)

    # well_known_router = APIRouter(prefix='/.well-known', tags=['.well-known'])

    # @well_known_router.get('/ni/')
    # async def well_known_ni_base():
    #     return RedirectResponse(f'/api/log/artifacts/ni/')

    # @well_known_router.get('/ni/{ni}')
    # async def well_known_ni_redirect(ni):
    #     return RedirectResponse(f'/api/log/artifacts/ni/{ni}')
    
    # api_app.api_app.include_router(well_known_router)
    auth_router = APIRouter(prefix='/auth', tags=["Authorization"])

    @auth_router.get('/entities')
    async def get_entities():
        """Get a list of all entities (users) in the system

        Returns:
            (list(models.Entity)): List of entities
        """
        return api_app.authorization.get_all_entities()

    @auth_router.post('/entities')
    async def add_entity(entity: models.EntityBase):
        """Add a new entity (user) to the system

        Args:
            entity (models.EntityBase): The entity to add

        Returns:
            (models.Entity): The added entity
        """
        return api_app.authorization.add_entity(entity)
    
    @auth_router.get('/entities/{uuid}')
    async def get_entity_details(uuid: str):
        """Get details for a specific entity (user)

        Args:
            uuid (str): The UUID of the entity to get details for

        Returns:
            (models.Entity): The entity details
        """
        return api_app.authorization.get_entity_details(uuid)
    
    @auth_router.post('/entities/{uuid}/provider')
    async def connect_entity_idp(uuid: str, provider: models.ProviderIdentityBase):
        """Connect an entity (user) to an identity provider

        Args:
            uuid (str): The UUID of the entity to connect
            provider (models.ProviderIdentityBase): The identity provider to connect to (e.g. email-password, OAuth, etc.)

        Returns:
            (models.AuthenticationIdentifiers): The authentication identifiers for the entity
        """
        return api_app.authorization.connect_entity_idp(uuid, provider)
    
    @auth_router.get('/providers')
    async def get_identity_providers():
        """Get a list of all identity providers

        Returns:
            (dict(str, str)): A dictionary of identity providers
        """
        return api_app.authorization.get_identity_providers()
    
    @auth_router.get('/providers/{name}')
    async def get_idp_details(name: str):
        """Get details for a specific identity provider

        Args:
            name (str): The name of the identity provider

        Returns:
            (list(models.AuthenticationIdentifiers)): The authentication identifiers for the identity provider
        """
        return api_app.authorization.get_idp_details(name)

    @auth_router.get('/test', dependencies=[Depends(auth.require_scope(['test']))]) # use auth.require_login instead to allow any logged in entity
    async def test_auth(request: Request):
        """Test the authentication system

        Returns:
            (dict): The state of the request
        """
        return {
            'request.state': request.state,
        }

    api_app.include_router(auth_router)
