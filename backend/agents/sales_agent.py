"""
Sales Agent - The orchestrator for ProGear sales operations.

Registered as a first-class identity in Okta's AI Agent Directory.
Uses raw Anthropic SDK for LLM calls.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class SalesAgent(BaseAgent):
    """
    Sales Agent - The primary agent for ProGear sales.

    Capabilities:
    - Create and manage sales quotes
    - Process customer orders
    - Track deals and pipeline
    - Provide sales analytics

    Security:
    - Registered in Okta AI Agent Directory
    - Uses ID-JAG (Cross App Access) for token exchange
    - Scopes: sales:read, sales:quote, sales:order
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Sales Agent",
            agent_type="sales",
            scopes=["sales:read", "sales:quote", "sales:order"],
            user_token=user_token,
            color="#3b82f6",  # Blue
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Sales Agent, an AI assistant specialized in sales operations for ProGear Sporting Goods.

Your capabilities:
- Create and manage sales quotes for sporting goods equipment
- Process customer orders
- Track deals in the sales pipeline
- Provide sales analytics and insights

You work for ProGear, a B2B sporting goods company serving retailers and sports teams.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- You authenticate using a JWK private key (JWT Bearer)
- Your access to data is controlled by scopes: sales:read, sales:quote, sales:order
- All your actions are audited through Okta
- You are acting ON BEHALF OF the logged-in user - their permissions apply

When responding, be helpful, professional, and accurate. Focus on sales-related information."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a sales-related task with demo data augmentation."""
        context = context or {}

        # Get demo data to include in response
        demo_data = self._get_demo_data(task)

        # Augment the task with demo data
        augmented_task = f"""{task}

Available data to reference:
{demo_data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_demo_data(self, task: str) -> str:
        """Get demo data based on the task."""
        task_lower = task.lower()

        if "order" in task_lower or "recent" in task_lower:
            return """Recent Orders:
- ORD-2024-001: State University Athletics - $7,109.53 (shipped)
- ORD-2024-002: Metro High School District - $23,796.60 (processing)
- ORD-2024-003: Riverside Youth League - $3,608.95 (pending)
- ORD-2024-004: City Pro Basketball Academy - $5,669.69 (shipped)
Pipeline Value: $40,184.77 this week"""

        return """Sales Summary:
- Active orders: 5 orders totaling $40,184.77
- Top customer: Metro High School District ($124,500 lifetime)
- Quote ready for 1,500 basketballs @ 20% bulk discount"""
