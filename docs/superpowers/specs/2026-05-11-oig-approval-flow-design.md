# OIG Access Request Approval Flow — Design Spec

**Date:** 2026-05-11
**Status:** Approved (sections 1–5)
**Scope:** Backend + frontend changes to add a human-in-the-loop approval gate for high-quantity inventory writes, backed by Okta Identity Governance (OIG) Access Requests.

---

## 1. Overview

Insert an asynchronous approval gate between the existing FGA check and agent execution. When a chat request targets `inventory:write` with a parsed `quantity >= 500`, the orchestrator creates an Okta OIG Access Request assigned to a pre-configured approver group and short-circuits the response with a `pending_approval` payload. Approval may happen immediately or days later; the backend resolves it via a hybrid poller (foreground per-request + in-process background loop). On approval, the backend executes the write using a service token minted from the AI agent's JWT assertion, with full idempotency so foreground and background paths cannot double-fire.

OIG is the sole persistence layer — no new database. The request's `justification` field carries human-readable text plus a fenced JSON payload of the original intent. On execution, a `[EXECUTED:<txn_id>]` comment marks completion; the marker is also the cross-process idempotency ledger.

## 2. Goals and Non-Goals

**Goals**
- Gate `inventory:write` with `quantity_delta >= 500` on OIG approval by a named Okta group.
- Support approval latency from seconds to days without state loss across restarts.
- Preserve the existing demo surface (`agent_flow`, `token_exchanges`, `fga_checks`) and extend it with `pending_approval` and an `ApprovalStatusCard` in the right panel.
- Idempotent execution, verifiable from OIG audit trail alone.

**Non-Goals**
- Approvals for other scopes (`pricing:*`, `sales:*`, `customer:*`) — deferred.
- OIG Event Hooks (webhook delivery of approval events) — noted as a future upgrade that reuses the same resolver.
- Adding a backend test suite. Existing project convention: no pytest. Structural testability is preserved so a suite can be added later without refactor.
- Multi-tenant / per-request-type approver routing — current design is single configurable group.

## 3. Architecture and Flow

**LangGraph pipeline change.** Current:

```
router → exchange_tokens → fga_check → process_agents → generate_response
```

New:

```
router → exchange_tokens → fga_check → approval_gate → process_agents → generate_response
                                             │
                                             └─(pending)→ generate_response (early return)
```

`approval_gate` fires only when both:
- a target scope in `state["agent_scopes"]` equals `inventory:write`, **and**
- the parsed intent contains a `quantity_delta >= APPROVAL_QUANTITY_THRESHOLD` (default 500, configurable — see §9).

The gate is positioned **after** FGA so approvers never see requests that would fail clearance or vacation checks. If FGA fails, the existing denial path runs unchanged and no OIG request is created.

**Resolution paths.** Two callers, one resolver:
1. **Foreground fast-path** — frontend polls `GET /api/approvals/{id}` every 5s while the `ApprovalStatusCard` is visible. The endpoint may synchronously execute if it observes `APPROVED` without an `[EXECUTED:]` marker.
2. **Background loop** — an asyncio task started at FastAPI startup runs every 60s, lists OIG requests of type `inventory-write-approval` with status `APPROVED`, and calls the same resolver for each. This is the path that handles the "user closed the tab for 10 days" case.

Both paths call `ApprovalService.execute_if_approved(request_id)`, which holds an in-process `asyncio.Lock` keyed by `request_id` and re-reads OIG inside the lock to confirm the `[EXECUTED:]` marker is absent before executing. Cross-process idempotency is additionally enforced at the `demo_store` level via an `idempotency_key=request_id` parameter.

**Execution identity.** At resolve time the original user token is gone. The resolver mints a fresh access token for `inventory:write` using the AI agent's JWT assertion (`OKTA_AI_AGENT_PRIVATE_KEY`). The audit record captures: original requester email, approver identity (from OIG), approval timestamp, service-token subject, and execution timestamp.

## 4. Components

Six new or modified units, each with a single responsibility.

### 4.1 `backend/services/okta_oig_client.py` (new)
Thin HTTP wrapper over the Okta OIG Access Requests REST API. No business logic.

```python
class OktaOIGClient:
    def __init__(self, base_url: str, api_token: str, http: AsyncClient): ...
    async def create_request(request_type_id, requester_id, approver_group_id, subject, justification) -> dict
    async def get_request(request_id) -> dict
    async def list_requests(request_type_id, status) -> list[dict]
    async def add_comment(request_id, text) -> None
```

Auth: bearer token from env var `OKTA_OIG_API_TOKEN`. 401 → raises `OIGAuthError` (no retry). 5xx / timeout → raises `OIGUnavailable` (caller decides retry semantics).

### 4.2 `backend/services/approval_service.py` (new)
All approval-flow business logic. Depends on `OktaOIGClient`, `demo_store`, a service-token minter, and a clock callable.

```python
class ApprovalService:
    def should_gate(scope: str, parsed_intent: dict) -> bool
    async def create_request(user: UserContext, agent: str, scope: str, intent: Intent) -> str  # request_id
    async def get_status(request_id: str) -> ApprovalStatus
    async def execute_if_approved(request_id: str) -> ExecutionResult
```

- `should_gate` is pure: returns `True` iff `scope == "inventory:write"` and `parsed_intent.quantity_delta >= APPROVAL_QUANTITY_THRESHOLD` (default 500, see §9).
- `create_request` encodes the intent JSON inside a `[INTENT_JSON]...[/INTENT_JSON]` fence within the OIG `justification` so approvers still see human-readable text.
- `execute_if_approved` is idempotent. Holds an `asyncio.Lock(request_id)`, re-fetches OIG inside the lock, checks for `[EXECUTED:]` marker, executes, writes the marker.

### 4.3 `backend/orchestrator/orchestrator.py` (modified)
Add one LangGraph node and one branch:

```python
workflow.add_node("approval_gate", self._approval_gate_node)
# Edges:
#   fga_check -> approval_gate
#   approval_gate -> generate_response   (if state["pending_approval"] is set)
#   approval_gate -> process_agents      (otherwise)
```

`_approval_gate_node` parses `quantity_delta` from the task (uses the same regex currently in `backend/agents/inventory_agent.py:98-100`, lifted into a shared helper), calls `ApprovalService.should_gate`, and on hit creates the OIG request + sets `state["pending_approval"]`.

New `WorkflowState` fields:

```python
pending_approval: Optional[Dict[str, Any]]   # set by approval_gate; drives early return
parsed_intent: Optional[Dict[str, Any]]      # populated by router / gate; carries quantity_delta
```

### 4.4 `backend/api/main.py` (modified)
Two new endpoints plus a startup hook:

```python
GET  /api/approvals/{request_id}     # returns ApprovalStatus; may synchronously execute
GET  /api/approvals?user={email}     # list user's in-flight requests

@app.on_event("startup")
async def _start_poller():
    asyncio.create_task(_approval_poller())  # 60s tick
```

`ChatResponse` gains an optional top-level `pending_approval` field, null when no gate fired.

### 4.5 `packages/progear-sales-agent/src/components/ApprovalStatusCard.tsx` (new)
Collapsible card matching the existing style (model off `FGAExplanationCard.tsx`). Props:

```ts
type ApprovalStatus = {
  request_id: string;
  status: 'pending' | 'approved' | 'executed' | 'denied';
  submitted_at: string;
  approved_at?: string;
  executed_at?: string;
  approver?: { email: string; display_name: string };
  intent: { product_name: string; quantity_delta: number; scope: string; original_task: string };
  execution_result?: { txn_id: string; previous_quantity: number; new_quantity: number };
};
```

Internally: `useEffect` with `setInterval(5000)` polling `/api/approvals/{id}` while `status in ('pending','approved')`. Stops at `executed` or `denied`. Visual: status badge, approver group, submit/approve/execute timestamps, intent summary, and final quantity transition on completion.

### 4.6 `packages/progear-sales-agent/src/app/page.tsx` (modified)
Slot `ApprovalStatusCard` in the right panel **between `FGAExplanationCard` (line 474) and `Learn More` (line 483)**. Track `pendingApproval` in component state; persist `request_id` to `sessionStorage` (same pattern as `currentAgentFlow` / `currentFGAChecks`) so a page refresh does not orphan the request.

### 4.7 Unchanged
`multi_agent_auth.py` already contains the JWT-assertion primitive — the service-token minter reuses it. `fga_client.py`, `agent_config.py`, and the individual agent files are not modified.

## 5. Data Flow and Contracts

### 5.1 OIG request creation (outbound)
`POST {okta_base}/governance/api/v1/requests`:

```json
{
  "requestTypeId": "<OKTA_OIG_INVENTORY_REQUEST_TYPE_ID>",
  "requesterId":   "<okta user id>",
  "subject":       "Inventory write: +500 basketball",
  "justification": "AI agent requests inventory write on behalf of bob@atko.email\nAction: Add 500 units of basketball (scope: inventory:write)\nOriginal task: \"add 500 basketballs\"\n\n[INTENT_JSON]\n{\"user_email\":\"bob@atko.email\",\"agent\":\"inventory\",\"scope\":\"inventory:write\",\"product_name\":\"basketball\",\"quantity_delta\":500,\"original_task\":\"add 500 basketballs\",\"submitted_at\":\"2026-05-11T14:22:03Z\",\"fga_check_id\":\"fga_abc123\"}\n[/INTENT_JSON]"
}
```

Approver group is pre-assigned to the Request Type in Okta Admin; it does not appear in the payload.

### 5.2 OIG status poll (inbound)
`GET {okta_base}/governance/api/v1/requests/{id}` — fields we read:

```json
{
  "id": "req_01abc...",
  "status": "PENDING | APPROVED | DENIED | COMPLETED",
  "approvedBy": { "id": "...", "displayName": "Alice Approver" },
  "approvedAt": "2026-05-11T16:04:55Z",
  "justification": "...[INTENT_JSON]{...}[/INTENT_JSON]",
  "comments": [ { "text": "[EXECUTED:inv_txn_789] completed at 2026-05-11T16:05:01Z" } ]
}
```

Resolver decision matrix:
- `APPROVED` + no `[EXECUTED:]` comment → execute, then write `[EXECUTED:<txn>]`.
- `APPROVED` + `[EXECUTED:]` present → no-op; parse prior `txn_id` and return it.
- `DENIED` → return denial with approver + reason.
- `PENDING` → return pending.
- `COMPLETED` (OIG-side terminal) → treat as APPROVED (path not expected in our flow, but handled).

### 5.3 Chat endpoint pending response
`POST /api/chat` when gate fires:

```json
{
  "response": "This inventory update (add 500 basketball units) requires manager approval. Request sent to InventoryApprovers. I'll complete it the moment it's approved.",
  "agent_flow": [ "...existing steps...", { "step": "approval_gate", "action": "Queued request req_01abc...", "status": "pending" } ],
  "token_exchanges": [ "..." ],
  "fga_checks": [ "..." ],
  "pending_approval": {
    "request_id": "req_01abc...",
    "status": "pending",
    "approver_group": "InventoryApprovers",
    "submitted_at": "2026-05-11T14:22:03Z",
    "intent": { "product_name": "basketball", "quantity_delta": 500, "scope": "inventory:write", "original_task": "add 500 basketballs" }
  }
}
```

### 5.4 Approval-status endpoint response
`GET /api/approvals/{id}`:

```json
{
  "request_id": "req_01abc...",
  "status": "pending | approved | executed | denied",
  "submitted_at": "...",
  "approved_at": "...",
  "executed_at": "...",
  "approver": { "email": "alice@atko.email", "display_name": "Alice Approver" },
  "intent": { "user_email": "...", "agent": "inventory", "scope": "inventory:write",
              "product_name": "basketball", "quantity_delta": 500, "original_task": "..." },
  "execution_result": {
    "txn_id": "inv_txn_789",
    "previous_quantity": 1200,
    "new_quantity": 1700,
    "executed_by": "ai-agent (service token)",
    "on_behalf_of": "bob@atko.email"
  }
}
```

`execution_result` is populated only when `status == "executed"`.

## 6. Error Handling

| Failure | Behavior |
|---|---|
| OIG API down on `create_request` | Chat request fails with a clear user message. `agent_flow` records `approval_gate: error`. No write executed. |
| OIG API down on foreground status poll | Endpoint returns `status: pending` + `poll_error: true`. Frontend card shows "approval service unreachable, retrying." Polling continues. |
| OIG API down on background poll | Log + swallow; retry on next tick. Loop body wrapped in `try/except` so the task never dies. |
| Approval denied | `ApprovalService.execute_if_approved` returns `{status: denied, approver, denial_reason}`. Card goes red. No write executed. Terminal `approval_gate: denied` step recorded. |
| Execution fails post-approval | Write `[EXECUTION_FAILED:attempt=N:reason=...]` comment to OIG request. Background poller retries up to 3 attempts total. After 3, write `[EXECUTION_ABANDONED]` and stop. |
| Race: foreground + background both try to execute | `asyncio.Lock(request_id)` serializes in-process. Inside the lock, refetch OIG and check `[EXECUTED:]` marker. `demo_store.update_inventory_quantity(..., idempotency_key=request_id)` enforces single-execution even across processes. |
| Quantity parse fails | Gate silently skipped (preserves current behavior). Request proceeds to `process_agents` as it does today. Rationale: fail-safe-triggering would queue every ambiguous phrasing for approval — too noisy. |
| User deactivated between submit and approval | Service-token path is unaffected (it uses the agent key, not the user session). Audit still records the original `on_behalf_of` email. |
| OIG API token expired (401) | `OktaOIGClient` raises `OIGAuthError`. Poller logs and keeps looping. Foreground returns 503. No automatic retry (would burn the token). |
| Poller/process restart mid-wait | Zero state loss — OIG is the ledger. Startup re-lists `APPROVED AND no [EXECUTED:] comment` and processes them. Retry counts reset (fresh 3-strike budget — acceptable). |

**Execution retry semantics.** Three attempts max, tracked via `[EXECUTION_FAILED:attempt=N]` comments (visible in OIG UI + survives restart). After 3, `[EXECUTION_ABANDONED]` is written and the request is ignored by future polls.

**Idempotency hardening.** In addition to the OIG `[EXECUTED:]` marker, `demo_store.update_inventory_quantity` gains an `idempotency_key` parameter. Second call with the same key is a no-op returning the prior result. This closes the narrow window between "check marker" and "write marker."

## 7. Testing

### 7.1 Manual test scenarios
Published to `docs/OIG_APPROVAL_TEST_SCENARIOS.md` (separate file, easy to hand to a demo presenter). Summary:

| # | Scenario | Expected |
|---|---|---|
| 1 | `add 499 basketballs` (manager, clearance 5) | Executes immediately. No OIG request, no `pending_approval`. |
| 2 | `add 500 basketballs`, approve in OIG | Pending card → within 5s → executed, shows previous/new quantity + approver. |
| 3 | `add 750 basketballs`, close tab, approve, wait ≥60s | Background poller executes. `[EXECUTED:]` comment present. Demo store updated. Reopening chat shows `executed` via `sessionStorage` → `/api/approvals/{id}`. |
| 4 | `add 1000 basketballs`, deny in OIG | Card flips to `denied`. No write. `approval_gate: denied` in flow. |
| 5 | Clearance-1 user: `add 500 basketballs` | FGA blocks first. No OIG request. Existing FGA denial UI fires. |
| 6 | Re-poll after execution | Returns same `execution_result`. Inventory unchanged on second call. |
| 7 | OIG API unreachable | Chat returns clean error, `approval_gate: error`, no partial state. |
| 8 | Transient execution failure | Retry succeeds on attempt 2. `[EXECUTION_FAILED:attempt=1]` + `[EXECUTED:]` comments both on the request. |

Scenarios 1–6 are the stakeholder demo. 7–8 are ops-mode correctness checks.

### 7.2 Frontend debug affordance
`?mockApprovalId=<id>` query param on the chat page injects a fake `pending_approval` into state for manual exercise of the `ApprovalStatusCard` lifecycle. Gated behind `NEXT_PUBLIC_ENABLE_DEBUG_HOOKS === 'true'` — off in production builds by default.

### 7.3 Structural testability
Even without a test suite, the new modules are written for isolation:
- `OktaOIGClient`: constructor-injected HTTP client and credentials. No globals.
- `ApprovalService`: constructor-injected `OktaOIGClient`, `demo_store`, service-token minter, and clock. `should_gate` is pure.
- `_approval_gate_node`: ≤20 lines, delegates to `ApprovalService`.

A future `tests/` directory can mock `OktaOIGClient` in a few lines and exercise every resolver decision path without Okta or the LangGraph runtime.

## 8. Okta Admin Setup (documented, executed by user)

One-time setup in the Okta Admin console. Will be captured in `docs/OIG_APPROVAL_SETUP.md` as part of implementation.

1. **Create Okta group** (or reuse an existing one) — name e.g. `InventoryApprovers`. Add members who will approve.
2. **Create OIG Request Type** — name e.g. `AI Agent Inventory Write Approval`. Assign `InventoryApprovers` as the approver group on this type.
3. **Capture IDs** — write down the Request Type ID and Approver Group ID for the env vars below.
4. **Create Okta API token** with scope to create/read OIG Access Requests. Store as `OKTA_OIG_API_TOKEN`.

## 9. Environment Variables

New entries in `.env` / `.env.example`:

```
OKTA_OIG_BASE_URL=https://<tenant>.oktapreview.com
OKTA_OIG_API_TOKEN=<Okta API token>
OKTA_OIG_INVENTORY_REQUEST_TYPE_ID=<created in Okta Admin>
OKTA_APPROVER_GROUP_ID=<Okta group id>
APPROVAL_QUANTITY_THRESHOLD=500          # overridable for demo tuning
APPROVAL_POLL_INTERVAL_SECONDS=60        # background poller tick
NEXT_PUBLIC_ENABLE_DEBUG_HOOKS=false     # frontend: enables ?mockApprovalId=
```

`APPROVAL_QUANTITY_THRESHOLD` is factored out so a live demo can drop it to a low value (e.g. 5) without redeploying.

## 10. Out of Scope / Future Work

- **Okta Event Hooks** — replace polling with push. The resolver signature stays identical; a new `POST /api/webhooks/okta/approval` endpoint calls the same `execute_if_approved`. Small follow-up.
- **Per-scope approver routing** — different thresholds/groups for `pricing:discount`, `sales:order`, etc. Requires a mapping config; trivial once the plumbing exists.
- **Persistent execution audit** — today the execution trail lives in OIG comments. A structured audit table in a real database is a later enhancement.
- **OAuth2 client-credentials for OIG access** — replace the static API token with a proper Okta OAuth app. Stronger posture, more Okta setup.
- **Multi-replica safety** — current `asyncio.Lock` is in-process. If we ever scale out, the `demo_store.idempotency_key` + OIG marker combo is sufficient for safety, but a shared Redis lock would be preferable for performance.

---

## Open Questions

None remaining — all design choices confirmed with the user across Sections 1–5. Implementation plan to follow via the `writing-plans` skill.
