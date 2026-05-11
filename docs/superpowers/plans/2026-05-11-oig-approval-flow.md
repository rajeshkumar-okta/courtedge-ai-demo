# OIG Approval Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert an Okta OIG Access Request approval gate between the existing FGA check and `inventory:write` execution. When `quantity_delta >= APPROVAL_QUANTITY_THRESHOLD` (default 500), the orchestrator creates an OIG Access Request assigned to a pre-configured Okta group and returns a `pending_approval` payload. Hybrid polling (5s foreground + 60s background) resolves it whenever approval lands, with execution using a service token minted from the AI agent's JWT assertion. OIG is the sole persistence layer.

**Architecture:** New LangGraph node `approval_gate` between `fga_check` and `process_agents`. Two new backend services (`OktaOIGClient`, `ApprovalService`). Two new API endpoints plus a FastAPI startup poller. One new React component (`ApprovalStatusCard`) slotted into the existing right panel. `demo_store.update_inventory_quantity` gains an `idempotency_key` parameter. No new database.

**Tech Stack:** Python 3.11 / FastAPI / LangGraph / `httpx` (async HTTP client, add to `requirements.txt` if absent), raw Anthropic SDK (already used, not relevant here), Next.js 14 / React 18, existing NextAuth/Okta setup.

**Important project conventions (from `CLAUDE.md`):**
- Backend has no test suite and no linter. Do NOT introduce pytest for this work. Each task instead has a concrete smoke-verification step (curl, log check, browser, or a one-off `python -c` probe).
- Use the **raw Anthropic SDK** where LLM calls are involved — not applicable here, but stated for context.
- Preserve the shape of `agent_flow`, `token_exchanges`, and `fga_checks` in responses; these are load-bearing demo surface.
- `.env` at repo root is shared by backend + frontend. Modify `.env.example` for any new keys; remind the user to mirror the values to their `.env` and Render env vars.

**File map:**

| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/services/__init__.py` | Mark package. |
| Create | `backend/services/intent.py` | `Intent` pydantic model + `[INTENT_JSON]` encode/decode helpers. |
| Create | `backend/services/okta_oig_client.py` | Thin async HTTP wrapper over Okta OIG Access Requests API. |
| Create | `backend/services/approval_service.py` | Business logic: `should_gate`, `create_request`, `get_status`, `execute_if_approved`. |
| Modify | `backend/data/demo_store.py` | Add `idempotency_key` param to `update_inventory_quantity`. |
| Modify | `backend/orchestrator/orchestrator.py` | Add `approval_gate` node + wire into graph; extract quantity parser into a shared helper used by both the gate and `inventory_agent`. |
| Modify | `backend/api/main.py` | New endpoints `GET /api/approvals/{id}` and `GET /api/approvals`; startup background poller; `ChatResponse.pending_approval` field. |
| Modify | `backend/agents/inventory_agent.py` | Replace inline quantity regex with the shared helper. |
| Modify | `backend/requirements.txt` | Ensure `httpx` is listed (may already be transitively present via openfga-sdk). |
| Modify | `.env.example` | Add 6 new env vars documented in spec §9. |
| Create | `packages/progear-sales-agent/src/components/ApprovalStatusCard.tsx` | Collapsible card; polls `/api/approvals/{id}` while state is pending/approved. |
| Modify | `packages/progear-sales-agent/src/app/page.tsx` | Slot card between `FGAExplanationCard` and Learn More; track `pendingApproval` state with `sessionStorage`; accept `?mockApprovalId=` debug param. |
| Create | `docs/OIG_APPROVAL_SETUP.md` | Step-by-step Okta Admin setup (group, request type, API token, IDs to copy into `.env`). |
| Create | `docs/OIG_APPROVAL_TEST_SCENARIOS.md` | The 8 manual test scenarios from spec §7. |

---

## Pre-flight

Before Task 1, the engineer MUST have these Okta resources ready (see §8 of the spec and `docs/OIG_APPROVAL_SETUP.md` which will be authored in Task 18). Task 18 can be written first if you prefer; it is listed late only because it is doc-only.

Required before you can verify anything end-to-end:
- Okta group created (e.g. `InventoryApprovers`) with at least one member who is NOT the demo user.
- Okta OIG Request Type created (e.g. `AI Agent Inventory Write Approval`) with the approver group assigned.
- Okta admin API token with OIG permissions.
- Values captured for: `OKTA_OIG_BASE_URL`, `OKTA_OIG_API_TOKEN`, `OKTA_OIG_INVENTORY_REQUEST_TYPE_ID`, `OKTA_APPROVER_GROUP_ID`.

Local-only tasks (1–9) can be implemented and smoke-verified without Okta. Tasks 10+ require the Okta resources above.

---

## Task 1: Add env-var scaffolding

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Append new env-var block to `.env.example`**

Append the following to the end of `.env.example`:

```
# --- OIG Approval Flow (spec: docs/superpowers/specs/2026-05-11-oig-approval-flow-design.md) ---
OKTA_OIG_BASE_URL=https://your-tenant.oktapreview.com
OKTA_OIG_API_TOKEN=<Okta admin API token with OIG permissions>
OKTA_OIG_INVENTORY_REQUEST_TYPE_ID=<request type id created in Okta Admin>
OKTA_APPROVER_GROUP_ID=<Okta group id for approvers>
OKTA_APPROVER_GROUP_NAME=InventoryApprovers
APPROVAL_QUANTITY_THRESHOLD=500
APPROVAL_POLL_INTERVAL_SECONDS=60
NEXT_PUBLIC_ENABLE_DEBUG_HOOKS=false
```

- [ ] **Step 2: Copy the same block into your local `.env` with real values**

Edit your repo-root `.env` manually. DO NOT commit real values. Placeholder real values are fine for now if the Okta resources aren't ready yet; anything requiring them fails loudly later.

- [ ] **Step 3: Verify dotenv loads the new keys**

Run from the repo root with the venv active:

```
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print({k: bool(os.getenv(k)) for k in ['OKTA_OIG_BASE_URL','OKTA_OIG_API_TOKEN','OKTA_OIG_INVENTORY_REQUEST_TYPE_ID','OKTA_APPROVER_GROUP_ID','APPROVAL_QUANTITY_THRESHOLD','APPROVAL_POLL_INTERVAL_SECONDS']})"
```

Expected output: each key prints `True` if it's set in `.env`, `False` otherwise. Any `False` for a value you intended to set is a typo.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "Add env vars for OIG approval flow"
```

---

## Task 2: Create `backend/services/` package and `OktaOIGClient`

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/okta_oig_client.py`

- [ ] **Step 1: Create the package marker**

Create `backend/services/__init__.py` with a single line:

```python
"""Service-layer modules for approval workflow and external integrations."""
```

- [ ] **Step 2: Write `OktaOIGClient`**

Create `backend/services/okta_oig_client.py`:

```python
"""Async HTTP wrapper around Okta OIG Access Requests API.

Endpoints used (verify against current Okta docs at
https://developer.okta.com/docs/reference/api/governance/ before
going to production):

- POST   /governance/api/v1/requests
- GET    /governance/api/v1/requests/{id}
- GET    /governance/api/v1/requests?requestTypeId=...&status=...
- POST   /governance/api/v1/requests/{id}/comments
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OIGAuthError(RuntimeError):
    """Raised when Okta returns 401 — API token expired/invalid."""


class OIGUnavailable(RuntimeError):
    """Raised when Okta returns 5xx or times out."""


class OktaOIGClient:
    def __init__(self, base_url: str, api_token: str, http: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._http = http or httpx.AsyncClient(timeout=10.0)
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"SSWS {self._api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base_url}/governance/api/v1{path}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = self._url(path)
        try:
            resp = await self._http.request(method, url, headers=self._headers(), **kwargs)
        except httpx.RequestError as exc:
            logger.warning("OIG transport error on %s %s: %s", method, url, exc)
            raise OIGUnavailable(f"OIG unreachable: {exc}") from exc

        if resp.status_code == 401:
            raise OIGAuthError(f"OIG auth failed on {method} {url}")
        if resp.status_code >= 500:
            raise OIGUnavailable(f"OIG {resp.status_code} on {method} {url}")
        if resp.status_code >= 400:
            # 4xx other than 401: surface as ValueError with body for caller visibility
            raise ValueError(f"OIG {resp.status_code} on {method} {url}: {resp.text}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def create_request(
        self,
        *,
        request_type_id: str,
        requester_id: str,
        subject: str,
        justification: str,
    ) -> dict[str, Any]:
        payload = {
            "requestTypeId": request_type_id,
            "requesterId": requester_id,
            "subject": subject,
            "justification": justification,
        }
        return await self._request("POST", "/requests", json=payload)

    async def get_request(self, request_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/requests/{request_id}")

    async def list_requests(
        self, *, request_type_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"requestTypeId": request_type_id}
        if status:
            params["status"] = status
        data = await self._request("GET", "/requests", params=params)
        # Okta list endpoints typically return {"items": [...]} or a bare list
        if isinstance(data, list):
            return data
        return data.get("items", []) or data.get("requests", [])

    async def add_comment(self, request_id: str, text: str) -> None:
        await self._request("POST", f"/requests/{request_id}/comments", json={"text": text})
```

- [ ] **Step 3: Confirm `httpx` is available; add to `requirements.txt` if not**

```
python -c "import httpx; print(httpx.__version__)"
```

If this prints a version, you're done. If it raises `ModuleNotFoundError`, add `httpx>=0.27` to `backend/requirements.txt` and `pip install httpx` in the active venv, then rerun. (`openfga-sdk` usually brings it in transitively, so most environments will already have it.)

- [ ] **Step 4: Smoke-verify the module imports cleanly**

From repo root with venv active:

```
python -c "from backend.services.okta_oig_client import OktaOIGClient, OIGAuthError, OIGUnavailable; print('ok')"
```

Expected output: `ok`. Any ImportError means a typo or path issue — fix before continuing.

- [ ] **Step 5: Commit**

```bash
git add backend/services/__init__.py backend/services/okta_oig_client.py backend/requirements.txt
git commit -m "Add OktaOIGClient async wrapper"
```

---

## Task 3: Add `Intent` model + `[INTENT_JSON]` fence helpers

**Files:**
- Create: `backend/services/intent.py`

- [ ] **Step 1: Write `intent.py`**

Create `backend/services/intent.py`:

```python
"""Shape of the intent payload encoded in OIG request justification."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

INTENT_FENCE_START = "[INTENT_JSON]"
INTENT_FENCE_END = "[/INTENT_JSON]"
_INTENT_FENCE_RE = re.compile(
    re.escape(INTENT_FENCE_START) + r"\s*(\{.*?\})\s*" + re.escape(INTENT_FENCE_END),
    re.DOTALL,
)


@dataclass
class Intent:
    user_email: str
    agent: str            # e.g. "inventory"
    scope: str            # e.g. "inventory:write"
    product_name: str
    quantity_delta: int
    original_task: str
    submitted_at: str     # ISO8601
    fga_check_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "Intent":
        data = json.loads(raw)
        return cls(**data)


def encode_justification(human_text: str, intent: Intent) -> str:
    """Return a justification string with human text plus a fenced JSON block."""
    return f"{human_text}\n\n{INTENT_FENCE_START}\n{intent.to_json()}\n{INTENT_FENCE_END}"


def decode_intent(justification: str) -> Intent | None:
    """Extract the Intent from a justification that was built with encode_justification."""
    match = _INTENT_FENCE_RE.search(justification or "")
    if not match:
        return None
    return Intent.from_json(match.group(1))


def find_comment(comments: list[dict[str, Any]], prefix: str) -> dict[str, Any] | None:
    """Return the first comment whose text starts with prefix, or None."""
    for c in comments or []:
        if (c.get("text") or "").startswith(prefix):
            return c
    return None
```

- [ ] **Step 2: Smoke-verify round-trip**

```
python -c "
from backend.services.intent import Intent, encode_justification, decode_intent
i = Intent(user_email='bob@atko.email', agent='inventory', scope='inventory:write',
           product_name='basketball', quantity_delta=500, original_task='add 500 basketballs',
           submitted_at='2026-05-11T14:22:03Z', fga_check_id='fga_abc')
j = encode_justification('AI agent on behalf of bob', i)
assert decode_intent(j).product_name == 'basketball', 'round-trip failed'
assert decode_intent('no fence here') is None
print('ok')
"
```

Expected output: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/intent.py
git commit -m "Add Intent dataclass and INTENT_JSON fence helpers"
```

---

## Task 4: Add `demo_store` idempotency key

**Files:**
- Modify: `backend/data/demo_store.py:141-180` (the `update_inventory_quantity` method)

- [ ] **Step 1: Add the signature change and short-circuit**

Replace the `update_inventory_quantity` method (around lines 141–180 of `backend/data/demo_store.py`) with:

```python
    def update_inventory_quantity(
        self,
        sku: str,
        quantity_change: int,
        operation: str = "set",
        idempotency_key: str | None = None,
    ) -> Dict[str, Any]:
        """
        Update inventory quantity.

        Args:
            sku: Product SKU
            quantity_change: Amount to change (or absolute value for 'set')
            operation: 'increase', 'decrease', or 'set'
            idempotency_key: optional key; if the same key was already used, the
                stored result is returned and inventory is NOT modified again.

        Returns:
            Updated item info with previous and new quantities
        """
        if idempotency_key is not None:
            # Lazy-init the cache the first time we see a key.
            cache = getattr(self, "_idempotency_cache", None)
            if cache is None:
                self._idempotency_cache = {}
                cache = self._idempotency_cache
            if idempotency_key in cache:
                return cache[idempotency_key]

        inventory = self._data.get("inventory", {})
        if sku not in inventory:
            # Try to find by name
            item = self.get_inventory_by_name(sku)
            if item:
                sku = item.get("sku")
            else:
                result = {"error": f"Product not found: {sku}"}
                if idempotency_key is not None:
                    self._idempotency_cache[idempotency_key] = result
                return result

        item = inventory[sku]
        previous_qty = item["quantity"]

        if operation == "increase":
            item["quantity"] = previous_qty + quantity_change
        elif operation == "decrease":
            item["quantity"] = max(0, previous_qty - quantity_change)
        elif operation == "set":
            item["quantity"] = quantity_change
        else:
            result = {"error": f"Unknown operation: {operation}"}
            if idempotency_key is not None:
                self._idempotency_cache[idempotency_key] = result
            return result

        # Update status based on quantity vs reorder point
        reorder_point = item.get("reorder_point", 100)
        if item["quantity"] <= reorder_point:
            item["status"] = "low"
        else:
            item["status"] = "good"
```

DO NOT remove anything below line 180 — this method continues past there in the current file. Only replace the signature + idempotency lookup + the existing body up to the status assignment. Re-read the full current method first if uncertain, and diff before saving to confirm the trailing return statement is preserved.

- [ ] **Step 2: Add idempotency caching at the return point**

Still in `update_inventory_quantity`, find the `return` statement at the very end of the method (whatever dict is returned on success) and wrap it so the idempotency cache stores the result:

```python
        result = {
            # ...existing keys exactly as they were (previous_quantity, new_quantity, etc.)...
        }
        if idempotency_key is not None:
            self._idempotency_cache[idempotency_key] = result
        return result
```

Re-read the file after editing to confirm:
- `self._idempotency_cache` is written on every success path AND every error path (item not found, unknown operation).
- The return shape for the success case is unchanged.

- [ ] **Step 3: Smoke-verify idempotency**

```
python -c "
import os
os.chdir('backend')
from data.demo_store import DemoStore
s = DemoStore()
r1 = s.update_inventory_quantity('basketball', 10, 'increase', idempotency_key='K1')
r2 = s.update_inventory_quantity('basketball', 10, 'increase', idempotency_key='K1')
assert r1 == r2, 'second call returned different result'
# third call with no key SHOULD mutate
r3 = s.update_inventory_quantity('basketball', 10, 'increase')
assert r3['new_quantity'] != r1['new_quantity'], 'third call without key should have mutated'
print('ok')
"
```

Expected: `ok`. If `basketball` isn't a valid SKU in your demo data, swap for any SKU from `backend/data/demo_store.py`'s inventory dict.

- [ ] **Step 4: Commit**

```bash
git add backend/data/demo_store.py
git commit -m "Add idempotency_key to DemoStore.update_inventory_quantity"
```

---

## Task 5: Extract shared quantity-parsing helper

**Files:**
- Modify: `backend/agents/inventory_agent.py:98-100`
- Create: `backend/services/intent.py` (append — same file as Task 3)

- [ ] **Step 1: Add `parse_inventory_intent` helper to `backend/services/intent.py`**

Append to the bottom of `backend/services/intent.py`:

```python
_QTY_RE = re.compile(r"(\d+)")
_PRODUCT_KEYWORDS = (
    "basketball", "treadmill", "helmet", "glove", "shoe", "jersey",
    "ball", "racket", "bat",
)


def parse_inventory_intent(task: str) -> dict | None:
    """Parse quantity + product from a natural-language inventory task.

    Returns None if quantity can't be determined. `product_name` defaults
    to "basketball" when no keyword matches, matching current inventory
    agent behavior — callers that care should check the returned product.
    """
    if not task:
        return None
    m = _QTY_RE.search(task)
    if not m:
        return None
    try:
        quantity = int(m.group(1))
    except ValueError:
        return None
    task_lower = task.lower()
    product = next((p for p in _PRODUCT_KEYWORDS if p in task_lower), "basketball")
    return {"quantity_delta": quantity, "product_name": product}
```

- [ ] **Step 2: Use it in `inventory_agent.py`**

Open `backend/agents/inventory_agent.py` and find the block near line 98 that parses quantity via regex. Replace the regex-based parsing with a call to the new helper:

```python
from backend.services.intent import parse_inventory_intent

# ...inside the method that currently parses quantity...
parsed = parse_inventory_intent(task)
quantity = parsed["quantity_delta"] if parsed else 30
```

Remove the now-dead `qty_match = re.search(...)` / `int(qty_match.group(1))` lines. If the agent also hardcodes `product = demo_store.get_inventory_by_name("basketball")`, change it to use `parsed["product_name"]` when `parsed` is not None:

```python
product_name = parsed["product_name"] if parsed else "basketball"
product = demo_store.get_inventory_by_name(product_name)
```

- [ ] **Step 3: Smoke-verify parser and that the agent still imports**

```
python -c "
from backend.services.intent import parse_inventory_intent
assert parse_inventory_intent('add 500 basketballs')['quantity_delta'] == 500
assert parse_inventory_intent('add 500 basketballs')['product_name'] == 'basketball'
assert parse_inventory_intent('hello') is None
print('parse ok')
from backend.agents.inventory_agent import InventoryAgent
print('agent import ok')
"
```

Expected: `parse ok` then `agent import ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/services/intent.py backend/agents/inventory_agent.py
git commit -m "Extract inventory quantity/product parser into shared helper"
```

---

## Task 6: `ApprovalService` — skeleton + `should_gate`

**Files:**
- Create: `backend/services/approval_service.py`

- [ ] **Step 1: Write the skeleton with `should_gate`**

Create `backend/services/approval_service.py`:

```python
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
```

- [ ] **Step 2: Smoke-verify `should_gate`**

```
python -c "
import asyncio
from backend.services.approval_service import ApprovalService
class _StubOIG: pass
async def _mint(scope): return 'tok'
svc = ApprovalService(oig=_StubOIG(), demo_store=None, mint_service_token=_mint,
                      request_type_id='rt', quantity_threshold=500)
assert svc.should_gate('inventory:write', {'quantity_delta': 500}) is True
assert svc.should_gate('inventory:write', {'quantity_delta': 499}) is False
assert svc.should_gate('inventory:read',  {'quantity_delta': 500}) is False
assert svc.should_gate('inventory:write', None) is False
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/approval_service.py
git commit -m "Add ApprovalService skeleton with should_gate"
```

---

## Task 7: `ApprovalService.create_request`

**Files:**
- Modify: `backend/services/approval_service.py`

- [ ] **Step 1: Append `create_request`**

Append the following method inside the `ApprovalService` class (after `should_gate`):

```python
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
```

- [ ] **Step 2: Smoke-verify with a stub OIG client**

```
python -c "
import asyncio
from backend.services.approval_service import ApprovalService

class StubOIG:
    async def create_request(self, **kwargs):
        self.last = kwargs
        return {'id': 'req_fake_1'}

async def main():
    svc = ApprovalService(oig=StubOIG(), demo_store=None, mint_service_token=lambda s: 'x',
                          request_type_id='rt', quantity_threshold=500)
    rid, intent = await svc.create_request(
        user_email='bob@atko.email', requester_id='00uABC',
        approver_group_name='InventoryApprovers', agent='inventory',
        scope='inventory:write',
        parsed_intent={'quantity_delta': 500, 'product_name': 'basketball'},
        original_task='add 500 basketballs')
    assert rid == 'req_fake_1'
    assert intent.quantity_delta == 500
    assert 'InventoryApprovers' in svc._oig.last['justification']
    assert '[INTENT_JSON]' in svc._oig.last['justification']
    print('ok')

asyncio.run(main())
"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/approval_service.py
git commit -m "Add ApprovalService.create_request"
```

---

## Task 8: `ApprovalService.get_status`

**Files:**
- Modify: `backend/services/approval_service.py`

- [ ] **Step 1: Append `get_status` + helpers**

Append inside `ApprovalService`:

```python
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
```

- [ ] **Step 2: Smoke-verify `_status_from_raw` branches**

```
python -c "
from backend.services.approval_service import ApprovalService
from backend.services.intent import Intent, encode_justification

i = Intent('u','inventory','inventory:write','basketball',500,'add 500','2026-05-11T00:00Z', None)
just = encode_justification('x', i)

svc = ApprovalService.__new__(ApprovalService)  # bypass __init__ for pure helper test
svc._threshold = 500

pending = svc._status_from_raw('r1', {'status': 'PENDING', 'justification': just})
assert pending.status == 'pending'
denied  = svc._status_from_raw('r2', {'status': 'DENIED', 'justification': just, 'statusReason': 'nope'})
assert denied.status == 'denied' and denied.denial_reason == 'nope'
approved = svc._status_from_raw('r3', {'status': 'APPROVED', 'justification': just})
assert approved.status == 'approved'
executed = svc._status_from_raw('r4', {
    'status': 'APPROVED', 'justification': just,
    'comments': [{'text': '[EXECUTED:txn_abc] done'}]})
assert executed.status == 'executed' and executed.execution_result.txn_id == 'txn_abc'
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/approval_service.py
git commit -m "Add ApprovalService.get_status with status classification"
```

---

## Task 9: `ApprovalService.execute_if_approved`

**Files:**
- Modify: `backend/services/approval_service.py`

- [ ] **Step 1: Append `execute_if_approved` and helpers**

Append inside `ApprovalService`:

```python
    # ---------- execution ----------

    def _lock_for(self, request_id: str) -> asyncio.Lock:
        lock = self._locks.get(request_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[request_id] = lock
        return lock

    def _count_failed_attempts(self, comments: list[dict]) -> int:
        return sum(1 for c in comments if (c.get("text") or "").startswith(FAILED_MARKER))

    async def execute_if_approved(self, request_id: str) -> ApprovalStatus:
        lock = self._lock_for(request_id)
        async with lock:
            raw = await self._oig.get_request(request_id)
            status = self._status_from_raw(request_id, raw)
            if status.status != "approved":
                return status

            # Check abandoned
            if find_comment(raw.get("comments") or [], ABANDONED_MARKER):
                status.denial_reason = "execution abandoned after repeated failures"
                return status

            intent = status.intent
            if intent is None:
                msg = "intent could not be decoded from justification"
                logger.error("%s: %s", request_id, msg)
                await self._oig.add_comment(request_id, f"{FAILED_MARKER}attempt=?:reason={msg}]")
                status.denial_reason = msg
                return status

            attempts_so_far = self._count_failed_attempts(raw.get("comments") or [])
            if attempts_so_far >= MAX_EXECUTION_ATTEMPTS:
                await self._oig.add_comment(request_id, ABANDONED_MARKER)
                status.denial_reason = "execution abandoned after repeated failures"
                return status

            # Attempt execution
            attempt_num = attempts_so_far + 1
            try:
                # Mint a service token for visibility/audit even though DemoStore
                # is local — mirrors the production flow.
                _token = await self._mint_token(intent.scope)
                result = self._store.update_inventory_quantity(
                    sku=intent.product_name,
                    quantity_change=intent.quantity_delta,
                    operation="increase",
                    idempotency_key=request_id,
                )
                if "error" in result:
                    raise RuntimeError(result["error"])
            except Exception as exc:  # noqa: BLE001 — we want to persist any failure as a comment
                logger.warning("execute_if_approved attempt %d failed for %s: %s",
                               attempt_num, request_id, exc)
                await self._oig.add_comment(
                    request_id, f"{FAILED_MARKER}attempt={attempt_num}:reason={exc}]"
                )
                status.denial_reason = None  # still approved; execution pending retry
                return status

            txn_id = f"inv_txn_{request_id[-8:]}_{attempt_num}"
            executed_at = self._now().isoformat().replace("+00:00", "Z")
            await self._oig.add_comment(
                request_id,
                f"{EXECUTED_MARKER}{txn_id}] completed at {executed_at}",
            )
            status.status = "executed"
            status.executed_at = executed_at
            status.execution_result = ExecutionResult(
                txn_id=txn_id,
                previous_quantity=result.get("previous_quantity", -1),
                new_quantity=result.get("new_quantity", -1),
            )
            return status
```

- [ ] **Step 2: Smoke-verify execute + idempotency with stubs**

```
python -c "
import asyncio
from backend.services.approval_service import ApprovalService
from backend.services.intent import Intent, encode_justification

class StubOIG:
    def __init__(self, raw):
        self.raw = raw
        self.added = []
    async def get_request(self, rid): return self.raw
    async def add_comment(self, rid, text):
        self.added.append(text)
        self.raw.setdefault('comments', []).append({'text': text})

class StubStore:
    def __init__(self):
        self.calls = []
    def update_inventory_quantity(self, sku, quantity_change, operation, idempotency_key=None):
        self.calls.append((sku, quantity_change, operation, idempotency_key))
        return {'previous_quantity': 1000, 'new_quantity': 1500}

async def main():
    i = Intent('u','inventory','inventory:write','basketball',500,'t','2026-05-11T00:00Z', None)
    raw = {'id':'r1','status':'APPROVED','justification': encode_justification('x', i)}
    oig = StubOIG(raw)
    store = StubStore()
    svc = ApprovalService(oig=oig, demo_store=store, mint_service_token=lambda s: _t(),
                          request_type_id='rt', quantity_threshold=500)
    st = await svc.execute_if_approved('r1')
    assert st.status == 'executed', st.status
    assert any('[EXECUTED:' in c for c in oig.added), oig.added
    # second call must be idempotent
    st2 = await svc.execute_if_approved('r1')
    assert st2.status == 'executed'
    assert len(store.calls) == 1, 'store should only be called once'
    print('ok')

async def _t(): return 'tok'
asyncio.run(main())
"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/approval_service.py
git commit -m "Add ApprovalService.execute_if_approved with idempotent resolution"
```

---

## Task 10: Service-token minter + `ApprovalService` factory wiring

**Files:**
- Modify: `backend/auth/multi_agent_auth.py` (add a helper if not already present)
- Create: `backend/services/factory.py`

- [ ] **Step 1: Identify the existing JWT-assertion helper**

Open `backend/auth/multi_agent_auth.py`. Find the function or method that currently builds a JWT assertion from `OKTA_AI_AGENT_PRIVATE_KEY`. It is likely named `_build_assertion` or similar and is used inside the token-exchange flow. Note its exact name for Step 2.

- [ ] **Step 2: Add a `mint_service_token(scope)` async helper**

At the bottom of `backend/auth/multi_agent_auth.py`, add:

```python
import httpx as _httpx  # type: ignore  # may already be imported above — deduplicate if so


async def mint_service_token(scope: str) -> str:
    """Mint an access token for the given scope using the AI agent's JWT assertion.

    This is the 'service identity' used when the resolver executes an inventory
    write after OIG approval — the original user token is long gone, so we present
    the agent's own credentials.
    """
    assertion = _build_assertion()  # reuse the existing helper; rename if yours differs
    token_url = os.getenv("OKTA_INVENTORY_TOKEN_URL") or os.getenv("OKTA_MCP_TOKEN_URL")
    if not token_url:
        raise RuntimeError("OKTA_INVENTORY_TOKEN_URL (or OKTA_MCP_TOKEN_URL) not configured")
    client_id = os.getenv("OKTA_AI_AGENT_CLIENT_ID")
    if not client_id:
        raise RuntimeError("OKTA_AI_AGENT_CLIENT_ID not configured")
    data = {
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": assertion,
        "scope": scope,
    }
    async with _httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(token_url, data=data)
        resp.raise_for_status()
        return resp.json()["access_token"]
```

If `_build_assertion` has a different name in your file, replace the call accordingly. If the existing helper is synchronous, the above works unchanged (JWT signing is CPU-bound but quick).

If your Okta tenant is not configured to allow `client_credentials` on the AI agent app, you can substitute an alternative minter that returns a placeholder string `"service-token-placeholder"` — `ApprovalService.execute_if_approved` doesn't validate the token; it only passes it through for audit. Adjust only as needed for the demo.

- [ ] **Step 3: Write the factory**

Create `backend/services/factory.py`:

```python
"""Construct ApprovalService from env vars. Called from api/main.py."""
from __future__ import annotations

import os

from backend.auth.multi_agent_auth import mint_service_token
from backend.data.demo_store import DemoStore
from backend.services.approval_service import ApprovalService
from backend.services.okta_oig_client import OktaOIGClient


def build_approval_service(store: DemoStore) -> ApprovalService:
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
```

- [ ] **Step 4: Smoke-verify factory builds without network**

With all env vars set in `.env`:

```
python -c "
from dotenv import load_dotenv; load_dotenv()
from backend.data.demo_store import DemoStore
from backend.services.factory import build_approval_service
svc = build_approval_service(DemoStore())
print('service built:', type(svc).__name__, 'threshold=', svc._threshold)
"
```

Expected output: `service built: ApprovalService threshold= 500` (or your configured threshold).

- [ ] **Step 5: Commit**

```bash
git add backend/auth/multi_agent_auth.py backend/services/factory.py
git commit -m "Add service-token minter and ApprovalService factory"
```

---

## Task 11: Orchestrator — add `approval_gate` node

**Files:**
- Modify: `backend/orchestrator/orchestrator.py`

- [ ] **Step 1: Add state fields to `WorkflowState`**

In `backend/orchestrator/orchestrator.py`, locate the `WorkflowState` TypedDict around line 41. Add two optional fields at the end:

```python
class WorkflowState(TypedDict, total=False):
    # ... existing fields unchanged ...
    pending_approval: Optional[Dict[str, Any]]
    parsed_intent: Optional[Dict[str, Any]]
```

If `WorkflowState` is declared as `TypedDict` without `total=False`, keep the existing keys required and add the two new ones under a second `class _OptionalState(TypedDict, total=False): ...` and combine. Simpler: if all existing keys happen to be always set in the current code, just add `total=False` to the single TypedDict — confirm by scanning the file for any read that would KeyError without the keys being set.

- [ ] **Step 2: Add the node method**

Add this method on the `Orchestrator` class (near the other `_..._node` methods):

```python
    async def _approval_gate_node(self, state: WorkflowState) -> WorkflowState:
        """Insert an OIG Access Request gate for high-quantity inventory writes."""
        from backend.services.intent import parse_inventory_intent  # local import to avoid cycles

        agent_scopes = state.get("agent_scopes", {})
        inv_scopes = agent_scopes.get(AGENT_INVENTORY, [])
        if "inventory:write" not in inv_scopes:
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": "No high-risk inventory write detected; skipping approval",
                "status": "skipped",
            })
            return state

        parsed = parse_inventory_intent(state["message"])
        state["parsed_intent"] = parsed

        if not self._approval_service.should_gate("inventory:write", parsed):
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": f"Quantity {parsed.get('quantity_delta') if parsed else '?'} below threshold; no approval needed",
                "status": "skipped",
            })
            return state

        approver_group = os.getenv("OKTA_APPROVER_GROUP_NAME", "InventoryApprovers")
        try:
            request_id, intent = await self._approval_service.create_request(
                user_email=self._user_info.get("email") or "",
                requester_id=self._user_info.get("sub") or self._user_info.get("id") or "",
                approver_group_name=approver_group,
                agent=AGENT_INVENTORY,
                scope="inventory:write",
                parsed_intent=parsed,
                original_task=state["message"],
                fga_check_id=state.get("fga_checks", [{}])[-1].get("id") if state.get("fga_checks") else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("approval_gate create_request failed: %s", exc)
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": f"Approval service error: {exc}",
                "status": "error",
            })
            # Surface as pending_approval None; caller's generate_response will emit error text
            state["pending_approval"] = None
            # Short-circuit to generate_response without executing anything dangerous
            state["agent_results"] = {}
            return state

        state["agent_flow"].append({
            "step": "approval_gate",
            "action": f"Queued OIG Access Request {request_id} for {approver_group}",
            "status": "pending",
        })
        state["pending_approval"] = {
            "request_id": request_id,
            "status": "pending",
            "approver_group": approver_group,
            "submitted_at": intent.submitted_at,
            "intent": {
                "product_name": intent.product_name,
                "quantity_delta": intent.quantity_delta,
                "scope": intent.scope,
                "original_task": intent.original_task,
            },
        }
        # Clear any per-agent scheduling so process_agents would be a no-op anyway
        return state
```

- [ ] **Step 3: Wire the node into the graph**

In `_build_workflow` (around line 177), add the new node and adjust the edges. Before:

```python
workflow.add_node("router", self._router_node)
workflow.add_node("exchange_tokens", self._exchange_tokens_node)
workflow.add_node("fga_check", self._fga_check_node)
workflow.add_node("process_agents", self._process_agents_node)
workflow.add_node("generate_response", self._generate_response_node)
# ... existing add_edge calls ...
```

Add after `add_node("fga_check", ...)`:

```python
workflow.add_node("approval_gate", self._approval_gate_node)
```

Then replace the edge `fga_check -> process_agents` (if present as an unconditional edge) with a conditional that routes through `approval_gate`:

```python
workflow.add_edge("fga_check", "approval_gate")

def _route_after_approval(state: WorkflowState) -> str:
    if state.get("pending_approval") is not None:
        return "generate_response"
    # explicit None set on error path also routes straight to response
    if "pending_approval" in state and state["pending_approval"] is None and state.get("agent_flow", [{}])[-1].get("status") == "error":
        return "generate_response"
    return "process_agents"

workflow.add_conditional_edges("approval_gate", _route_after_approval, {
    "generate_response": "generate_response",
    "process_agents": "process_agents",
})
```

If the existing graph already uses `add_conditional_edges` from `fga_check`, merge the new routing in rather than adding two conflicting edges — re-read the current `_build_workflow` carefully first.

- [ ] **Step 4: Inject `ApprovalService` into the `Orchestrator`**

Find the `Orchestrator.__init__` around line 156. Add a parameter and assignment:

```python
def __init__(
    self,
    user_token: str,
    user_info: Optional[Dict[str, Any]] = None,
    approval_service: Optional["ApprovalService"] = None,
):
    # ... existing body ...
    self._approval_service = approval_service  # may be None during unit construction
```

Add the import at the top of the file:

```python
from backend.services.approval_service import ApprovalService  # type: ignore
```

The caller (api/main.py) will pass an instance in Task 14.

- [ ] **Step 5: Update `_generate_response_node` to emit the pending message**

Find `_generate_response_node`. Near the start, after existing context collection, add:

```python
if state.get("pending_approval") is not None:
    pa = state["pending_approval"]
    state["response"] = (
        f"This inventory update ({pa['intent']['original_task']!r}) requires manager "
        f"approval. Request {pa['request_id']} sent to {pa['approver_group']}. "
        f"I'll complete it automatically the moment it's approved — you can close this tab."
    )
    return state
```

Return immediately so the node doesn't run its usual LLM-summary path.

- [ ] **Step 6: Smoke-verify the graph imports and wires**

```
python -c "
from dotenv import load_dotenv; load_dotenv()
from backend.orchestrator.orchestrator import Orchestrator
o = Orchestrator(user_token='x', user_info={'email':'u','sub':'s'}, approval_service=None)
g = o._build_workflow()
print('nodes:', sorted(g.nodes.keys()))
"
```

Expected output must include `'approval_gate'` in the node list.

- [ ] **Step 7: Commit**

```bash
git add backend/orchestrator/orchestrator.py
git commit -m "Add approval_gate LangGraph node with conditional routing"
```

---

## Task 12: Backend API — `ChatResponse.pending_approval` field

**Files:**
- Modify: `backend/api/main.py` (the `ChatResponse` model and `/api/chat` handler)

- [ ] **Step 1: Add field to `ChatResponse`**

Find the `ChatResponse` pydantic model (around line 112). Add:

```python
class ChatResponse(BaseModel):
    # ... existing fields ...
    pending_approval: Optional[Dict[str, Any]] = None
```

- [ ] **Step 2: Populate from orchestrator state in `/api/chat`**

In the `chat` handler (around line 148), after the orchestrator produces `final_state`, read `final_state.get("pending_approval")` and include it in the response construction:

```python
return ChatResponse(
    response=final_state["response"],
    agent_flow=final_state.get("agent_flow", []),
    token_exchanges=final_state.get("token_exchanges", []),
    fga_checks=final_state.get("fga_checks", []),
    pending_approval=final_state.get("pending_approval"),
)
```

- [ ] **Step 3: Smoke-verify via curl (orchestrator still runs normally without OIG)**

Start the backend: `cd backend && uvicorn api.main:app --reload`.

In another terminal:

```
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <a valid Okta ID token from your Next.js session>" \
  -d '{"message":"what do we have in stock?"}' | jq '.pending_approval'
```

Expected: `null` (no gate triggered for a read).

- [ ] **Step 4: Commit**

```bash
git add backend/api/main.py
git commit -m "Add pending_approval field to ChatResponse"
```

---

## Task 13: Backend API — `GET /api/approvals/{request_id}`

**Files:**
- Modify: `backend/api/main.py`

- [ ] **Step 1: Add the endpoint**

Append to `backend/api/main.py` (after the other route handlers):

```python
from backend.services.factory import build_approval_service

_approval_service = None  # lazily constructed on first request

def _get_approval_service():
    global _approval_service
    if _approval_service is None:
        _approval_service = build_approval_service(DEMO_STORE)  # or whatever the existing global is named
    return _approval_service


@app.get("/api/approvals/{request_id}")
async def get_approval(request_id: str):
    svc = _get_approval_service()
    # Fast-path: if approved-not-executed, resolve now.
    status = await svc.execute_if_approved(request_id)
    return _approval_status_to_json(status)


def _approval_status_to_json(status) -> dict:
    # Convert dataclass to JSON-safe dict for FastAPI
    from dataclasses import asdict
    data = asdict(status)
    # Flatten nested dataclass if present
    if data.get("execution_result"):
        data["execution_result"] = asdict(status.execution_result)
    if data.get("intent"):
        data["intent"] = asdict(status.intent)
    return data
```

Replace `DEMO_STORE` with the actual variable name the current file uses for the shared `DemoStore` instance.

- [ ] **Step 2: Smoke-verify with a fabricated id (will 404 or OIG error)**

```
curl -s http://localhost:8000/api/approvals/does-not-exist | jq
```

Expected: either a clean 500 with an informative error, OR a response indicating OIG returned 4xx. Either way, NOT a stack trace leaking to the client. If a raw stack appears, wrap the endpoint body in a try/except that returns `{"error": str(exc), "status": "error"}` with HTTP 502.

- [ ] **Step 3: Commit**

```bash
git add backend/api/main.py
git commit -m "Add GET /api/approvals/{id} resolver endpoint"
```

---

## Task 14: Backend API — `GET /api/approvals` (list by user) + startup poller

**Files:**
- Modify: `backend/api/main.py`

- [ ] **Step 1: Add the list endpoint**

Append:

```python
@app.get("/api/approvals")
async def list_approvals(user: str | None = None):
    svc = _get_approval_service()
    try:
        raw_list = await svc._oig.list_requests(
            request_type_id=os.environ["OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"],
            status=None,
        )
    except Exception as exc:  # noqa: BLE001
        return {"items": [], "error": str(exc)}

    out = []
    for raw in raw_list:
        status = svc._status_from_raw(raw.get("id") or "", raw)
        if user and status.intent and status.intent.user_email != user:
            continue
        out.append(_approval_status_to_json(status))
    return {"items": out}
```

- [ ] **Step 2: Add the background poller**

Still in `backend/api/main.py`, add near the startup event handlers:

```python
import asyncio as _asyncio

_poll_task: _asyncio.Task | None = None


async def _approval_poller():
    import logging
    log = logging.getLogger("approval_poller")
    interval = int(os.getenv("APPROVAL_POLL_INTERVAL_SECONDS", "60"))
    while True:
        try:
            svc = _get_approval_service()
            raw_list = await svc._oig.list_requests(
                request_type_id=os.environ["OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"],
                status="APPROVED",
            )
            for raw in raw_list:
                rid = raw.get("id")
                if not rid:
                    continue
                try:
                    await svc.execute_if_approved(rid)
                except Exception as exc:  # noqa: BLE001
                    log.warning("poller execute failed for %s: %s", rid, exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("poller loop error: %s", exc)
        await _asyncio.sleep(interval)


@app.on_event("startup")
async def _start_approval_poller():
    global _poll_task
    _poll_task = _asyncio.create_task(_approval_poller())


@app.on_event("shutdown")
async def _stop_approval_poller():
    global _poll_task
    if _poll_task is not None:
        _poll_task.cancel()
        try:
            await _poll_task
        except _asyncio.CancelledError:
            pass
```

If the file already has a `@app.on_event("shutdown")` handler (it does, around line 53), merge the cancellation into that existing handler rather than declaring a second one.

- [ ] **Step 3: Smoke-verify poller starts and doesn't crash**

Restart the backend and watch the log for a couple of minutes:

```
cd backend && uvicorn api.main:app --reload
```

Within ~60s you should see either a log line indicating a successful empty OIG poll or a warning if the token is bad. No stack trace should be printed; the loop should tick again.

- [ ] **Step 4: Commit**

```bash
git add backend/api/main.py
git commit -m "Add GET /api/approvals list endpoint and background poller"
```

---

## Task 15: Wire `ApprovalService` into `Orchestrator` construction

**Files:**
- Modify: `backend/api/main.py` (the `/api/chat` handler where `Orchestrator(...)` is constructed)

- [ ] **Step 1: Pass the shared service to `Orchestrator`**

In the `chat` handler body, just before `Orchestrator(...)` is instantiated:

```python
approval_svc = _get_approval_service()
orchestrator = Orchestrator(
    user_token=user_token,
    user_info=user_info,
    approval_service=approval_svc,
)
```

- [ ] **Step 2: End-to-end smoke — unexecuted gate path**

Prerequisites: `.env` populated with real Okta OIG values, Okta group + request type created (see Task 18 doc), approver group has at least one member.

Trigger a write of 500+ units:

```
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid Okta ID token>" \
  -d '{"message":"add 500 basketballs to inventory"}' | jq '.pending_approval, .agent_flow[-1]'
```

Expected:
- `pending_approval` is an object with a `request_id`.
- Last `agent_flow` step has `step: "approval_gate"` and `status: "pending"`.
- In your Okta Admin console's Access Requests view, a new request is visible with the `[INTENT_JSON]` fence in the justification.

- [ ] **Step 3: Commit**

```bash
git add backend/api/main.py
git commit -m "Pass ApprovalService into Orchestrator for chat requests"
```

---

## Task 16: Frontend — `ApprovalStatusCard`

**Files:**
- Create: `packages/progear-sales-agent/src/components/ApprovalStatusCard.tsx`

- [ ] **Step 1: Write the component**

Create `packages/progear-sales-agent/src/components/ApprovalStatusCard.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

type Approver = { email?: string; display_name?: string };
type Intent = {
  user_email?: string;
  agent?: string;
  scope?: string;
  product_name?: string;
  quantity_delta?: number;
  original_task?: string;
};
type ExecutionResult = {
  txn_id: string;
  previous_quantity: number;
  new_quantity: number;
};

export type ApprovalStatus = {
  request_id: string;
  status: "pending" | "approved" | "executed" | "denied";
  submitted_at?: string;
  approved_at?: string;
  executed_at?: string;
  approver?: Approver;
  intent?: Intent | null;
  execution_result?: ExecutionResult | null;
  denial_reason?: string | null;
  poll_error?: boolean;
};

const STATUS_STYLES: Record<ApprovalStatus["status"], string> = {
  pending: "bg-amber-100 text-amber-900 border-amber-300",
  approved: "bg-blue-100 text-blue-900 border-blue-300",
  executed: "bg-emerald-100 text-emerald-900 border-emerald-300",
  denied: "bg-rose-100 text-rose-900 border-rose-300",
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function ApprovalStatusCard({
  initial,
}: {
  initial: ApprovalStatus | null;
}) {
  const [status, setStatus] = useState<ApprovalStatus | null>(initial);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!status) return;
    if (status.status === "executed" || status.status === "denied") return;

    const id = status.request_id;
    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/approvals/${id}`);
        if (!res.ok) return;
        const data: ApprovalStatus = await res.json();
        setStatus(data);
      } catch {
        /* swallow; next tick will retry */
      }
    };
    tick();
    const handle = setInterval(tick, 5000);
    return () => clearInterval(handle);
  }, [status?.request_id, status?.status]);

  if (!status) return null;

  const intent = status.intent ?? {};

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900">Approval Request</span>
          <span
            className={`rounded-full border px-2 py-0.5 text-xs ${STATUS_STYLES[status.status]}`}
          >
            {status.status}
          </span>
          {status.poll_error && (
            <span className="text-xs text-gray-500">(service unreachable, retrying)</span>
          )}
        </div>
        <span className="text-gray-400">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-gray-100 px-4 py-3 text-sm">
          <div className="text-gray-500">Request ID: <span className="font-mono">{status.request_id}</span></div>
          {intent.original_task && (
            <div>Task: <span className="italic">&ldquo;{intent.original_task}&rdquo;</span></div>
          )}
          {typeof intent.quantity_delta === "number" && intent.product_name && (
            <div>
              Action: add {intent.quantity_delta.toLocaleString()} {intent.product_name} ({intent.scope})
            </div>
          )}
          {status.submitted_at && <div>Submitted: {status.submitted_at}</div>}
          {status.approved_at && (
            <div>
              Approved {status.approved_at}
              {status.approver?.display_name && ` by ${status.approver.display_name}`}
            </div>
          )}
          {status.status === "executed" && status.execution_result && (
            <div className="rounded-lg bg-emerald-50 p-2">
              <div>Transaction: <span className="font-mono">{status.execution_result.txn_id}</span></div>
              <div>
                {status.execution_result.previous_quantity} → {status.execution_result.new_quantity}
              </div>
            </div>
          )}
          {status.status === "denied" && status.denial_reason && (
            <div className="rounded-lg bg-rose-50 p-2">Reason: {status.denial_reason}</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Smoke-verify build**

```
cd packages/progear-sales-agent && npx tsc --noEmit
```

Expected: no type errors. If `NEXT_PUBLIC_API_BASE_URL` is reported as undeclared, the existing code uses the same var in `page.tsx:198` — confirm it's declared in your env.d.ts or referenced the same way; otherwise use `process.env.NEXT_PUBLIC_API_BASE_URL as string`.

- [ ] **Step 3: Commit**

```bash
git add packages/progear-sales-agent/src/components/ApprovalStatusCard.tsx
git commit -m "Add ApprovalStatusCard component with 5s polling"
```

---

## Task 17: Frontend — slot `ApprovalStatusCard` into `page.tsx`

**Files:**
- Modify: `packages/progear-sales-agent/src/app/page.tsx`

- [ ] **Step 1: Add state, sessionStorage hydration, and the debug hook**

Near the other `useState` declarations (around line 64), add:

```tsx
const [pendingApproval, setPendingApproval] = useState<any | null>(null);
const APPROVAL_STORAGE_KEY = "progear.pendingApproval";
```

In the existing hydration `useEffect` (around line 75), add a read for the new key:

```tsx
const savedApproval = sessionStorage.getItem(APPROVAL_STORAGE_KEY);
if (savedApproval) {
  try { setPendingApproval(JSON.parse(savedApproval)); } catch { /* ignore */ }
}
```

In the persistence `useEffect` (around line 105, beside the other `sessionStorage.setItem` calls), add:

```tsx
if (pendingApproval) {
  sessionStorage.setItem(APPROVAL_STORAGE_KEY, JSON.stringify(pendingApproval));
} else {
  sessionStorage.removeItem(APPROVAL_STORAGE_KEY);
}
```

And add `pendingApproval` to the dep array of that effect.

- [ ] **Step 2: Populate `pendingApproval` from each chat response**

In the chat submit handler (around line 207 where `setCurrentAgentFlow(data.agent_flow || [])` is called), add:

```tsx
setPendingApproval(data.pending_approval ?? null);
```

In the clear-history handler (around line 130) add:

```tsx
setPendingApproval(null);
```

- [ ] **Step 3: Render the card between `FGAExplanationCard` and `Learn More`**

Import at top:

```tsx
import ApprovalStatusCard from '@/components/ApprovalStatusCard';
```

Find the block around line 474:

```tsx
<FGAExplanationCard checks={currentFGAChecks} isLoading={isLoading} />
```

Immediately AFTER it, BEFORE the `Learn More` block (line 483), insert:

```tsx
{pendingApproval && (
  <div className="mb-4">
    <ApprovalStatusCard initial={pendingApproval} />
  </div>
)}
```

- [ ] **Step 4: Add the `?mockApprovalId=` debug hook**

Near the top of the `Home` component, below the other `useState` blocks, add:

```tsx
useEffect(() => {
  if (process.env.NEXT_PUBLIC_ENABLE_DEBUG_HOOKS !== "true") return;
  const params = new URLSearchParams(window.location.search);
  const mockId = params.get("mockApprovalId");
  if (mockId) {
    setPendingApproval({
      request_id: mockId,
      status: "pending",
      submitted_at: new Date().toISOString(),
      intent: {
        product_name: "basketball",
        quantity_delta: 500,
        scope: "inventory:write",
        original_task: "debug: add 500 basketballs",
      },
    });
  }
}, []);
```

- [ ] **Step 5: Smoke-verify frontend build + render**

```
cd packages/progear-sales-agent && npm run build
```

Expected: build succeeds. Launch `npm run dev`, open `http://localhost:3000/?mockApprovalId=req_fake_1` with `NEXT_PUBLIC_ENABLE_DEBUG_HOOKS=true` in `.env`. Expected: the "Approval Request" card appears in the right panel between the FGA card and Learn More, with a `pending` badge and the request ID. The card will attempt to poll `/api/approvals/req_fake_1` — you'll see a network error since it doesn't exist, which is fine for this smoke test.

- [ ] **Step 6: Commit**

```bash
git add packages/progear-sales-agent/src/app/page.tsx
git commit -m "Render ApprovalStatusCard in right panel and persist pending requests"
```

---

## Task 18: Write `docs/OIG_APPROVAL_SETUP.md`

**Files:**
- Create: `docs/OIG_APPROVAL_SETUP.md`

- [ ] **Step 1: Author the setup doc**

Create `docs/OIG_APPROVAL_SETUP.md`:

```markdown
# OIG Approval Flow — Okta Admin Setup

One-time setup in the Okta Admin console to enable the OIG approval gate. Companion to the design spec (`docs/superpowers/specs/2026-05-11-oig-approval-flow-design.md`) and test scenarios (`docs/OIG_APPROVAL_TEST_SCENARIOS.md`).

## 1. Create the approver group

- Directory → Groups → Add Group
- Name: `InventoryApprovers` (or your preferred name — record the final name)
- Add at least one member who is NOT the demo chat user
- Capture the **Group ID** from the group's details page URL (`/admin/group/{GROUP_ID}`)

## 2. Create the OIG Request Type

- Identity Governance → Request Types → Create Request Type
- Name: `AI Agent Inventory Write Approval`
- Approver: the `InventoryApprovers` group created above
- Fields: default single-approver workflow is sufficient; no custom fields required (the intent JSON is stored in the built-in justification field)
- Save and capture the **Request Type ID**

## 3. Create the Okta API token

- Security → API → Tokens → Create Token
- Name: `ai-agent-oig-integration`
- Assign to a service-account user with permissions to read/write OIG Access Requests (typically Super Admin for demo; scope down for production)
- Copy the token value (shown once)

## 4. Populate `.env`

Add the captured values to your repo-root `.env` (and mirror on Render for deployed envs):

```
OKTA_OIG_BASE_URL=https://<your-tenant>.oktapreview.com
OKTA_OIG_API_TOKEN=<token from step 3>
OKTA_OIG_INVENTORY_REQUEST_TYPE_ID=<from step 2>
OKTA_APPROVER_GROUP_ID=<from step 1>
OKTA_APPROVER_GROUP_NAME=InventoryApprovers
APPROVAL_QUANTITY_THRESHOLD=500
APPROVAL_POLL_INTERVAL_SECONDS=60
```

## 5. Verify end-to-end

After restarting the backend:

```
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <user ID token>" \
  -d '{"message":"add 500 basketballs"}' | jq .pending_approval
```

Expected: JSON with a `request_id`. Check the Okta Admin "Access Requests" view — a new request should be visible assigned to `InventoryApprovers`.

## Troubleshooting

- **401 from Okta** — API token expired or lacks OIG permissions. Regenerate.
- **No approver group visible on the request** — the group was not assigned to the Request Type. Edit the Request Type and re-assign.
- **Polling sees 404** — request type ID is wrong. Double-check the ID from step 2.
- **Justification is shown without the `[INTENT_JSON]` block in the approver UI** — some Okta UIs truncate long justification text. Approvers can still approve; the backend always reads the full field via the API.
```

- [ ] **Step 2: Commit**

```bash
git add docs/OIG_APPROVAL_SETUP.md
git commit -m "Document Okta Admin setup for OIG approval flow"
```

---

## Task 19: Write `docs/OIG_APPROVAL_TEST_SCENARIOS.md`

**Files:**
- Create: `docs/OIG_APPROVAL_TEST_SCENARIOS.md`

- [ ] **Step 1: Author the scenarios doc**

Create `docs/OIG_APPROVAL_TEST_SCENARIOS.md` by copying the 8-scenario table from spec §7.1 into a runnable checklist. Do not reference spec sections in the text — this file is meant to be read standalone by a demo presenter.

```markdown
# OIG Approval Flow — Test Scenarios

Manual scenarios for verifying the OIG approval gate. Run in order; scenarios 1–6 are the demo script, 7–8 are ops-mode checks.

## Environment prerequisites

- Backend running at `localhost:8000` with `.env` populated (see `OIG_APPROVAL_SETUP.md`).
- Frontend running at `localhost:3000`.
- Demo user = a manager with clearance 5 and NOT on vacation (e.g. `bob.manager@atko.email`).
- At least one approver in the `InventoryApprovers` group.

## Scenario 1 — Gate does NOT fire below threshold

**Setup:** logged in as demo user.

**Action:** in chat, send `add 499 basketballs`.

**Expected:**
- Response says the write executed.
- Right panel: no Approval Request card appears.
- In Okta: no new Access Request is created.
- Inventory in `demo_store` actually changed.

## Scenario 2 — Gate fires, foreground approval

**Action:** `add 500 basketballs`.

**Expected immediately:**
- Response says "requires manager approval", mentions the request ID and approver group.
- Right panel: Approval Request card with `pending` badge.
- Inventory unchanged.
- Okta: new Access Request visible with a readable justification including `[INTENT_JSON]` fence.

**Next step:** in another browser, sign in as an approver and approve the request in Okta's dashboard.

**Expected within ~5s:**
- Approval card flips to `approved`, then to `executed`.
- Card shows approver name/email, previous → new quantity.
- Inventory now reflects the update.

## Scenario 3 — Background poller completes while user is away

**Action:** send `add 750 basketballs`. Close the browser tab.

**In Okta:** approve the request.

**Wait:** at least `APPROVAL_POLL_INTERVAL_SECONDS` (default 60s).

**Expected:**
- Backend logs show the poller executed the request.
- Okta Access Request comments include `[EXECUTED:<txn>] ...`.
- `demo_store` inventory reflects +750.
- Reopen the app (`localhost:3000`) — the card hydrates from `sessionStorage`, calls `GET /api/approvals/{id}`, and shows `executed` state.

## Scenario 4 — Approval denied

**Action:** `add 1000 basketballs`. Deny in Okta.

**Expected:**
- Approval card flips to `denied` (red badge).
- Inventory unchanged.
- Card shows the denial reason if Okta included one.

## Scenario 5 — Clearance-1 user never reaches the gate

**Setup:** log in as a manager with clearance 1.

**Action:** `add 500 basketballs`.

**Expected:**
- FGA blocks the request before the approval gate runs.
- No OIG request created.
- Existing FGA denial UI fires.

## Scenario 6 — Idempotent re-resolve

**Precondition:** scenario 2 just completed (status = executed).

**Action:** hit `GET /api/approvals/<request_id>` directly:

```
curl -s http://localhost:8000/api/approvals/<request_id> | jq
```

**Expected:**
- Same `txn_id` returned.
- Inventory did NOT change a second time (verify via a read query in chat or inspect `demo_store`).
- No new `[EXECUTED:]` comment added in Okta.

## Scenario 7 — OIG API down at gate time (ops)

**Setup:** temporarily break `OKTA_OIG_API_TOKEN` (append `_bad`) and restart the backend.

**Action:** `add 500 basketballs`.

**Expected:**
- Chat returns a clean error about the approval service being unavailable.
- `agent_flow` shows `approval_gate: error`.
- No partial state, no crash.

Restore the token before continuing.

## Scenario 8 — Transient execution failure and retry (ops)

**Setup:** introduce a one-shot failure in `demo_store.update_inventory_quantity` (monkey-patch in a REPL or add a temporary `if random.random() < 1: raise ...` that's manually cleared after the first call).

**Action:** send `add 500 basketballs` and approve.

**Expected:**
- First resolver attempt fails. Okta request has a `[EXECUTION_FAILED:attempt=1:reason=...]` comment.
- Within the next poll tick, the second attempt succeeds. `[EXECUTED:<txn>]` comment added.
- Inventory reflects the update exactly once.

Remove the simulated failure.
```

- [ ] **Step 2: Commit**

```bash
git add docs/OIG_APPROVAL_TEST_SCENARIOS.md
git commit -m "Add manual test scenarios for OIG approval flow"
```

---

## Task 20: End-to-end demo verification

**Files:** none — exercise the full feature.

- [ ] **Step 1: Cold-start both tiers**

Terminal 1:
```
cd backend && source ../.venv/bin/activate && uvicorn api.main:app --reload
```

Terminal 2:
```
npm run dev
```

- [ ] **Step 2: Run Scenarios 1–6 from `docs/OIG_APPROVAL_TEST_SCENARIOS.md`**

Follow the doc top-to-bottom. Each scenario's "Expected" section must pass. If any fails, read its backend logs and the Okta Access Request comments for clues.

- [ ] **Step 3: Run Scenarios 7 and 8 (ops mode)**

These require temporary breakage of env/code; restore after each.

- [ ] **Step 4: Capture screenshots for the demo deck (optional)**

One screenshot per state transition: pending → approved → executed. Save to `docs/screenshots/oig-approval/` if you want to embed them in the architecture explainer page later.

- [ ] **Step 5: Final commit (no code change — just the sign-off)**

If screenshots were added:

```bash
git add docs/screenshots/oig-approval/
git commit -m "Add OIG approval flow demo screenshots"
```

Otherwise there's nothing to commit for this task.

---

## Self-review notes (author-only, delete after execution if you prefer)

- Spec coverage check:
  - §3 flow (approval_gate between fga_check and process_agents) → Task 11.
  - §4.1 OktaOIGClient → Task 2.
  - §4.2 ApprovalService → Tasks 6, 7, 8, 9.
  - §4.3 orchestrator modification → Task 11.
  - §4.4 API endpoints + startup poller → Tasks 12, 13, 14, 15.
  - §4.5 ApprovalStatusCard → Task 16.
  - §4.6 page.tsx integration → Task 17.
  - §5 data contracts → reflected in code of Tasks 2, 3, 7, 8, 12, 13.
  - §6 error handling → embedded across Tasks 9, 13, 14; transient retry limit = 3 (Task 9 constant `MAX_EXECUTION_ATTEMPTS`).
  - §7 testing → Tasks 19, 20 + structural testability preserved via dependency injection in Tasks 2, 6, 10.
  - §8 Okta Admin setup → Task 18.
  - §9 env vars → Task 1.
- No placeholder strings left (TBD/TODO/…); all code blocks are complete.
- Type consistency: `Intent` is the dataclass introduced in Task 3 and used identically in Tasks 7, 8, 9. `ExecutionResult` / `ApprovalStatus` declared in Task 6, populated in Task 8/9, serialized in Task 13.
- One carried simplification: on status "executed" reconstructed from comments (Task 8 `_status_from_raw` executed branch), `previous_quantity` / `new_quantity` are set to `-1` because the marker comment doesn't currently carry those numbers. The foreground fast-path in Task 13 always comes from the live `execute_if_approved` which DOES produce real numbers. If the user-facing "executed" display must always show real numbers post-restart, amend Task 9 to embed them into the `[EXECUTED:]` comment text and Task 8 to parse them back out.

---
