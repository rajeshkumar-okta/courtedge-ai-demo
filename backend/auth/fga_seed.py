"""
Seed FGA store with initial relationship tuples for the ProGear demo.

Run once: python -m auth.fga_seed

Assigns users as managers of the inventory_system.
The check_vacation condition is evaluated at check time (not seed time).

NOTE: This script is for documentation and re-seeding purposes.
The tuples may already exist in the FGA store (01KNSR7472HW2PAYFR224NAPCY).
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def seed():
    """Seed FGA store with relationship tuples."""
    try:
        from openfga_sdk import ClientConfiguration, OpenFgaClient, RelationshipCondition
        from openfga_sdk.credentials import Credentials, CredentialConfiguration
        from openfga_sdk.client.models import ClientTuple, ClientWriteRequest
    except ImportError:
        print("ERROR: openfga_sdk not installed. Run: pip install openfga-sdk")
        return

    api_url = os.getenv("FGA_API_URL")
    store_id = os.getenv("FGA_STORE_ID")
    client_id = os.getenv("FGA_CLIENT_ID")
    client_secret = os.getenv("FGA_CLIENT_SECRET")

    if not all([api_url, store_id, client_id, client_secret]):
        print("ERROR: Missing FGA environment variables. Check .env file.")
        print("Required: FGA_API_URL, FGA_STORE_ID, FGA_CLIENT_ID, FGA_CLIENT_SECRET")
        return

    configuration = ClientConfiguration(
        api_url=api_url,
        store_id=store_id,
        authorization_model_id=os.getenv("FGA_MODEL_ID", ""),
        credentials=Credentials(
            method='client_credentials',
            configuration=CredentialConfiguration(
                api_issuer=os.getenv("FGA_API_TOKEN_ISSUER", "fga.us.auth0.com"),
                api_audience=os.getenv("FGA_API_AUDIENCE", "https://api.us1.fga.dev/"),
                client_id=client_id,
                client_secret=client_secret,
            )
        )
    )

    async with OpenFgaClient(configuration) as fga:
        # Define relationship tuples
        # User IDs use email format (matching FGA store convention)
        # The check_vacation condition context is stored ON the tuple
        tuples = [
            # Warehouse manager - on vacation (will be DENIED inventory:write)
            ClientTuple(
                user="user:mike.manager@atko.email",
                relation="manager",
                object="inventory_system:main_db",
                condition=RelationshipCondition(
                    name="check_vacation",
                    context=dict(is_on_vacation=True),  # Mike is on vacation
                ),
            ),

            # Example: Another warehouse user NOT on vacation (would be ALLOWED)
            # Uncomment to add:
            # ClientTuple(
            #     user="user:jane.warehouse@atko.email",
            #     relation="manager",
            #     object="inventory_system:main_db",
            #     condition=RelationshipCondition(
            #         name="check_vacation",
            #         context=dict(is_on_vacation=False),
            #     ),
            # ),
        ]

        try:
            body = ClientWriteRequest(writes=tuples)
            await fga.write(body)
            print(f"SUCCESS: Seeded {len(tuples)} FGA tuples")
            for t in tuples:
                ctx = t.condition.context if t.condition else {}
                print(f"  - {t.user} -> {t.relation} -> {t.object} (context: {ctx})")
        except Exception as e:
            if "cannot write a tuple which already exists" in str(e).lower():
                print("INFO: Tuples already exist in FGA store (this is fine)")
            else:
                print(f"ERROR: Failed to write tuples: {e}")


async def verify():
    """Verify FGA checks work as expected."""
    from auth.fga_client import check_inventory_access

    print("\n--- Verification Checks ---")

    # Test 1: Manager not on vacation -> should be ALLOWED
    result = await check_inventory_access(
        user_email="mike.manager@atko.email",
        relation="manager",
        is_on_vacation=False
    )
    print(f"Manager (not on vacation): allowed={result.allowed}")
    print(f"  Reason: {result.reason}")

    # Test 2: Manager on vacation -> should be DENIED
    result = await check_inventory_access(
        user_email="mike.manager@atko.email",
        relation="manager",
        is_on_vacation=True
    )
    print(f"Manager (on vacation): allowed={result.allowed}")
    print(f"  Reason: {result.reason}")

    # Test 3: can_increase_inventory while on vacation -> should be DENIED
    result = await check_inventory_access(
        user_email="mike.manager@atko.email",
        relation="can_increase_inventory",
        is_on_vacation=True
    )
    print(f"can_increase_inventory (on vacation): allowed={result.allowed}")
    print(f"  Reason: {result.reason}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        asyncio.run(verify())
    else:
        asyncio.run(seed())
        print("\nTo verify: python -m auth.fga_seed --verify")
