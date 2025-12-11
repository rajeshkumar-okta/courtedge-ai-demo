"""
ProGear Sales AI - FastAPI Backend
Main entry point for the API server.
"""

import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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


# --- Chat Endpoint ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    This will:
    1. Authenticate the user (via Okta token)
    2. Route to appropriate agent(s)
    3. Perform token exchange if needed
    4. Return response with audit trail
    """
    # TODO: Implement full chat logic with LangGraph orchestrator
    # For now, return a placeholder response

    return ChatResponse(
        content=f"[Demo Mode] Received: {request.message}. Full implementation coming soon!",
        session_id=request.session_id or "demo-session",
        agent_type="placeholder",
        agent_flow=[],
        token_exchanges=[],
        mcp_info=None
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
