"""Business logic for the OIG approval flow.

Depends on:
- OktaOIGClient   (HTTP)
- A demo_store-like object supporting update_inventory_quantity(sku, qty, op, idempotency_key)
- A service-token minter: callable(scope: str) -> str returning an access token
- A clock:  callable() -> datetime.datetime (UTC)

All external I/O lives in those dependencies; the service itself is pure orchestration.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .intent import (
    Intent,
    decode_intent,
    encode_justification,
    find_comment,
)
from .okta_oig_client import OktaOIGClient, OIGAuthError, OIGUnavailable

logger = logging.getLogger(__name__)

EXECUTED_MARKER = "[EXECUTED:"
FAILED_MARKER = "[EXECUTION_FAILED:"
ABANDONED_MARKER = "[EXECUTION_ABANDONED]"
MAX_EXECUTION_ATTEMPTS = 3


@dataclass
class ExecutionResult:
    txn_id: str
    previous_quantity: int
    new_quantity: int


@dataclass
class ApprovalStatus:
    request_id: str
    status: str  # 'pending' | 'approved' | 'executed' | 'denied'
    intent: Intent | None
    submitted_at: str | None = None
    approved_at: str | None = None
    executed_at: str | None = None
    approver: dict | None = None
    execution_result: ExecutionResult | None = None
    denial_reason: str | None = None
    poll_error: bool = False


class ApprovalService:
    def __init__(
        self,
        *,
        oig: OktaOIGClient,
        demo_store: Any,
        mint_service_token: Callable[[str], Awaitable[str]],
        request_type_id: str,
        quantity_threshold: int = 500,
        clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
    ):
        self._oig = oig
        self._store = demo_store
        self._mint_token = mint_service_token
        self._request_type_id = request_type_id
        self._threshold = quantity_threshold
        self._now = clock
        self._locks: dict[str, asyncio.Lock] = {}

    # ---------- gating ----------

    def should_gate(self, scope: str, parsed_intent: dict | None) -> bool:
        if scope != "inventory:write":
            return False
        if not parsed_intent:
            return False
        qty = parsed_intent.get("quantity_delta")
        return isinstance(qty, int) and qty >= self._threshold

    # ---------- creation ----------

    async def create_request(
        self,
        *,
        user_email: str,
        requester_id: str,
        approver_group_name: str,
        agent: str,
        scope: str,
        parsed_intent: dict,
        original_task: str,
        fga_check_id: str | None = None,
    ) -> tuple[str, Intent]:
        """Create an OIG Access Request and return (request_id, intent).

        Approver group is assigned to the Request Type in Okta Admin; passing
        `approver_group_name` here is only for the human-readable message.
        """
        qty = int(parsed_intent["quantity_delta"])
        product = str(parsed_intent["product_name"])
        intent = Intent(
            user_email=user_email,
            agent=agent,
            scope=scope,
            product_name=product,
            quantity_delta=qty,
            original_task=original_task,
            submitted_at=self._now().isoformat().replace("+00:00", "Z"),
            fga_check_id=fga_check_id,
        )
        subject = f"Inventory write: +{qty} {product}"
        human = (
            f"AI agent requests inventory write on behalf of {user_email}.\n"
            f"Action: Add {qty} units of {product} (scope: {scope}).\n"
            f"Original task: \"{original_task}\".\n"
            f"Assigned approver group: {approver_group_name}."
        )
        justification = encode_justification(human, intent)

        try:
            created = await self._oig.create_request(
                request_type_id=self._request_type_id,
                requester_id=requester_id,
                subject=subject,
                justification=justification,
            )
        except (OIGUnavailable, OIGAuthError) as exc:
            logger.error("OIG create_request failed: %s", exc)
            raise

        request_id = created.get("id") or created.get("requestId")
        if not request_id:
            raise RuntimeError(f"OIG response missing request id: {created!r}")
        return request_id, intent

    # ---------- status ----------

    async def get_status(self, request_id: str) -> ApprovalStatus:
        try:
            raw = await self._oig.get_request(request_id)
        except OIGUnavailable:
            return ApprovalStatus(request_id=request_id, status="pending", intent=None, poll_error=True)

        return self._status_from_raw(request_id, raw)

    def _status_from_raw(self, request_id: str, raw: dict) -> ApprovalStatus:
        justification = raw.get("justification") or ""
        intent = decode_intent(justification)
        comments = raw.get("comments") or []
        executed = find_comment(comments, EXECUTED_MARKER)

        oig_status = (raw.get("status") or "").upper()
        submitted_at = raw.get("createdAt") or raw.get("created")
        approved_at = raw.get("approvedAt")
        approved_by = raw.get("approvedBy") or {}
        approver = None
        if approved_by:
            approver = {
                "email": approved_by.get("email") or approved_by.get("login"),
                "display_name": approved_by.get("displayName"),
            }

        if executed:
            # Parse "[EXECUTED:txn_id] ..." -> extract txn
            text = executed.get("text", "")
            txn_id = text.split(EXECUTED_MARKER, 1)[1].split("]", 1)[0]
            return ApprovalStatus(
                request_id=request_id,
                status="executed",
                intent=intent,
                submitted_at=submitted_at,
                approved_at=approved_at,
                executed_at=executed.get("createdAt"),
                approver=approver,
                execution_result=ExecutionResult(
                    txn_id=txn_id,
                    previous_quantity=-1,   # not recoverable from comment; UI shows whatever the marker knows
                    new_quantity=-1,
                ),
            )

        if oig_status == "DENIED":
            # Denial reason often in a comment or a "statusReason" field
            reason = raw.get("statusReason") or ""
            return ApprovalStatus(
                request_id=request_id,
                status="denied",
                intent=intent,
                submitted_at=submitted_at,
                approved_at=approved_at,
                approver=approver,
                denial_reason=reason,
            )

        if oig_status in ("APPROVED", "COMPLETED"):
            return ApprovalStatus(
                request_id=request_id,
                status="approved",
                intent=intent,
                submitted_at=submitted_at,
                approved_at=approved_at,
                approver=approver,
            )

        # Default: pending
        return ApprovalStatus(
            request_id=request_id,
            status="pending",
            intent=intent,
            submitted_at=submitted_at,
        )
