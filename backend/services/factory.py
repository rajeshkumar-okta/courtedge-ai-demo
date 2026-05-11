"""Build ApprovalService from env vars.

Called from api/main.py on first request (lazy construction).
"""
from __future__ import annotations

import os

from .approval_service import ApprovalService
from .okta_oig_client import OktaOIGClient
from .service_token import mint_service_token


def build_approval_service(store) -> ApprovalService:
    base_url = os.environ["OKTA_OIG_BASE_URL"]
    api_token = os.environ["OKTA_OIG_API_TOKEN"]
    request_type_id = os.environ["OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"]
    threshold = int(os.environ.get("APPROVAL_QUANTITY_THRESHOLD", "500"))
    oig = OktaOIGClient(base_url=base_url, api_token=api_token)
    return ApprovalService(
        oig=oig,
        demo_store=store,
        mint_service_token=mint_service_token,
        request_type_id=request_type_id,
        quantity_threshold=threshold,
    )
