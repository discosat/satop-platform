from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy.exc
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from satop_platform.components.authorization import models
from satop_platform.components.authorization.auth import ProviderDictItem
from satop_platform.components.authorization.models import Token
from satop_platform.components.restapi import exceptions

if TYPE_CHECKING:
    from satop_platform.core.satop_application import SatOPApplication


def load_routes(components: SatOPApplication):
    api_app = components.api
    auth = components.auth

    root_router = APIRouter(include_in_schema=False)

    @root_router.get("/")
    async def docs_redirect():
        """Redirect to the API documentation"""
        return RedirectResponse("/docs")

    api_app.api_app.include_router(root_router)

    router = APIRouter(prefix=api_app._root_path, tags=["Platform Core"])

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
    auth_router = APIRouter(prefix="/auth", tags=["Authorization"])

    @auth_router.get(
        "/entities",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.list"))],
        summary="List all registered entities",
        description="Get a list of all entities in the authorization system.",
        response_description="A list of entities.",
    )
    async def get_entities() -> list[models.Entity]:
        return api_app.authorization.get_all_entities()

    @auth_router.post(
        "/entities",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.create"))],
        response_model=models.Entity,
        summary="Add a new entity",
        description="Register a new entity in the authorization system, including the scopes the new entity should have access to.",
        response_description="The details of the added entity, including the assigned UUID.",
    )
    async def add_entity(entity: models.EntityBase) -> models.Entity:
        return api_app.authorization.add_entity(entity)

    @auth_router.get(
        "/entities/{uuid}",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.read"))],
        summary="Get entity details",
        description="Get details for a specific entity.",
        response_description="The details of the specified entity.",
        responses={**exceptions.NotFound("Entity not found").response},
    )
    async def get_entity_details(uuid: str) -> models.Entity:
        return api_app.authorization.get_entity_details(uuid)

    @auth_router.delete(
        "/entities/{uuid}",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.delete"))],
        summary="Delete an entity",
        responses={**exceptions.NotFound("Entity not found").response},
    )
    async def delete_entity(uuid: UUID) -> None:
        try:
            return api_app.authorization.delete_entity(uuid)
        except sqlalchemy.exc.NoResultFound:
            raise exceptions.NotFound("Entity not found")

    @auth_router.patch(
        "/entities/{uuid}",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.update"))],
        summary="Update an entity",
        responses={**exceptions.NotFound("Entity not found").response},
    )
    async def update_entity(uuid: UUID, entity: models.EntityUpdate) -> models.Entity:
        try:
            return api_app.authorization.update_entity(uuid, entity)
        except sqlalchemy.exc.NoResultFound:
            raise exceptions.NotFound("Entity not found")

    @auth_router.post(
        "/entities/{uuid}/providers",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.connect-idp"))],
        summary="Connect an entity to an identity provider",
        description="\n".join(
            [
                "Connect an entity to an identity provider given a identifier that is authenticated by the provider.",
                "",
                "Two entities must not have the same identity with the same provider. ",
                "",
                "E.g. a user identified by their email address can afterwards be authenticated by proving they have the corresponding password in the 'email_password' provider.",
            ]
        ),
        response_description="The authentication identifiers for the entity.",
    )
    async def connect_entity_idp(
        uuid: str, provider: models.ProviderIdentityBase
    ) -> models.AuthenticationIdentifiers:
        return api_app.authorization.connect_entity_idp(uuid, provider)

    @auth_router.get(
        "/entities/{uuid}/providers",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.list-idp"))],
        summary="List identity providers connected to an entity",
    )
    async def list_entitys_idps(uuid: UUID) -> dict[str, list[str]]:
        return api_app.authorization.get_entity_idps(uuid)

    @auth_router.delete(
        "/entities/{uuid}/providers/{provider}/{ident}",
        dependencies=[
            Depends(auth.require_scope("satop.auth.entities.disconnect-idp"))
        ],
        summary="Unlink an entity from an identity provider",
    )
    async def unlink_entity_idp(uuid: UUID, provider: str, ident: str):
        return api_app.authorization.unlink_identity(
            models.AuthenticationIdentifiers(
                provider=provider, identity=ident, entity_id=uuid
            )
        )

    @auth_router.get(
        "/providers",
        summary="Get identity providers",
        description="Get a list of all identity providers and hints for the identity field associated with the IdP.",
        responses={
            200: {
                "description": "A dictionary of identity providers. Depends on which authentication provider plugins have been added to the platform.",
                "content": {
                    "application/json": {
                        "example": {
                            "email_password": {
                                "identity_hint": "Email address of the user"
                            },
                            "api_key": {"identity_hint": "API key of the system"},
                            "AUID": {
                                "identity_hint": "AUID for AU SSO (auXXXXXX@uni.au.dk)"
                            },
                        }
                    }
                },
            }
        },
    )
    async def get_identity_providers() -> dict[str, ProviderDictItem]:
        return api_app.authorization.get_identity_providers()

    @auth_router.get(
        "/providers/{name}",
        dependencies=[Depends(auth.require_scope("satop.auth.entities.read"))],
        summary="Get identity provider details",
        description="Get details for a specific identity provider.",
        response_description="The authentication identifiers for the identity provider.",
        responses={**exceptions.NotFound("Provider not found").response},
    )
    async def get_idp_details(name: str) -> models.IdentityProviderDetails:
        return api_app.authorization.get_idp_details(name)

    @auth_router.get(
        "/test",
        summary="Test the authentication system",
        description="Test the authentication system by returning the state of the request for which an Entity is required to have been assigned the 'test' scope.",
        response_description="The state of the request.",
        responses={
            **exceptions.MissingCredentials().response,
            **exceptions.InsufficientPermissions().response,
        },
        dependencies=[
            Depends(auth.require_scope(["test"]))
        ],  # use auth.require_login instead to allow any logged in entity
    )
    async def test_auth(request: Request) -> dict:

        return {"request.state": request.state._state}

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

    @auth_router.get("/refresh_token")
    async def refresh_access_token(tok: Token = Depends(auth.require_refresh)):
        return auth.refresh_tokens(tok)

    @auth_router.get("/all_scopes", response_model=list[str])
    async def list_all_scopes():
        return sorted(auth.used_scopes)

    @auth_router.get("/roles", response_model=dict[str, list[str]])
    async def list_all_roles():
        return auth.get_roles()

    @auth_router.post(
        "/roles",
        status_code=201,
        dependencies=[Depends(auth.require_scope("satop.auth.roles.edit"))],
    )
    async def create_new_role(role: models.NewRole):
        return auth.create_new_role(role.name, role.scopes)

    @auth_router.put(
        "/roles/{role_name}",
        dependencies=[Depends(auth.require_scope("satop.auth.roles.edit"))],
    )
    async def update_role(role_name: str, role: models.NewRole):
        return auth.update_role(role_name, role.scopes)

    @auth_router.delete(
        "/roles/{role_name}",
        dependencies=[Depends(auth.require_scope("satop.auth.roles.edit"))],
    )
    async def delete_role(role_name: str, role: models.NewRole):
        return auth.remove_role(role_name)

    @auth_router.get("/check_my_roles")
    async def check_roles(token: dict = Depends(auth.require_login)):
        return auth.get_entity_scopes(UUID(token.get("sub")))

    api_app.include_router(auth_router)
