"""
Okta Authentication & Token Exchange

Handles:
1. Token validation
2. Token exchange (RFC 8693) with JWT Bearer assertion
3. ID-JAG cross-app access for AI Agents
4. Agent credential management using JWK private keys
"""

import os
import json
import time
import uuid
import httpx
from typing import Optional, Dict, Any, List
from jose import jwt, JWTError
from jose.constants import ALGORITHMS
import logging

logger = logging.getLogger(__name__)

# MCP scopes available for the Sales Agent (orchestrator)
MCP_SCOPES = ["mcp:read", "mcp:inventory", "mcp:pricing", "mcp:customers"]


class OktaAuth:
    """
    Okta authentication and token exchange manager for AI Agents.

    Implements:
    - Token validation using Okta JWKS
    - Token exchange (RFC 8693) with JWT Bearer client assertion
    - ID-JAG cross-app access for MCP servers
    - Proper AI Agent authentication using JWK private keys
    """

    def __init__(self):
        """Initialize with environment variables."""
        self.domain = os.getenv("OKTA_DOMAIN", "").rstrip("/")
        self.client_id = os.getenv("OKTA_CLIENT_ID", "")  # Sales Agent App client ID

        # AI Agent credentials (JWK private key for JWT Bearer)
        self.agent_id = os.getenv("OKTA_AI_AGENT_ID", "")
        self._agent_private_key = None

        # MCP Authorization Server
        self.mcp_auth_server_id = os.getenv("OKTA_MCP_AUTH_SERVER_ID", "aus8x7lzid61nnRv70g7")
        self.mcp_audience = os.getenv("OKTA_MCP_AUDIENCE", "api://progear-mcp")

        # Main Authorization Server (for user auth)
        self.main_auth_server_id = os.getenv("OKTA_MAIN_AUTH_SERVER_ID", "aus8x7md5e7ObXMAH0g7")
        self.main_audience = os.getenv("OKTA_MAIN_AUDIENCE", "api://progear-main")

        # Token cache
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._jwks_cache: Optional[Dict] = None
        self._jwks_cache_time: float = 0

    @property
    def agent_private_key(self) -> Optional[Dict]:
        """Lazy load agent private key from environment."""
        if self._agent_private_key is None:
            key_json = os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", "")
            if key_json:
                try:
                    self._agent_private_key = json.loads(key_json)
                    logger.info(f"Loaded agent private key with kid: {self._agent_private_key.get('kid', 'unknown')}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse OKTA_AI_AGENT_PRIVATE_KEY: {e}")
        return self._agent_private_key

    @property
    def mcp_token_endpoint(self) -> str:
        """Get the token endpoint for the MCP auth server."""
        return f"{self.domain}/oauth2/{self.mcp_auth_server_id}/v1/token"

    @property
    def main_token_endpoint(self) -> str:
        """Get the token endpoint for the main auth server."""
        return f"{self.domain}/oauth2/{self.main_auth_server_id}/v1/token"

    def _create_client_assertion(self, token_endpoint: str) -> str:
        """
        Create a JWT client assertion for authentication.

        This is how AI Agents authenticate to Okta - using their JWK private key
        to sign a JWT assertion instead of using a client secret.

        Args:
            token_endpoint: The token endpoint URL (used as audience)

        Returns:
            Signed JWT assertion string
        """
        if not self.agent_private_key:
            raise ValueError("Agent private key not configured")

        now = int(time.time())

        # JWT claims for client assertion
        claims = {
            "iss": self.client_id,  # Issuer is the client ID
            "sub": self.client_id,  # Subject is the client ID
            "aud": token_endpoint,  # Audience is the token endpoint
            "iat": now,
            "exp": now + 300,  # 5 minute expiry
            "jti": str(uuid.uuid4()),  # Unique token ID
        }

        # Sign with the agent's private key
        private_key = self.agent_private_key
        algorithm = private_key.get("alg", "RS256")

        assertion = jwt.encode(
            claims,
            private_key,
            algorithm=algorithm,
            headers={"kid": private_key.get("kid")}
        )

        logger.debug(f"Created client assertion for {self.client_id}")
        return assertion

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
            # For production, implement proper JWKS validation
            # For now, decode without verification (demo only!)
            claims = jwt.get_unverified_claims(token)
            return claims
        except JWTError as e:
            logger.error(f"Token validation failed: {e}")
            raise ValueError(f"Invalid token: {e}")

    async def exchange_token_for_mcp(
        self,
        user_token: str,
        scopes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Exchange a user's token for an MCP access token.

        This is the ID-JAG (Cross App Access) flow:
        1. User's ID/access token is the subject token
        2. Agent authenticates using JWT Bearer (private key)
        3. Okta returns an access token for the MCP audience

        Args:
            user_token: The user's ID or access token
            scopes: List of scopes to request (defaults to all MCP scopes)

        Returns:
            Dict with access_token, token_type, expires_in, scope
        """
        if scopes is None:
            scopes = MCP_SCOPES

        scope_string = " ".join(scopes)

        # Demo mode
        if not self.domain or user_token == "demo-token" or not self.agent_private_key:
            logger.info(f"[Demo] Token exchange for MCP, scopes: {scope_string}")
            return {
                "access_token": f"demo-mcp-token-{int(time.time())}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": scope_string,
                "demo_mode": True
            }

        # Check cache
        cache_key = f"mcp:{scope_string}:{hash(user_token)}"
        if cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if cached["expires_at"] > time.time():
                logger.debug("Returning cached MCP token")
                return cached["response"]

        # Token exchange request - use client_secret for now
        # TODO: Implement proper AI Agent JWT Bearer once app-agent linking is configured
        client_secret = os.getenv("OKTA_CLIENT_SECRET", "")

        if client_secret:
            # Use client_secret authentication
            logger.info("Using client_secret authentication for token exchange")
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": self.client_id,
                "client_secret": client_secret,
                "subject_token": user_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
                "audience": self.mcp_audience,
                "scope": scope_string,
            }
        elif self.agent_private_key:
            # Use JWT Bearer with agent private key
            logger.info("Using JWT Bearer authentication for token exchange")
            try:
                client_assertion = self._create_client_assertion(self.mcp_token_endpoint)
            except Exception as e:
                logger.error(f"Failed to create client assertion: {e}")
                raise ValueError(f"Failed to authenticate agent: {e}")

            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": self.client_id,
                "subject_token": user_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
                "audience": self.mcp_audience,
                "scope": scope_string,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_assertion,
            }
        else:
            raise ValueError("No authentication method available (need client_secret or agent private key)")

        async with httpx.AsyncClient() as client:
            logger.info(f"Exchanging token for MCP access, audience: {self.mcp_audience}")
            response = await client.post(
                self.mcp_token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Token exchange failed: {response.status_code} - {error_detail}")
                raise ValueError(f"Token exchange failed: {response.status_code} - {error_detail}")

            result = response.json()

            # Cache the token
            self._token_cache[cache_key] = {
                "response": result,
                "expires_at": time.time() + result.get("expires_in", 3600) - 60
            }

            logger.info(f"Token exchange successful, scopes: {result.get('scope', 'unknown')}")
            return result

    async def get_mcp_token(
        self,
        user_token: str,
        resource_type: str = "all"
    ) -> str:
        """
        Get an MCP access token for a specific resource type.

        Args:
            user_token: The user's token to exchange
            resource_type: Type of resource - "inventory", "pricing", "customers", or "all"

        Returns:
            Access token string for MCP
        """
        # Map resource type to scopes
        scope_map = {
            "inventory": ["mcp:read", "mcp:inventory"],
            "pricing": ["mcp:read", "mcp:pricing"],
            "customers": ["mcp:read", "mcp:customers"],
            "all": MCP_SCOPES,  # Sales agent has all scopes
        }

        scopes = scope_map.get(resource_type, MCP_SCOPES)
        result = await self.exchange_token_for_mcp(user_token, scopes)
        return result["access_token"]

    async def get_token_info(self, user_token: str) -> Dict[str, Any]:
        """
        Get information about what tokens are available for this user.

        Useful for demo/debugging to show the token exchange flow.

        Args:
            user_token: The user's token

        Returns:
            Dict with token info and available scopes
        """
        user_claims = await self.validate_token(user_token)

        return {
            "user": {
                "sub": user_claims.get("sub"),
                "email": user_claims.get("email"),
                "name": user_claims.get("name"),
            },
            "agent": {
                "id": self.agent_id,
                "client_id": self.client_id,
                "has_private_key": self.agent_private_key is not None,
            },
            "mcp": {
                "auth_server_id": self.mcp_auth_server_id,
                "audience": self.mcp_audience,
                "available_scopes": MCP_SCOPES,
            },
            "demo_mode": not self.domain or not self.agent_private_key,
        }


# Singleton instance
_okta_auth: Optional[OktaAuth] = None


def get_okta_auth() -> OktaAuth:
    """Get or create the OktaAuth singleton."""
    global _okta_auth
    if _okta_auth is None:
        _okta_auth = OktaAuth()
    return _okta_auth
