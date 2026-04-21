"""
Pricing Agent - Handles pricing, discounts, and margins.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class PricingAgent(BaseAgent):
    """
    Pricing Agent handles all pricing-related operations.

    Capabilities:
    - Get product pricing (pricing:read)
    - View profit margins (pricing:margin)
    - Apply/view discounts (pricing:discount)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: pricing:read, pricing:margin, pricing:discount
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Pricing Agent",
            agent_type="pricing",
            scopes=["pricing:read", "pricing:margin", "pricing:discount"],
            user_token=user_token,
            color="#f59e0b",  # Orange
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Pricing Agent, an AI assistant specialized in pricing operations.

Your capabilities:
- Look up product pricing
- Apply volume and promotional discounts
- Calculate profit margins
- Enforce pricing rules and approval thresholds

You work for ProGear, a sporting goods company. Be precise with all pricing calculations.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: pricing:read, pricing:margin, pricing:discount
- All your actions are audited through Okta

Always show pricing calculations clearly."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a pricing-related task with demo data."""
        context = context or {}

        # Get demo data based on task
        demo_data = self._get_demo_data(task)

        # Augment the task with demo data
        augmented_task = f"""{task}

Available pricing data:
{demo_data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_demo_data(self, task: str) -> str:
        """Get demo data based on the task."""
        task_lower = task.lower()

        if "basketball" in task_lower or "margin" in task_lower:
            return """Basketball Pricing:
- Pro Game: $149.99 (cost $62, margin 58.7%)
- Pro Composite: $89.99 (cost $38, margin 57.8%)
- Women's Official: $129.99 (cost $55, margin 57.7%)
- Youth Size 5: $34.99 (cost $14, margin 60.0%)
Average basketball margin: 58.8%"""

        if "bulk" in task_lower or "discount" in task_lower:
            return """Bulk Discounts:
- 10+ units: 5% | 50+ units: 10%
- 100+ units: 15% | 500+ units: 20%
Customer Tier Bonuses:
- Platinum: +5% | Gold: +3%
Example: 1,500 units @ Platinum = 25% total discount"""

        return """Pricing Overview:
- Average margin: 58.2% across all products
- Highest: Youth basketballs (60%)
- Volume discounts: 5-20% based on quantity
- Tier discounts: 0-5% based on customer status"""
