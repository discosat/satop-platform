import datetime as dt
from typing import Annotated
from uuid import UUID

import typer
from rich import print

from satop_platform.components.authorization import auth
from satop_platform.components.authorization.models import EntityBase, EntityType


def auth_cli(auth: auth.PlatformAuthorization):
    app = typer.Typer(name="auth")

    @app.command("create-admin")
    def create_admin(name: str = "SatOP Admin"):
        roles = auth.get_roles()
        if "admin" not in roles:
            auth.create_new_role("admin", ["*"])

        new_user = auth.add_entity(
            EntityBase(name=name, type=EntityType.person, roles="admin")
        )

        print(new_user)

    @app.command("users")
    def print_users():
        for e in auth.get_all_entities():
            print(e)

    @app.command("roles")
    def print_roles():
        print(auth.get_roles())

    @app.command("get-token")
    def create_token(
        uid: UUID, exp_minutes: Annotated[int, typer.Option("--exp", "-e")] = 30
    ):
        exp = None
        if exp_minutes:
            exp = dt.timedelta(minutes=exp_minutes)
        tok = auth.create_token(uid, expires_delta=exp)

        print(tok)

    return app
