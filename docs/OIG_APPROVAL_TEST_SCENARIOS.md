# OIG Approval Flow — Test Scenarios

Manual scenarios for verifying the OIG approval gate end-to-end. Run in order. Scenarios 1–6 are the stakeholder demo; 7 and 8 are ops-mode correctness checks.

Prerequisites (one-time):
- Okta tenant configured per [`docs/OIG_APPROVAL_SETUP.md`](OIG_APPROVAL_SETUP.md).
- Backend running locally at `localhost:8000`.
- Frontend running locally at `localhost:3000`.
- Demo user = a manager with clearance ≥ 5, NOT on vacation (e.g. `bob.manager@atko.email`).
- Approver group has at least one member who is NOT the demo user.

---

## Scenario 1 — Gate does NOT fire below threshold

**Setup:** signed in as the demo user.

**Action:** in chat, send `add 499 basketballs`.

**Expected:**
- Response says the write executed (normal inventory-update message).
- Right panel: no Approval Request card appears.
- Okta Admin → Access Requests: no new request created.
- `demo_store` inventory reflects the +499 update.

---

## Scenario 2 — Gate fires, foreground approval

**Action:** `add 500 basketballs`.

**Expected immediately:**
- Chat response: "This inventory update ... requires manager approval."
- Right panel: "Approval Request" card appears with `pending` badge, request ID, and intent details.
- `demo_store` inventory is unchanged.
- Okta Admin: a new request is visible under the approver group, with a readable justification that includes an `[INTENT_JSON]` fenced block.

**Next step:** in a second browser, sign in as an approver and approve the request in Okta's dashboard.

**Expected within ~5 seconds:**
- Approval card flips to `approved`, then to `executed` (green badge).
- Card shows approver name, previous → new quantity, transaction ID.
- `demo_store` inventory now reflects the +500 update.

---

## Scenario 3 — Background poller completes while user is away

**Action:** send `add 750 basketballs`. Close the browser tab immediately.

**In Okta:** approve the request.

**Wait:** at least `APPROVAL_POLL_INTERVAL_SECONDS` (default 60).

**Expected:**
- Backend logs show the poller executed the request.
- Okta Access Request has an `[EXECUTED:<txn>]` comment.
- `demo_store` inventory reflects +750.
- Reopen the chat page — the `ApprovalStatusCard` hydrates from `sessionStorage`, calls `GET /api/approvals/{id}`, and now shows `executed` state.

This scenario proves the 10-days-later case: approval decisions persist and auto-complete independently of the user's presence.

---

## Scenario 4 — Approval denied

**Action:** `add 1000 basketballs`. Deny in Okta.

**Expected:**
- Approval card flips to `denied` (red badge).
- `demo_store` inventory unchanged.
- Last entry in the agent-flow visualization: `approval_gate: denied`.
- If the approver left a reason, it appears in the card.

---

## Scenario 5 — Clearance-1 user never reaches the gate

**Setup:** sign in as a manager with clearance level 1.

**Action:** `add 500 basketballs`.

**Expected:**
- FGA blocks the write before the approval gate runs.
- No OIG request is created.
- Existing FGA denial UI fires as usual.

This confirms the gate sits behind FGA — unauthorized users never queue noise for approvers.

---

## Scenario 6 — Idempotent re-resolve

**Precondition:** Scenario 2 just completed (`status = executed`).

**Action:** hit `GET /api/approvals/<request_id>` directly:

```bash
curl -s http://localhost:8000/api/approvals/<request_id> | jq
```

**Expected:**
- Same `txn_id` returned.
- `demo_store` inventory did NOT change a second time (verify via a read in chat or by inspecting `live_data.json`).
- No new `[EXECUTED:]` comment added in Okta.

Idempotency lives in `ApprovalService.execute_if_approved` (in-process lock + OIG comment marker + `demo_store.idempotency_key`). This is the defense against the foreground fast-path racing the background poller.

---

## Scenario 7 — OIG API down at gate time (ops check)

**Setup:** temporarily break `OKTA_OIG_API_TOKEN` (append `_bad`) and restart the backend.

**Action:** `add 500 basketballs`.

**Expected:**
- Chat returns a clean error message about the approval service being unavailable.
- Agent flow shows `approval_gate: error`.
- No partial state, no stack trace leaked to the client.
- Inventory unchanged.

**Restore** `OKTA_OIG_API_TOKEN` before continuing.

---

## Scenario 8 — Transient execution failure and retry (ops check)

**Setup:** introduce a one-shot failure in `demo_store.update_inventory_quantity` (monkey-patch in a Python REPL, or edit the method to raise on the first call and clear after).

**Action:** `add 500 basketballs`, then approve in Okta.

**Expected:**
- First execution attempt fails. The OIG request gets an `[EXECUTION_FAILED:attempt=1:reason=...]` comment.
- Within one poller tick (≤ `APPROVAL_POLL_INTERVAL_SECONDS`), the second attempt succeeds. An `[EXECUTED:<txn>]` comment is added.
- `demo_store` inventory reflects the update exactly once.

Remove the simulated failure.

---

## What success looks like

If all 8 scenarios pass, the OIG approval flow is exercising every branch of:

- Trigger logic (quantity threshold, scope check)
- FGA-before-gate ordering
- Foreground resolve via `GET /api/approvals/{id}`
- Background resolve via the poller
- Idempotency across both resolve paths
- Error handling at the gate and in execution

Screenshots from Scenario 2 (pending → approved → executed transitions) are the cleanest demo material — worth saving to `docs/screenshots/oig-approval/` for presentations.
