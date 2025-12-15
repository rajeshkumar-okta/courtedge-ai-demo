"""
ProGear Sales AI - FastAPI Backend
Main entry point for the API server.
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from auth.okta_auth import get_okta_auth, OktaAuth
from auth.okta_cross_app_access import get_cross_app_manager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ProGear Sales AI API",
    description="AI-powered sales assistant backend with Okta + Auth0 security",
    version="0.1.0",
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    session_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    content: str
    session_id: str
    agent_type: str  # Which agent handled the request
    agent_flow: Optional[List[Dict[str, Any]]] = None  # For multi-agent workflows
    token_exchanges: Optional[List[Dict[str, Any]]] = None  # For demo visibility
    mcp_info: Optional[Dict[str, Any]] = None  # MCP server calls


# --- Health Check ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "progear-sales-api",
        "version": "0.1.0"
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "ProGear Sales AI API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


# --- Helper to extract token ---

async def get_user_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization


# --- Chat Endpoint ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Main chat endpoint.

    This will:
    1. Authenticate the user (via Okta token)
    2. Perform ID-JAG token exchange
    3. Route to appropriate agent(s)
    4. Return response with audit trail
    """
    # Debug: Log what we received
    logger.info(f"=== Chat Request Received ===")
    logger.info(f"Authorization header present: {authorization is not None}")
    logger.info(f"Authorization header value: {authorization[:50] + '...' if authorization else 'None'}")

    okta_auth = get_okta_auth()
    token_exchanges = []
    user_info = None

    # Extract user token
    user_token = None
    if authorization and authorization.startswith("Bearer "):
        user_token = authorization[7:]

    # Validate user and perform token exchange
    if user_token:
        try:
            # Get user info from token
            user_claims = await okta_auth.validate_token(user_token)
            user_info = {
                "sub": user_claims.get("sub"),
                "email": user_claims.get("email"),
                "name": user_claims.get("name"),
            }
            logger.info(f"User authenticated: {user_info.get('email', 'unknown')}")

            # Perform ID-JAG token exchange for MCP access using the new SDK
            logger.info("Attempting ID-JAG token exchange via Okta AI SDK...")
            cross_app_manager = get_cross_app_manager()
            mcp_token_result = await cross_app_manager.exchange_id_to_mcp_token(user_token)

            if mcp_token_result:
                token_exchanges.append({
                    "type": "ID-JAG Token Exchange",
                    "from": "User ID Token",
                    "to": "MCP Access Token",
                    "audience": okta_auth.mcp_audience,
                    "scopes": mcp_token_result.get("scope", "").split() if mcp_token_result.get("scope") else [],
                    "success": True,
                    "demo_mode": mcp_token_result.get("demo_mode", False),
                    "subject": mcp_token_result.get("subject"),
                })
                logger.info(f"Token exchange successful! Scopes: {mcp_token_result.get('scope')}")
            else:
                raise ValueError("Token exchange returned no result")

        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            token_exchanges.append({
                "type": "ID-JAG Token Exchange",
                "error": str(e),
                "success": False,
            })

    # Build response content
    if token_exchanges and token_exchanges[0].get("success"):
        exchange_info = token_exchanges[0]
        if exchange_info.get("demo_mode"):
            content = (
                f"[ID-JAG Demo] Your message: '{request.message}'\n\n"
                f"Token Exchange Details:\n"
                f"- User: {user_info.get('email', 'unknown') if user_info else 'unknown'}\n"
                f"- Target Audience: {exchange_info.get('audience')}\n"
                f"- Scopes Granted: {', '.join(exchange_info.get('scopes', []))}\n"
                f"- Mode: Demo (configure OKTA_AI_AGENT_PRIVATE_KEY for production)\n\n"
                f"The AI Agent would now use this MCP token to access inventory, pricing, and customer data."
            )
        else:
            content = (
                f"[ID-JAG Active] Your message: '{request.message}'\n\n"
                f"Token Exchange Successful!\n"
                f"- User: {user_info.get('email', 'unknown') if user_info else 'unknown'}\n"
                f"- MCP Audience: {exchange_info.get('audience')}\n"
                f"- Scopes: {', '.join(exchange_info.get('scopes', []))}\n\n"
                f"The AI Agent can now securely access MCP resources on your behalf."
            )
    else:
        content = f"[No Auth] Received: {request.message}. Sign in for full ID-JAG demo."

    return ChatResponse(
        content=content,
        session_id=request.session_id or "demo-session",
        agent_type="sales-agent",
        agent_flow=[
            {"agent": "sales-agent", "action": "process_request", "status": "completed"}
        ],
        token_exchanges=token_exchanges,
        mcp_info={
            "audience": okta_auth.mcp_audience,
            "auth_server": okta_auth.mcp_auth_server_id,
        }
    )


# --- Agent Status Endpoint ---

@app.get("/api/agents/status")
async def agent_status():
    """Get status of all agents."""
    return {
        "agents": [
            {"name": "sales-agent", "status": "pending", "description": "Orders, quotes, deals"},
            {"name": "inventory-agent", "status": "pending", "description": "Stock levels, products"},
            {"name": "pricing-agent", "status": "pending", "description": "Discounts, margins"},
            {"name": "customer-agent", "status": "pending", "description": "Accounts, contacts"},
        ],
        "orchestrator": "pending",
        "mcp_servers": ["sales-mcp", "inventory-mcp", "customer-mcp"]
    }


# --- Okta Config Endpoint (for frontend) ---

@app.get("/api/config/okta")
async def okta_config():
    """
    Return Okta configuration for frontend.
    Only returns public information.
    """
    return {
        "domain": os.getenv("OKTA_DOMAIN", ""),
        "clientId": os.getenv("OKTA_CLIENT_ID", ""),
        "issuer": os.getenv("OKTA_ISSUER", ""),
        # Never return secrets!
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
