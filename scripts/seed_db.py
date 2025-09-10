import os
import uuid
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from satop_platform.components.authorization.models import (
    AuthenticationIdentifiers,
    Entity,
    EntityType,
    RoleScopes,
)

print("--- SatOP Database Seeding Script ---")


SATOP_DATA_ROOT = os.getenv("SATOP_DATA_ROOT", "./docker/data")
AUTH_DB_FILE = Path(SATOP_DATA_ROOT) / "database/authorization.db"
PASSWORD_DB_FILE = Path(SATOP_DATA_ROOT) / "plugins/password_authentication_provider/users.db"


# --- Define our seed data ---
ADMIN_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "admin.satop.dev")
OPERATOR_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "operator.satop.dev")

ADMIN_EMAIL = "admin@example.com"
OPERATOR_EMAIL = "operator@example.com"

def tear_down_databases():
    """Removes the database files to ensure a clean slate."""
    print("\n[Phase 1: Tearing Down Databases]")
    
    try:
        if AUTH_DB_FILE.exists():
            AUTH_DB_FILE.unlink()
            print(f"  - Successfully removed main authorization database: {AUTH_DB_FILE}")
        else:
            print(f"  - Main authorization database not found, skipping removal.")
            
        if PASSWORD_DB_FILE.exists():
            PASSWORD_DB_FILE.unlink()
            print(f"  - Successfully removed password plugin database: {PASSWORD_DB_FILE}")
        else:
            print(f"  - Password plugin database not found, skipping removal.")

    except OSError as e:
        print(f"  - Error removing database file: {e}")
        raise

def seed_main_authorization_db():
    """Creates and seeds the main authorization.db with Roles, Entities, and Provider links."""
    print("\n[Phase 2: Seeding Main Authorization Database]")

    AUTH_DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{AUTH_DB_FILE}")
    SQLModel.metadata.create_all(engine)
    print("  - Database and tables created successfully.")

    with Session(engine) as session:
        # Seed Roles and Scopes
        print("  - Seeding Roles and Scopes...")
        admin_scopes = [
            RoleScopes(role="admin", scope="*"),  # Wildcard for full admin access
            RoleScopes(role="admin", scope="satop.auth.entities.create"),
            RoleScopes(role="admin", scope="satop.auth.entities.list"),
        ]

        operator_scopes = [
            RoleScopes(role="operator", scope="scheduling.flightplan.create"),
            RoleScopes(role="operator", scope="scheduling.flightplan.read"),
        ]
        
        session.add_all(admin_scopes)
        session.add_all(operator_scopes)

        # Seed Entities (the users)
        print("  - Seeding Entities...")
        admin_entity = Entity(
            id=ADMIN_ID,
            name="Admin User",
            type=EntityType.person,
            roles="admin",
        )
        operator_entity = Entity(
            id=OPERATOR_ID,
            name="Operator User",
            type=EntityType.person,
            roles="operator",
        )
        session.add_all([admin_entity, operator_entity])
        print(f"    - Created Admin User with ID: {ADMIN_ID}")
        print(f"    - Created Operator User with ID: {OPERATOR_ID}")

        # Link Entities to the Authentication Provider Identity
        print("  - Linking Entities to 'email_password' provider...")
        admin_auth_link = AuthenticationIdentifiers(
            provider="email_password",
            identity=ADMIN_EMAIL,
            entity_id=ADMIN_ID,
        )
        operator_auth_link = AuthenticationIdentifiers(
            provider="email_password",
            identity=OPERATOR_EMAIL,
            entity_id=OPERATOR_ID,
        )
        session.add_all([admin_auth_link, operator_auth_link])
        print(f"    - Linked {ADMIN_EMAIL} to Admin User.")
        print(f"    - Linked {OPERATOR_EMAIL} to Operator User.")

        session.commit()
    print("  - Main authorization database seeding complete.")


if __name__ == "__main__":
    tear_down_databases()
    seed_main_authorization_db()
    print("\n--- Database seeding finished successfully. ---")
    print("NOTE: Passwords are not set by this script. You must use the API after the server starts.")