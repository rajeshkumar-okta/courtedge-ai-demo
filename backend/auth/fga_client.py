"""
Auth0 FGA Client for Agent Permission Gating

Checks whether a user can access the inventory system before
attempting Okta token exchange. Uses the check_vacation condition
to block managers who are on vacation.

This demonstrates "Okta + FGA Better Together":
- Okta: Identity (ID-JAG), coarse-grained RBAC (group membership)
- FGA: Fine-grained, contextual authorization (runtime conditions)

FGA Model (already in store):
  type inventory_system
    relations
      define can_increase_inventory: manager
      define manager: [user with check_vacation]

  condition check_vacation(is_on_vacation: bool) {
    is_on_vacation == false
  }
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Lazy import to avoid startup errors if FGA not configured
_fga_client = None
_fga_config = None


@dataclass
class FGACheckResult:
    """Result of an FGA permission check."""
    allowed: bool
    relation: str
    object: str
    user: str
    context: Dict[str, Any]
    reason: str  # Human-readable explanation


# Maps ProGear agent types -> FGA object types
# Only inventory_system is modeled in FGA for now.
# Other agents pass through (no FGA check).
AGENT_TO_FGA_OBJECT = {
    "inventory": "inventory_system:main_db",
}


def _get_fga_config():
    """Build FGA configuration from environment variables."""
    global _fga_config
    if _fga_config is not None:
        return _fga_config

    api_url = os.getenv("FGA_API_URL", "")
    store_id = os.getenv("FGA_STORE_ID", "")
    client_id = os.getenv("FGA_CLIENT_ID", "")
    client_secret = os.getenv("FGA_CLIENT_SECRET", "")

    if not all([api_url, store_id, client_id, client_secret]):
        logger.info("FGA not configured - skipping fine-grained checks")
        return None

    try:
        from openfga_sdk import ClientConfiguration
        from openfga_sdk.credentials import Credentials, CredentialConfiguration

        _fga_config = ClientConfiguration(
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
        logger.info(f"FGA configured: store={store_id}, url={api_url}")
        return _fga_config
    except ImportError:
        logger.warning("openfga_sdk not installed - FGA checks disabled")
        return None
    except Exception as e:
        logger.error(f"FGA configuration failed: {e}")
        return None


async def check_inventory_access(
    user_email: str,
    relation: str = "manager",
    is_on_vacation: bool = False,
) -> FGACheckResult:
    """
    Check if a user has access to the inventory system via FGA.

    The check_vacation condition is passed as context - if the user
    is on vacation, FGA denies access even if they are a manager.

    Args:
        user_email: User's email (e.g., "mike.manager@atko.email")
        relation: FGA relation to check ("manager" or "can_increase_inventory")
        is_on_vacation: Whether the user is currently on vacation (from Okta profile)

    Returns:
        FGACheckResult with allowed status and explanation
    """
    config = _get_fga_config()
    context = {"is_on_vacation": is_on_vacation}
    user_id = f"user:{user_email}"
    object_id = "inventory_system:main_db"

    if config is None:
        return FGACheckResult(
            allowed=True,
            relation=relation,
            object=object_id,
            user=user_id,
            context=context,
            reason="FGA not configured - relying on Okta RBAC"
        )

    try:
        from openfga_sdk import OpenFgaClient
        from openfga_sdk.client.models import ClientCheckRequest

        async with OpenFgaClient(config) as fga:
            response = await fga.check(ClientCheckRequest(
                user=user_id,
                relation=relation,
                object=object_id,
                context=context,
            ))
            allowed = response.allowed

            if allowed:
                reason = f"FGA allowed: {user_email} has '{relation}' on inventory_system"
            else:
                if is_on_vacation:
                    reason = f"FGA denied: {user_email} is on vacation - check_vacation condition failed"
                else:
                    reason = f"FGA denied: {user_email} does not have '{relation}' relation"

            logger.info(
                f"FGA check: {user_id} {relation} {object_id} "
                f"(vacation={is_on_vacation}) -> {allowed}"
            )
            return FGACheckResult(
                allowed=allowed,
                relation=relation,
                object=object_id,
                user=user_id,
                context=context,
                reason=reason
            )
    except Exception as e:
        logger.error(f"FGA check failed: {e} - allowing (fail-open)")
        return FGACheckResult(
            allowed=True,
            relation=relation,
            object=object_id,
            user=user_id,
            context=context,
            reason=f"FGA check error: {str(e)} - fail-open"
        )


async def check_agent_access(
    user_email: str,
    agent_type: str,
    scopes: list = None,
    is_on_vacation: bool = False,
) -> FGACheckResult:
    """
    Check if a user can access a specific agent via FGA.

    Currently only inventory_system is modeled in FGA.
    Other agents pass through (return allowed=True).

    For inventory:
    - Write scopes (inventory:write) -> checks "can_increase_inventory"
    - Read scopes -> checks "manager"

    Args:
        user_email: User's email address
        agent_type: Agent type (sales, inventory, customer, pricing)
        scopes: Requested scopes (used to determine read vs write check)
        is_on_vacation: Whether the user is currently on vacation

    Returns:
        FGACheckResult with allowed status and explanation
    """
    scopes = scopes or []

    # Only inventory has an FGA model - others pass through
    if agent_type not in AGENT_TO_FGA_OBJECT:
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=f"{agent_type}_system",
            user=f"user:{user_email}",
            context={"is_on_vacation": is_on_vacation},
            reason=f"No FGA model for {agent_type} - Okta RBAC only"
        )

    # Determine which relation to check based on requested scopes
    if scopes and "inventory:write" in scopes:
        relation = "can_increase_inventory"
    else:
        relation = "manager"

    return await check_inventory_access(user_email, relation, is_on_vacation)


def is_fga_configured() -> bool:
    """Check if FGA is configured."""
    return _get_fga_config() is not None


def get_fga_model_info() -> Dict[str, Any]:
    """Get FGA model information for UI display."""
    return {
        "store_id": os.getenv("FGA_STORE_ID", ""),
        "model_id": os.getenv("FGA_MODEL_ID", ""),
        "api_url": os.getenv("FGA_API_URL", ""),
        "configured": is_fga_configured(),
        "model_description": {
            "type": "inventory_system",
            "relations": {
                "manager": "User assigned as manager with vacation check",
                "can_increase_inventory": "Derived from manager - can modify inventory"
            },
            "condition": {
                "name": "check_vacation",
                "description": "Blocks access when is_on_vacation == true"
            }
        }
    }
