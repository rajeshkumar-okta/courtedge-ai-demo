# OIG Approval Flow — Okta Admin Setup

One-time setup in the Okta Admin console to enable the OIG approval gate for high-quantity inventory writes. Companion docs:

- Design: [`docs/superpowers/specs/2026-05-11-oig-approval-flow-design.md`](superpowers/specs/2026-05-11-oig-approval-flow-design.md)
- Test scenarios: [`docs/OIG_APPROVAL_TEST_SCENARIOS.md`](OIG_APPROVAL_TEST_SCENARIOS.md)

## What this feature does

When a user asks the AI agent to update inventory by a quantity at or above a configurable threshold (default 500 units), the backend pauses execution and creates an Okta OIG Access Request assigned to a pre-configured approver group. The inventory write runs automatically once the request is approved — even if the user has closed their browser tab or days have passed. A background poller on the backend catches approvals that land while no one is watching.

## Prerequisites

- Okta tenant with Identity Governance (OIG) enabled.
- Admin access to that tenant.
- At least one Okta user who is NOT the demo chat user, to act as approver.

## Step 1 — Create or identify the approver group

- Directory → Groups → Add Group (or pick an existing group).
- Suggested name: `InventoryApprovers`. Write down the exact name you used — you'll paste it verbatim into `.env` as `OKTA_APPROVER_GROUP_NAME`.
- Add at least one member who is NOT the user who will be triggering the chat request.
- On the group detail page, the URL looks like `/admin/group/<GROUP_ID>`. Copy `<GROUP_ID>` — you'll need it in Step 2, but it does NOT need to be pasted into `.env` (the runtime code never reads the group ID; only the Request Type uses it).

## Step 2 — Create the OIG Request Type

- Identity Governance → Request Types → Create Request Type.
- Suggested name: `AI Agent Inventory Write Approval` (a type named `O4AA HITL Request` works interchangeably).
- Approver: set to the group from Step 1.
- **Add one custom TEXT field** called `Justification`. The backend serializes the intent payload into this field's value as an `[INTENT_JSON]...[/INTENT_JSON]` fenced blob, so approvers see a human-readable description above the fence and the backend round-trips the structured data underneath.
- Save and capture TWO values:
  - **Request Type ID** — from the URL of the type's detail page.
  - **Justification Field ID** — not visible in the admin UI. Fastest way: once the type exists, POST an empty request to `/governance/api/v1/requests` (body `{"requestTypeId":"<id>","subject":"probe","requesterFieldValues":[]}`) with your admin API token. The response includes `requesterFieldValues[].id`. Copy that. You can cancel the probe request afterward.

## Step 3 — Create an Okta API token

- Security → API → Tokens → Create Token.
- Suggested name: `ai-agent-oig-integration`.
- Assign it to a service-account user with permissions to read/write OIG Access Requests. For a demo tenant, Super Admin is sufficient; scope it down for production.
- Copy the token value (shown once on creation — save it immediately).

## Step 4 — Populate your `.env`

Paste these values into the repo-root `.env` file. Replace each `<...>` with the real value you captured above.

```bash
# Your Okta tenant URL (same as OKTA_DOMAIN)
OKTA_OIG_BASE_URL=https://<your-tenant>.oktapreview.com

# SSWS token from Step 3
OKTA_OIG_API_TOKEN=<token>

# Request Type ID from Step 2
OKTA_OIG_INVENTORY_REQUEST_TYPE_ID=<request type id>

# Justification custom-field ID from Step 2
OKTA_OIG_JUSTIFICATION_FIELD_ID=<field id>

# Human-readable group label — must match the name you used in Step 1
OKTA_APPROVER_GROUP_NAME=InventoryApprovers

# Tunables — sensible defaults shown; override freely
APPROVAL_QUANTITY_THRESHOLD=500
APPROVAL_POLL_INTERVAL_SECONDS=60

# Frontend debug hook — keep false in production
NEXT_PUBLIC_ENABLE_DEBUG_HOOKS=false
```

DO NOT commit your `.env`. `.gitignore` already excludes it.

## Step 5 — Mirror values on Render and Vercel

- Render (backend): Dashboard → Service → Environment → add the 8 keys above.
- Vercel (frontend): Project → Settings → Environment Variables → add `NEXT_PUBLIC_ENABLE_DEBUG_HOOKS` only (frontend doesn't read the others).

## Step 6 — Verify locally

Start both tiers:

```bash
# Terminal 1 — backend
cd backend && source ../.venv/bin/activate && uvicorn api.main:app --reload

# Terminal 2 — frontend
npm run dev
```

Trigger a gated request:

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <a valid user ID token from your Next.js session>" \
  -d '{"message":"add 500 basketballs"}' | jq .pending_approval
```

Expected: a JSON object with a `request_id`. Refresh the Okta Admin Access Requests view — a new request should be visible, assigned to `InventoryApprovers`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `401 Unauthorized` from Okta in backend logs | API token expired, revoked, or lacks OIG permissions. Regenerate under Security → API → Tokens. |
| `pending_approval` is always `null` even for 500+ units | Check the `agent_flow` last step — if `status: skipped`, the request didn't parse `inventory:write` scope. Confirm the user's message contains a clear write verb ("add", "update", "set"). |
| Request created but approver can't see it in Okta | The approver group was not assigned to the Request Type. Edit the Request Type in Okta Admin and re-assign. |
| Approver approves but inventory never updates | Check backend logs for the poller. Look for entries in `backend/data/approvals_ledger.json` (keyed by request_id) — `last_error` and `failed_attempts` fields show what's failing. |
| Chat card shows "approval service unreachable, retrying" | Backend can't reach Okta. Verify `OKTA_OIG_BASE_URL` is correct and outbound HTTPS is not firewalled. |

## Runtime knobs

| Env var | Effect |
|---|---|
| `APPROVAL_QUANTITY_THRESHOLD` | Minimum quantity that triggers the gate. Default 500. Drop to 5 for fast demos. |
| `APPROVAL_POLL_INTERVAL_SECONDS` | How often the backend checks OIG for new approvals. Default 60. Lower for demos. Don't go below ~10. |
| `NEXT_PUBLIC_ENABLE_DEBUG_HOOKS` | When `true`, enables `?mockApprovalId=<id>` on the chat page for UI testing without a real chat round-trip. |
