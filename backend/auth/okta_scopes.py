"""
Okta Scope Definitions

Centralized definitions for all OAuth scopes used in the demo.
Each agent has specific scopes for its domain.
"""


class SalesScopes:
    """Scopes for Sales Agent."""
    READ = "sales:read"
    WRITE = "sales:write"
    READ_WRITE = "sales:read sales:write"


class InventoryScopes:
    """Scopes for Inventory Agent."""
    READ = "inventory:read"
    WRITE = "inventory:write"
    READ_WRITE = "inventory:read inventory:write"


class PricingScopes:
    """Scopes for Pricing Agent."""
    READ = "pricing:read"
    WRITE = "pricing:write"
    READ_WRITE = "pricing:read pricing:write"


class CustomerScopes:
    """Scopes for Customer Agent."""
    READ = "customer:read"
    WRITE = "customer:write"
    READ_WRITE = "customer:read customer:write"


class MCPScopes:
    """Scopes for MCP Server access."""
    READ = "mcp:read"
    WRITE = "mcp:write"
    READ_WRITE = "mcp:read mcp:write"


class OKTA_SCOPES:
    """
    All Okta scopes organized by domain.

    Usage:
        from auth.okta_scopes import OKTA_SCOPES

        scope = OKTA_SCOPES.SALES.READ_WRITE
    """
    SALES = SalesScopes
    INVENTORY = InventoryScopes
    PRICING = PricingScopes
    CUSTOMER = CustomerScopes
    MCP = MCPScopes
