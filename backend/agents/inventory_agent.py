"""
Inventory Agent - Handles stock levels and products.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.

IMPORTANT: This agent has FGA (Fine-Grained Authorization) integration.
- Write operations require FGA check with contextual tuples
- Users on vacation are denied write access via FGA
- FGA model: can_increase_inventory = manager but not on_vacation
"""

import re
from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class InventoryAgent(BaseAgent):
    """
    Inventory Agent handles all inventory-related operations.

    Capabilities:
    - Check stock levels (inventory:read)
    - List products (inventory:read)
    - Add/update inventory (inventory:write) - FGA protected
    - Manage inventory alerts (inventory:alert)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: inventory:read, inventory:write, inventory:alert
    - FGA check for write operations (vacation check via contextual tuples)
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Inventory Agent",
            agent_type="inventory",
            scopes=["inventory:read", "inventory:write", "inventory:alert"],
            user_token=user_token,
            color="#10b981",  # Green
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Inventory Agent, an AI assistant specialized in inventory management.

Your capabilities:
- Check real-time stock levels for any product
- List available products by category
- Add or update inventory quantities (if authorized)
- Track warehouse and fulfillment status
- Manage low-stock alerts

You work for ProGear, a sporting goods company. Provide accurate inventory information.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: inventory:read, inventory:write, inventory:alert
- WRITE operations are additionally protected by Auth0 FGA (Fine-Grained Authorization)
- FGA checks if the user is on vacation - managers on vacation cannot modify inventory
- All your actions are audited through Okta

When processing inventory updates, confirm the action clearly."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process an inventory-related task with demo data."""
        context = context or {}
        scopes = context.get("scopes", self.scopes)

        # Get demo data based on task and scopes
        demo_data = self._get_demo_data(task, scopes)

        # Augment the task with demo data
        augmented_task = f"""{task}

Available data and action result:
{demo_data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_demo_data(self, task: str, scopes: list = None) -> str:
        """Get demo data based on the task and scopes."""
        task_lower = task.lower()
        scopes = scopes or []

        # Check if this is a WRITE operation
        has_write_scope = "inventory:write" in scopes
        is_write_request = any(kw in task_lower for kw in [
            "add", "update", "increase", "set", "put", "remove", "decrease"
        ])

        if has_write_scope and is_write_request:
            # Extract quantity from task
            qty_match = re.search(r'(\d+)\s*(basket|ball|unit)', task_lower)
            quantity = qty_match.group(1) if qty_match else "30"

            return f"""INVENTORY UPDATE SUCCESSFUL:
- Action: Added {quantity} basketballs to inventory
- Product: Pro Game Basketball (default SKU)
- Previous count: 2,847 units
- New count: {int(quantity) + 2847} units
- Status: CONFIRMED
- Transaction ID: INV-2026-{hash(task) % 10000:04d}
Total basketballs now: {12219 + int(quantity)} units"""

        # Read-only inventory data
        if "basketball" in task_lower:
            return """Basketball Inventory:
- Pro Game Basketball: 2,847 units - GOOD
- Pro Composite: 1,523 units - GOOD
- Women's Official: 1,234 units - GOOD
- Youth Size 5: 3,567 units - GOOD
- Youth Size 4: 2,156 units - GOOD
Total basketballs: 12,219 units available"""

        return """Inventory Summary:
- Basketballs: 12,219 units (6 SKUs)
- Hoops & Backboards: 769 units (4 SKUs)
- Uniforms: 21,120 units (4 SKUs)
- Training Equipment: 4,700 units (4 SKUs)
Low stock alert: Pro Arena Hoop System (45 units)"""
