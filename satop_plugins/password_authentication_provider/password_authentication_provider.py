import logging
import os
from hashlib import scrypt
from typing import Annotated

import sqlalchemy.exc
import sqlmodel
import typer
from fastapi import APIRouter, Depends, HTTPException, status

# from .password_authentication_provider import models
from pydantic import BaseModel
from satop_platform.components.authorization.models import (
    EntityBase,
    EntityType,
    ProviderIdentityBase,
    TokenPair,
)
from satop_platform.components.restapi import exceptions
from satop_platform.plugin_engine.plugin import AuthenticationProviderPlugin


class HashedCredentials(sqlmodel.SQLModel, table=True):
    email: str = sqlmodel.Field(unique=True, primary_key=True)
    password_hash: bytes
    salt: bytes

class TokenResponse(TokenPair):
    scopes: list[str]


class PasswordCredentials(BaseModel):
    email: str
    password: str


class PasswordUser(BaseModel):
    email: str

    model_config = {"json_schema_extra": {"examples": [{"email": "hello@example.com"}]}}


logger = logging.getLogger("plugin.password_authentication_provider")


class PasswordAuthenticationProvider(AuthenticationProviderPlugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        engine_path = self.data_dir / "users.db"
        engine_path.parent.mkdir(exist_ok=True, parents=True)
        self.sql_engine = sqlmodel.create_engine("sqlite:///" + str(engine_path))

        # sqlmodel.SQLModel.metadata.create_all(self.sql_engine)
        # if not inspect(self.sql_engine).has_table(HashedCredentials.__tablename__):
        HashedCredentials.__table__.create(self.sql_engine, checkfirst=True)

        self.init_cli()

        self.api_router = APIRouter(prefix="/login", tags=["Authentication"])

        @self.api_router.post(
            "/token",
            response_model=TokenResponse,
            summary="Request an access and refresh token with scopes.",
            description="Obtain new tokens and a list of effective user permissions by providing valid credentials.",
            response_description="An access token, refresh token, and a list of permission scopes.",
            responses={**exceptions.InvalidCredentials().response},
        )
        async def __create_token(credentials: PasswordCredentials):
            if not self.validate(credentials.email, credentials.password):
                raise exceptions.InvalidCredentials

            user_id_for_auth_system = self.app.auth.get_uuid(
                provider="email_password", entity_identifier=credentials.email
            )
            if not user_id_for_auth_system:
                raise exceptions.InvalidCredentials(detail="User is valid but not linked to a platform entity.")

            user_scopes = self.app.auth.get_entity_scopes(user_id_for_auth_system)

            token_pair = self.create_token_pair(user_id=credentials.email)

            response_data = TokenResponse(
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                scopes=sorted(list(user_scopes)),
            )

            print(f"--- SENDING TOKEN RESPONSE TO FRONTEND: {response_data.model_dump_json()} ---")
            return response_data



        @self.api_router.post(
            "/user",
            status_code=status.HTTP_201_CREATED,
            summary="Create a new user.",
            description="Create a new user with the provided credentials, provided that the email is not already registered.",
            response_model=PasswordUser,
            responses={
                status.HTTP_409_CONFLICT: {
                    "description": "User already exists",
                },
            },
            dependencies=[
                Depends(self.app.auth.require_scope(["satop.auth.entities.create"]))
            ],
        )
        async def __create_user(credentials: PasswordCredentials):
            return self.create_user(credentials)

        @self.api_router.get(
            "/users",
            response_model=list[PasswordUser],
            summary="List all users",
            description="List all registered user emails.",
            response_description="List of all users that have been registered with the email-password authentication provider.",
            dependencies=[
                Depends(self.app.auth.require_scope(["satop.auth.entities.list"]))
            ],
        )
        async def __get_all_users():
            return self.get_users()

    def create_user(self, credentials: PasswordCredentials):
        with sqlmodel.Session(self.sql_engine) as session:
            salt = os.urandom(16)
            hashed_pass = self.hash_function(credentials.password, salt)
            entry = HashedCredentials(
                email=credentials.email, password_hash=hashed_pass, salt=salt
            )
            try:
                session.add(entry)

                session.commit()
                return PasswordUser(email=credentials.email)
            except sqlalchemy.exc.IntegrityError:
                raise HTTPException(status.HTTP_409_CONFLICT, "User already exists")

    def get_user(self, email: str):
        with sqlmodel.Session(self.sql_engine) as session:
            statement = sqlmodel.select(HashedCredentials).where(
                HashedCredentials.email == email
            )
            user = session.exec(statement).first()
            return user

    def get_users(self):
        with sqlmodel.Session(self.sql_engine) as session:
            statement = sqlmodel.select(HashedCredentials)
            users = session.exec(statement).all()
            return list(map(lambda u: PasswordUser(email=u.email), users))

    def remove_user(self, email: str):
        with sqlmodel.Session(self.sql_engine) as session:
            statement = sqlmodel.select(HashedCredentials).where(
                HashedCredentials.email == email
            )
            user = session.exec(statement).first()
            if user:
                logger.info(f"Deleting user ({email})")
                session.delete(user)
            else:
                logger.warning(f"Could not delete user ({email}). Not found!")
                raise exceptions.NotFound()
            session.commit()

    def validate(self, email: str, password: str) -> bool:
        user = self.get_user(email)
        if not user:
            return False

        calculated_hash = self.hash_function(password, user.salt)

        if calculated_hash == user.password_hash:
            return True

        return False

    def hash_function(self, password: bytes | str, salt: bytes | str):
        # OWASP recommendation: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
        #   scrypt is selected, as it is in the standard library.
        if isinstance(password, str):
            password = password.encode()
        if isinstance(salt, str):
            salt = salt.encode()

        n = 2**17
        r = 8
        p = 1
        maxmem = n * 2 * r * 65
        dklen = 64

        return scrypt(password, salt=salt, n=n, r=r, p=p, maxmem=maxmem, dklen=dklen)

    def init_cli(self):
        from rich import print

        self.cli = typer.Typer(name="password-auth")

        provider_key = self.config.get("authentication_provider", dict()).get(
            "provider_key", self.name
        )

        @self.cli.command("new-user")
        def create_email_password_user(
            name: str,
            email: str,
            password: Annotated[
                str,
                typer.Option(prompt=True, confirmation_prompt=True, hide_input=True),
            ],
            roles: list[str],
        ):
            credentials = PasswordCredentials(email=email, password=password)

            entity = self.app.auth.add_entity(
                EntityBase(name=name, roles=",".join(roles), type=EntityType.person)
            )
            pwuser = self.create_user(credentials)
            self.app.auth.connect_entity_idp(
                str(entity.id),
                ProviderIdentityBase(provider=provider_key, identity=email),
            )

            print("Created new user:")
            print(entity)
            print(pwuser)

        @self.cli.command("rm-user")
        def remove_user(
            email: str,
            remove_entity: Annotated[bool, typer.Option("--remove-entity")] = False,
        ):
            print("Deleting following user: ", email)
            self.remove_user(email)

            if remove_entity:
                raise NotImplementedError

        @self.cli.command("users")
        def list_users():
            registered = self.app.auth.get_idp_details(provider_key).registered_users
            internal = self.get_users()

            unregistered = list(
                filter(
                    lambda x: all(x.email != y.identity for y in registered), internal
                )
            )

            if registered:
                print("Email users registered on the platform:")
                for e in registered:
                    print("-", end=" ")
                    print(e)
            else:
                print(
                    "There is currently no email users connected to the main platform authorization."
                )

            if unregistered:
                print("\nRegisterd users not connected to the platform:")
                for e in unregistered:
                    print("-", end=" ")
                    print(e)
