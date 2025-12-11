"""
Sales Agent - Handles orders, quotes, and deals.

This is a VISIBLE agent class - customers can see this code.
The agent is registered as a first-class identity in Okta.
"""

from typing import Dict, Any, Optional
from langchain_anthropic import ChatAnthropic


class SalesAgent:
    """
    Sales Agent handles all sales-related operations.

    Capabilities:
    - Create and manage quotes
    - Process orders
    - Track deals and pipeline

    Security:
    - Registered as Okta AI Agent
    - Uses token exchange (ID-JAG) for MCP access
    - Scoped to sales:read, sales:write
    """

    def __init__(self, user_token: str, okta_auth: Optional[Any] = None):
        """
        Initialize the Sales Agent.

        Args:
            user_token: The user's access token (will be exchanged for agent token)
            okta_auth: OktaAuth instance for token exchange
        """
        self.user_token = user_token
        self.okta_auth = okta_auth
        self.agent_name = "sales-agent"
        self.scopes = ["sales:read", "sales:write"]

        # Initialize LLM (Claude)
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.7,
        )

    async def get_agent_token(self) -> str:
        """
        Exchange user token for sales agent token.

        This is the ID-JAG flow:
        User Token -> ID-JAG Token -> MCP Access Token
        """
        if not self.okta_auth:
            return "demo-token"  # Demo mode

        # TODO: Implement actual token exchange
        # return await self.okta_auth.exchange_token(
        #     token=self.user_token,
        #     target_audience="sales-agent-audience",
        #     scope=" ".join(self.scopes)
        # )
        return "demo-token"

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a sales-related task.

        Args:
            task: The task description from the user
            context: Additional context (user info, conversation history, etc.)

        Returns:
            Dict with result, agent info, and token exchange details
        """
        # Get agent-specific token
        agent_token = await self.get_agent_token()

        # TODO: Use agent_token to call MCP tools
        # For now, return demo response

        return {
            "agent": self.agent_name,
            "result": f"[Sales Agent] Processing: {task}",
            "token_exchange": {
                "from": "user",
                "to": "sales-agent",
                "audience": "sales-agent-audience",
                "scopes": self.scopes,
            },
            "tools_called": [],  # Will be populated when MCP is connected
        }

    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return """You are the ProGear Sales Agent, an AI assistant specialized in sales operations.

Your capabilities:
- Create and manage sales quotes
- Process customer orders
- Track deals in the pipeline
- Provide sales analytics and insights

You work for ProGear, a sporting goods company. Always be helpful, professional, and accurate.
When you need data, you'll use MCP tools to access the sales database.

Important: You operate with security controls. Your access is scoped to sales data only,
and all your actions are audited through Okta."""
