"""
Customer Agent - Handles accounts, contacts, and customer data.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class CustomerAgent(BaseAgent):
    """
    Customer Agent handles all customer-related operations.

    Capabilities:
    - Look up customer accounts (customer:read)
    - Search/find customers (customer:lookup)
    - View purchase history (customer:history)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: customer:read, customer:lookup, customer:history
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Customer Agent",
            agent_type="customer",
            scopes=["customer:read", "customer:lookup", "customer:history"],
            user_token=user_token,
            color="#8b5cf6",  # Purple
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Customer Agent, an AI assistant specialized in customer management.

Your capabilities:
- Look up customer accounts and profiles
- Search for customers by name, email, or account number
- View purchase and order history
- Check customer tier, loyalty status, and preferences

You work for ProGear, a sporting goods company. Protect customer privacy and only share relevant info.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: customer:read, customer:lookup, customer:history
- All your actions are audited through Okta

Be helpful while respecting customer data privacy."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a customer-related task with demo data."""
        context = context or {}

        # Get demo data based on task
        demo_data = self._get_demo_data(task)

        # Augment the task with demo data
        augmented_task = f"""{task}

Available customer data:
{demo_data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_demo_data(self, task: str) -> str:
        """Get demo data based on the task."""
        task_lower = task.lower()

        if "state" in task_lower or "university" in task_lower:
            return """Customer: State University Athletics
- Tier: Platinum
- Lifetime Value: $89,500 (156 orders)
- Contact: Coach Williams
- Territory: West | Payment: Net 45
Note: Preferred for bulk basketball orders"""

        if "platinum" in task_lower or "tier" in task_lower:
            return """Platinum Tier Customers:
1. Metro High School District - $124,500 lifetime
2. State University Athletics - $89,500 lifetime
3. City Pro Basketball Academy - $67,800 lifetime
Platinum benefits: 5% discount, Net 45-60 terms"""

        return """Customer Overview:
- Platinum: 3 accounts ($281,800 combined)
- Gold: 3 accounts ($63,500 combined)
- Silver: 2 accounts ($15,200 combined)
Top: Metro High School District ($124,500)"""
