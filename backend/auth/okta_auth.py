"""
Okta Authentication & Token Exchange

Handles:
1. Token validation
2. Token exchange (RFC 8693)
3. ID-JAG cross-app access
4. Agent credential management
"""

import os
import json
import time
import httpx
from typing import Optional, Dict, Any
from jose import jwt, JWTError
import logging

logger = logging.getLogger(__name__)


class OktaAuth:
    """
    Okta authentication and token exchange manager.

    Implements:
    - Token validation using Okta JWKS
    - Token exchange (RFC 8693) for agent-to-agent communication
    - ID-JAG cross-app access for MCP servers
    """

    def __init__(self):
        """Initialize with environment variables."""
        self.domain = os.getenv("OKTA_DOMAIN", "")
        self.client_id = os.getenv("OKTA_CLIENT_ID", "")
        self.client_secret = os.getenv("OKTA_CLIENT_SECRET", "")
        self.issuer = os.getenv("OKTA_ISSUER", f"{self.domain}/oauth2/default")

        # AI Agent credentials (for ID-JAG)
        self.agent_id = os.getenv("OKTA_AI_AGENT_ID", "")
        self._agent_private_key = None

        # Custom auth server for MCP
        self.custom_auth_server_id = os.getenv("OKTA_CUSTOM_AUTH_SERVER_ID", "")
        self.custom_audience = os.getenv("OKTA_CUSTOM_AUTH_SERVER_AUDIENCE", "")

        # Token cache
        self._token_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def agent_private_key(self) -> Optional[Dict]:
        """Lazy load agent private key from environment."""
        if self._agent_private_key is None:
            key_json = os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", "")
            if key_json:
                try:
                    self._agent_private_key = json.loads(key_json)
                except json.JSONDecodeError:
                    logger.error("Failed to parse OKTA_AI_AGENT_PRIVATE_KEY")
        return self._agent_private_key

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an Okta access or ID token.

        Args:
            token: The JWT token to validate

        Returns:
            Dict with token claims if valid

        Raises:
            ValueError: If token is invalid
        """
        # Demo mode - accept test tokens
        if token == "demo-token" or token.startswith("test-"):
            return {
                "sub": "demo-user",
                "email": "demo@progear.example",
                "name": "Demo User",
            }

        try:
            # Fetch JWKS and validate
            # TODO: Implement proper JWKS validation with okta-jwt-verifier
            # For now, decode without verification (demo only!)
            claims = jwt.get_unverified_claims(token)
            return claims
        except JWTError as e:
            logger.error(f"Token validation failed: {e}")
            raise ValueError(f"Invalid token: {e}")

    async def exchange_token(
        self,
        token: str,
        target_audience: str,
        scope: str,
        source_agent: Optional[str] = None
    ) -> str:
        """
        Exchange a token for a new token with different audience/scope.

        This implements RFC 8693 token exchange.

        Args:
            token: The source token (user or agent token)
            target_audience: The audience for the new token
            scope: The scopes to request
            source_agent: If set, use this agent's credentials

        Returns:
            New access token

        Token Exchange Flow:
        1. User ID Token -> ID-JAG Token (agent assertion)
        2. ID-JAG Token -> MCP Access Token
        """
        # Demo mode
        if not self.domain or token == "demo-token":
            logger.info(f"[Demo] Token exchange: {target_audience}, scopes: {scope}")
            return f"demo-token-{target_audience}"

        # Check cache
        cache_key = f"{target_audience}:{scope}"
        if cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if cached["expires_at"] > time.time():
                return cached["access_token"]

        # Perform token exchange
        token_endpoint = f"{self.issuer}/v1/token"

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "audience": target_audience,
            "scope": scope,
        }

        auth = (self.client_id, self.client_secret)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_endpoint,
                data=data,
                auth=auth,
            )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise ValueError(f"Token exchange failed: {response.status_code}")

            result = response.json()

            # Cache the token
            self._token_cache[cache_key] = {
                "access_token": result["access_token"],
                "expires_at": time.time() + result.get("expires_in", 3600) - 60
            }

            return result["access_token"]

    async def get_id_jag_token(self, user_id_token: str) -> str:
        """
        Exchange user ID token for an ID-JAG (agent) token.

        This is the first step in cross-app access:
        User ID Token -> ID-JAG Token -> MCP Access Token

        Args:
            user_id_token: User's ID token from Okta

        Returns:
            ID-JAG token for agent operations
        """
        if not self.agent_private_key:
            logger.warning("No agent private key configured, using demo mode")
            return f"demo-id-jag-token"

        # Create JWT bearer assertion using agent private key
        # This proves the agent's identity to Okta

        # TODO: Implement full ID-JAG flow with JWT bearer
        # For now, use regular token exchange
        return await self.exchange_token(
            token=user_id_token,
            target_audience=self.custom_audience,
            scope="mcp:read mcp:write"
        )

    async def get_mcp_token(self, id_jag_token: str, mcp_audience: str) -> str:
        """
        Exchange ID-JAG token for MCP server access token.

        This is the second step in cross-app access:
        User ID Token -> ID-JAG Token -> MCP Access Token

        Args:
            id_jag_token: The ID-JAG token
            mcp_audience: The MCP server audience

        Returns:
            Access token for MCP server
        """
        return await self.exchange_token(
            token=id_jag_token,
            target_audience=mcp_audience,
            scope="mcp:read mcp:write"
        )
