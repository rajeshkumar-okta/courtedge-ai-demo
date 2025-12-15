"""
Okta Cross-App Access (ID-JAG) Manager

Enables secure token exchange for MCP access using the Okta AI SDK.
Implements the 4-step ID-JAG flow:
1. Exchange ID token for ID-JAG token
2. Verify ID-JAG token (optional, for logging)
3. Exchange ID-JAG for authorization server token
4. Verify authorization server token

Based on Oliver's implementation pattern.
"""

import logging
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import the Okta AI SDK
SDK_AVAILABLE = False
try:
    from okta_ai_sdk import OktaAISDK, OktaAIConfig, AuthServerTokenRequest
    SDK_AVAILABLE = True
    logger.info("Okta AI SDK loaded successfully")
except ImportError as e:
    logger.warning(f"Okta AI SDK not available: {e}. Using fallback demo mode.")


class OktaCrossAppAccessManager:
    """
    Manages ID-JAG token exchange for MCP server access.

    Usage:
        manager = OktaCrossAppAccessManager()
        mcp_token = await manager.exchange_id_to_mcp_token(user_id_token)
    """

    def __init__(self):
        """Initialize the Cross-App Access Manager with SDK configuration"""
        self.okta_domain = os.getenv("OKTA_DOMAIN", "").strip()
        if self.okta_domain and not self.okta_domain.startswith("http"):
            self.okta_domain = f"https://{self.okta_domain}"

        # Get agent credentials
        self.agent_id = os.getenv("OKTA_AI_AGENT_ID", "").strip()
        agent_private_key_str = os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", "")

        # MCP auth server configuration
        self.mcp_auth_server_id = os.getenv("OKTA_MCP_AUTH_SERVER_ID", "").strip()
        self.mcp_audience = os.getenv("OKTA_MCP_AUDIENCE", "api://progear-mcp").strip()

        # Main auth server (for ID-JAG exchange)
        self.main_auth_server_id = os.getenv("OKTA_MAIN_AUTH_SERVER_ID", "default").strip()

        self.sdk_main = None
        self.sdk_mcp = None
        self.main_config = None
        self.mcp_config = None

        if not SDK_AVAILABLE:
            logger.warning("Okta AI SDK not available - running in demo mode")
            return

        if not self.okta_domain or not self.agent_id or not agent_private_key_str:
            logger.warning("Missing Okta configuration - ID-JAG exchange will be disabled")
            return

        try:
            agent_private_key = json.loads(agent_private_key_str) if isinstance(agent_private_key_str, str) else agent_private_key_str

            # STEP 1 Config: ID token → ID-JAG token exchange
            # Uses JWT bearer assertion with agent credentials
            self.main_config = OktaAIConfig(
                oktaDomain=self.okta_domain,
                clientId=self.agent_id,
                clientSecret="",  # Not used with JWT bearer
                authorizationServerId="default",  # POST to /oauth2/v1/token
                principalId=self.agent_id,
                privateJWK=agent_private_key
            )
            logger.info("Main config loaded for ID-JAG exchange (JWT Bearer)")

            # STEP 3 Config: ID-JAG → MCP auth server token exchange
            if self.mcp_auth_server_id:
                self.mcp_config = OktaAIConfig(
                    oktaDomain=self.okta_domain,
                    clientId=self.agent_id,
                    clientSecret="",  # Not used with JWT bearer
                    authorizationServerId=self.mcp_auth_server_id,
                    principalId=self.agent_id,
                    privateJWK=agent_private_key
                )
                logger.info(f"MCP config loaded for auth server: {self.mcp_auth_server_id}")

            # Initialize SDKs
            self.sdk_main = OktaAISDK(self.main_config)
            if self.mcp_config:
                self.sdk_mcp = OktaAISDK(self.mcp_config)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OKTA_AI_AGENT_PRIVATE_KEY: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize Okta AI SDK: {e}")

    @property
    def is_configured(self) -> bool:
        """Check if ID-JAG exchange is properly configured"""
        return self.sdk_main is not None and self.sdk_mcp is not None

    async def exchange_id_to_mcp_token(
        self,
        user_id_token: str,
        scopes: str = "mcp:read mcp:inventory mcp:pricing mcp:customers"
    ) -> Optional[Dict[str, Any]]:
        """
        Exchange user's ID token for MCP access token using ID-JAG.

        4-step process:
        1. ID token → ID-JAG token (org audience)
        2. ID-JAG token verification (optional)
        3. ID-JAG → MCP auth server token
        4. Return token info

        Args:
            user_id_token: User's ID token from Okta
            scopes: Scopes to request for MCP access

        Returns:
            Dict with access_token, expires_in, token_type, or None if failed
        """
        # Demo mode if not configured
        if not self.is_configured:
            logger.info("[ID-JAG Demo] SDK not configured - returning demo token")
            return {
                "access_token": f"demo-mcp-token-{int(datetime.now().timestamp())}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": scopes,
                "demo_mode": True,
                "exchanged_at": datetime.now().isoformat()
            }

        try:
            logger.info("[ID-JAG] Starting 4-step token exchange")

            # STEP 1: Exchange ID token for ID-JAG token
            id_jag_audience = f"{self.okta_domain}/oauth2/{self.mcp_auth_server_id}"
            logger.info(f"[ID-JAG] STEP 1: Exchanging ID token for ID-JAG, audience={id_jag_audience}")

            try:
                id_jag_result = self.sdk_main.cross_app_access.exchange_id_token(
                    id_token=user_id_token,
                    audience=id_jag_audience,
                    scope=scopes
                )
                logger.info(f"[ID-JAG] STEP 1 SUCCESS: expires_in={id_jag_result.expires_in}s")
            except Exception as e:
                logger.error(f"[ID-JAG] STEP 1 FAILED: {e}")
                return None

            # STEP 2: Verify ID-JAG token (optional, for audit)
            verification_sub = None
            try:
                verification_result = self.sdk_main.cross_app_access.verify_id_jag_token(
                    token=id_jag_result.access_token,
                    audience=id_jag_audience
                )
                if verification_result.valid:
                    verification_sub = verification_result.sub
                    logger.info(f"[ID-JAG] STEP 2 SUCCESS: verified sub={verification_sub}")
            except Exception as e:
                logger.debug(f"[ID-JAG] STEP 2 verification skipped: {e}")

            # STEP 3: Exchange ID-JAG for MCP auth server token
            logger.info(f"[ID-JAG] STEP 3: Exchanging ID-JAG for MCP token")

            try:
                auth_server_request = AuthServerTokenRequest(
                    id_jag_token=id_jag_result.access_token,
                    authorization_server_id=self.mcp_auth_server_id,
                    principal_id=self.mcp_config.principal_id,
                    private_jwk=self.mcp_config.private_jwk
                )

                mcp_token_result = self.sdk_mcp.cross_app_access.exchange_id_jag_for_auth_server_token(
                    auth_server_request
                )
                logger.info(f"[ID-JAG] STEP 3 SUCCESS: MCP token expires_in={mcp_token_result.expires_in}s")
            except Exception as e:
                logger.error(f"[ID-JAG] STEP 3 FAILED: {e}")
                return None

            # Return token info
            return {
                "access_token": mcp_token_result.access_token,
                "id_jag_token": id_jag_result.access_token,
                "token_type": getattr(mcp_token_result, "token_type", "Bearer"),
                "expires_in": mcp_token_result.expires_in,
                "scope": getattr(mcp_token_result, "scope", scopes),
                "subject": verification_sub,
                "demo_mode": False,
                "exchanged_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[ID-JAG] Exchange failed: {e}")
            return None

    async def verify_mcp_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Verify MCP authorization server token"""
        if not self.is_configured:
            return {"valid": True, "demo_mode": True}

        try:
            verification_result = self.sdk_mcp.cross_app_access.verify_auth_server_token(
                token=access_token,
                authorization_server_id=self.mcp_auth_server_id,
                audience=self.mcp_audience
            )

            if verification_result.valid:
                return {
                    "valid": True,
                    "sub": verification_result.sub,
                    "aud": verification_result.aud,
                    "scope": verification_result.scope
                }
            return None
        except Exception as e:
            logger.error(f"[ID-JAG] Token verification failed: {e}")
            return None


# Singleton instance
_cross_app_manager: Optional[OktaCrossAppAccessManager] = None


def get_cross_app_manager() -> OktaCrossAppAccessManager:
    """Get or create the OktaCrossAppAccessManager singleton"""
    global _cross_app_manager
    if _cross_app_manager is None:
        _cross_app_manager = OktaCrossAppAccessManager()
    return _cross_app_manager
