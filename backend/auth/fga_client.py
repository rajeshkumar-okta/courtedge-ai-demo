"""
Auth0 FGA Client for Agent Permission Gating

Evaluates fine-grained authorization using Okta token claims.
This demonstrates "Okta + FGA Better Together":
- Okta: Identity (ID-JAG), coarse-grained RBAC (group membership)
- FGA: Fine-grained, contextual authorization (runtime conditions)

Instead of requiring pre-seeded FGA tuples for every user, we evaluate
the FGA model logic using claims from the authenticated user's token:
- is_a_manager: From Okta user profile (Manager claim)
- is_on_vacation: From Okta user profile (Vacation claim)

FGA Model Logic (evaluated locally using token claims):
  type inventory_system
    relations
      define can_increase_inventory: manager
      define manager: [user with check_vacation]

  condition check_vacation(is_on_vacation: bool) {
    is_on_vacation == false
  }

This approach:
- Works for ANY authenticated user (no hardcoded tuples)
- Uses Okta as single source of truth for user attributes
- Maintains same FGA decision logic and UI visualization
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
# Only inventory_system is modeled for now.
# Other agents pass through (no FGA check).
AGENT_TO_FGA_OBJECT = {
    "inventory": "inventory_system:main_db",
}


def check_inventory_access_from_claims(
    user_email: str,
    is_a_manager: bool,
    is_on_vacation: bool,
    relation: str = "manager",
) -> FGACheckResult:
    """
    Evaluate FGA-style authorization using Okta token claims.

    Applies the same logic as the FGA model:
    - manager relation: user must be a manager AND not on vacation
    - can_increase_inventory: derived from manager (same rules)

    Args:
        user_email: User's email from token
        is_a_manager: From Okta 'Manager' claim (user.is_a_manager)
        is_on_vacation: From Okta 'Vacation' claim (user.is_on_vacation)
        relation: FGA relation to evaluate ("manager" or "can_increase_inventory")

    Returns:
        FGACheckResult with allowed status and explanation
    """
    user_id = f"user:{user_email}"
    object_id = "inventory_system:main_db"
    context = {
        "is_a_manager": is_a_manager,
        "is_on_vacation": is_on_vacation,
    }

    # Apply FGA model logic using token claims
    # manager: [user with check_vacation]
    # check_vacation: is_on_vacation == false

    if not is_a_manager:
        # User doesn't have manager attribute
        allowed = False
        reason = f"Access denied: {user_email} is not a manager (is_a_manager=false)"
    elif is_on_vacation:
        # User is a manager but on vacation - condition fails
        allowed = False
        reason = f"Access denied: {user_email} is on vacation - check_vacation condition failed"
    else:
        # User is a manager and not on vacation - allowed
        allowed = True
        reason = f"Access granted: {user_email} is a manager and not on vacation"

    logger.info(
        f"FGA check (claims-based): {user_id} {relation} {object_id} "
        f"(manager={is_a_manager}, vacation={is_on_vacation}) -> {allowed}"
    )

    return FGACheckResult(
        allowed=allowed,
        relation=relation,
        object=object_id,
        user=user_id,
        context=context,
        reason=reason
    )


async def check_agent_access(
    user_email: str,
    agent_type: str,
    scopes: list = None,
    is_a_manager: bool = False,
    is_on_vacation: bool = False,
) -> FGACheckResult:
    """
    Check if a user can access a specific agent using token claims.

    Currently only inventory_system has FGA-style checks.
    Other agents pass through (return allowed=True).

    For inventory:
    - Write scopes (inventory:write) -> checks "can_increase_inventory"
    - Read scopes -> checks "manager"

    Args:
        user_email: User's email address from token
        agent_type: Agent type (sales, inventory, customer, pricing)
        scopes: Requested scopes (used to determine read vs write check)
        is_a_manager: From Okta token claim
        is_on_vacation: From Okta token claim

    Returns:
        FGACheckResult with allowed status and explanation
    """
    scopes = scopes or []

    # Only inventory has FGA-style checks - others pass through
    if agent_type not in AGENT_TO_FGA_OBJECT:
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=f"{agent_type}_system",
            user=f"user:{user_email}",
            context={"is_a_manager": is_a_manager, "is_on_vacation": is_on_vacation},
            reason=f"No FGA model for {agent_type} - Okta RBAC only"
        )

    # Determine which relation to check based on requested scopes
    if scopes and "inventory:write" in scopes:
        relation = "can_increase_inventory"
    else:
        relation = "manager"

    return check_inventory_access_from_claims(
        user_email=user_email,
        is_a_manager=is_a_manager,
        is_on_vacation=is_on_vacation,
        relation=relation,
    )


def is_fga_configured() -> bool:
    """
    Check if FGA-style checks are enabled.

    Since we're using token claims, this is always True
    as long as the claims are present in the token.
    """
    return True


def get_fga_model_info() -> Dict[str, Any]:
    """Get FGA model information for UI display."""
    return {
        "mode": "claims-based",
        "description": "FGA logic evaluated using Okta token claims",
        "model_description": {
            "type": "inventory_system",
            "relations": {
                "manager": "User with is_a_manager=true AND is_on_vacation=false",
                "can_increase_inventory": "Derived from manager - can modify inventory"
            },
            "condition": {
                "name": "check_vacation",
                "description": "Blocks access when is_on_vacation == true",
                "source": "Okta user profile attribute"
            }
        },
        "claims_used": [
            {"name": "Manager", "okta_attribute": "user.is_a_manager"},
            {"name": "Vacation", "okta_attribute": "user.is_on_vacation"},
        ]
    }
