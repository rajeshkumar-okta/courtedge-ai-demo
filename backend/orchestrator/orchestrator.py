"""
Orchestrator - Coordinates multiple agents using LangGraph.

This is the brain of the multi-agent system. It:
1. Receives user messages
2. Determines which agent(s) to invoke
3. Manages token exchange for each agent
4. Coordinates multi-agent workflows
5. Returns unified responses with audit trail
"""

from typing import Dict, Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, END

from agents import SalesAgent, InventoryAgent, PricingAgent, CustomerAgent


class WorkflowState(TypedDict):
    """State passed through the LangGraph workflow."""
    messages: List[Any]
    user_message: str
    user_info: Dict[str, Any]
    user_token: str

    # Agent results
    sales_result: Optional[Dict[str, Any]]
    inventory_result: Optional[Dict[str, Any]]
    pricing_result: Optional[Dict[str, Any]]
    customer_result: Optional[Dict[str, Any]]

    # Tracking for demo visibility
    agent_flow: List[Dict[str, Any]]
    token_exchanges: List[Dict[str, Any]]

    # Final response
    final_response: Optional[str]


class Orchestrator:
    """
    Multi-agent orchestrator using LangGraph.

    Routes requests to appropriate agents and coordinates
    complex multi-agent workflows.
    """

    def __init__(self, user_token: str, okta_auth: Optional[Any] = None):
        """
        Initialize the orchestrator with user context.

        Args:
            user_token: User's access token
            okta_auth: OktaAuth instance for token exchange
        """
        self.user_token = user_token
        self.okta_auth = okta_auth

        # Initialize agents
        self.sales_agent = SalesAgent(user_token, okta_auth)
        self.inventory_agent = InventoryAgent(user_token, okta_auth)
        self.pricing_agent = PricingAgent(user_token, okta_auth)
        self.customer_agent = CustomerAgent(user_token, okta_auth)

        # Build the workflow
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("sales", self._sales_node)
        workflow.add_node("inventory", self._inventory_node)
        workflow.add_node("pricing", self._pricing_node)
        workflow.add_node("customer", self._customer_node)
        workflow.add_node("coordinator", self._coordinator_node)

        # Set entry point
        workflow.set_entry_point("router")

        # Add conditional edges from router
        workflow.add_conditional_edges(
            "router",
            self._route_to_agent,
            {
                "sales": "sales",
                "inventory": "inventory",
                "pricing": "pricing",
                "customer": "customer",
                "multi": "sales",  # Start multi-agent with sales
                "general": "coordinator",
            }
        )

        # Agent nodes go to coordinator
        workflow.add_edge("sales", "coordinator")
        workflow.add_edge("inventory", "coordinator")
        workflow.add_edge("pricing", "coordinator")
        workflow.add_edge("customer", "coordinator")

        # Coordinator ends the workflow
        workflow.add_edge("coordinator", END)

        return workflow.compile()

    def _route_to_agent(self, state: WorkflowState) -> str:
        """Determine which agent(s) to route to based on the message."""
        message = state["user_message"].lower()

        # Simple keyword-based routing (will be enhanced with LLM)
        if any(word in message for word in ["order", "quote", "deal", "sale"]):
            return "sales"
        elif any(word in message for word in ["stock", "inventory", "product", "warehouse"]):
            return "inventory"
        elif any(word in message for word in ["price", "discount", "margin", "cost"]):
            return "pricing"
        elif any(word in message for word in ["customer", "account", "contact", "client"]):
            return "customer"
        elif any(word in message for word in ["create a quote", "process order"]):
            return "multi"  # Multi-agent workflow
        else:
            return "general"

    async def _router_node(self, state: WorkflowState) -> WorkflowState:
        """Router node - logs the routing decision."""
        state["agent_flow"].append({
            "step": "router",
            "action": "Analyzing request",
            "message": state["user_message"][:100]
        })
        return state

    async def _sales_node(self, state: WorkflowState) -> WorkflowState:
        """Sales agent node."""
        result = await self.sales_agent.process(
            state["user_message"],
            {"user_info": state["user_info"]}
        )
        state["sales_result"] = result
        state["agent_flow"].append({
            "step": "sales-agent",
            "action": "Processing sales request",
            "result": result["result"]
        })
        state["token_exchanges"].append(result["token_exchange"])
        return state

    async def _inventory_node(self, state: WorkflowState) -> WorkflowState:
        """Inventory agent node."""
        result = await self.inventory_agent.process(
            state["user_message"],
            {"user_info": state["user_info"]}
        )
        state["inventory_result"] = result
        state["agent_flow"].append({
            "step": "inventory-agent",
            "action": "Processing inventory request",
            "result": result["result"]
        })
        state["token_exchanges"].append(result["token_exchange"])
        return state

    async def _pricing_node(self, state: WorkflowState) -> WorkflowState:
        """Pricing agent node."""
        result = await self.pricing_agent.process(
            state["user_message"],
            {"user_info": state["user_info"]}
        )
        state["pricing_result"] = result
        state["agent_flow"].append({
            "step": "pricing-agent",
            "action": "Processing pricing request",
            "result": result["result"]
        })
        state["token_exchanges"].append(result["token_exchange"])
        return state

    async def _customer_node(self, state: WorkflowState) -> WorkflowState:
        """Customer agent node."""
        result = await self.customer_agent.process(
            state["user_message"],
            {"user_info": state["user_info"]}
        )
        state["customer_result"] = result
        state["agent_flow"].append({
            "step": "customer-agent",
            "action": "Processing customer request",
            "result": result["result"]
        })
        state["token_exchanges"].append(result["token_exchange"])
        return state

    async def _coordinator_node(self, state: WorkflowState) -> WorkflowState:
        """Coordinator node - combines results and generates final response."""
        # Collect all agent results
        results = []
        if state.get("sales_result"):
            results.append(state["sales_result"]["result"])
        if state.get("inventory_result"):
            results.append(state["inventory_result"]["result"])
        if state.get("pricing_result"):
            results.append(state["pricing_result"]["result"])
        if state.get("customer_result"):
            results.append(state["customer_result"]["result"])

        # Generate final response
        if results:
            state["final_response"] = "\n".join(results)
        else:
            state["final_response"] = "I'm not sure how to help with that. Try asking about orders, inventory, pricing, or customers."

        state["agent_flow"].append({
            "step": "coordinator",
            "action": "Combining agent results",
            "agents_used": len(results)
        })

        return state

    async def process(self, message: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a user message through the orchestrator.

        Args:
            message: User's message
            user_info: Information about the user

        Returns:
            Dict with response, agent flow, and token exchanges
        """
        # Initialize state
        initial_state: WorkflowState = {
            "messages": [],
            "user_message": message,
            "user_info": user_info,
            "user_token": self.user_token,
            "sales_result": None,
            "inventory_result": None,
            "pricing_result": None,
            "customer_result": None,
            "agent_flow": [],
            "token_exchanges": [],
            "final_response": None,
        }

        # Run the workflow
        final_state = await self.workflow.ainvoke(initial_state)

        return {
            "content": final_state["final_response"],
            "agent_flow": final_state["agent_flow"],
            "token_exchanges": final_state["token_exchanges"],
        }
