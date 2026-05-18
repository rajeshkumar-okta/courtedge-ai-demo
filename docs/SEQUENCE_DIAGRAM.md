# ProGear Sales AI — End-to-End Sequence Diagram

Traced from the current code in `backend/orchestrator/orchestrator.py`, `backend/auth/multi_agent_auth.py`, `backend/auth/fga_client.py`, and `backend/services/approval_service.py`.

The pipeline is a LangGraph state machine with six nodes:

```
router → exchange_tokens → fga_check → approval_gate
       ├─(pending_approval set)─→ generate_response → END
       └─(otherwise)──────────→ process_agents → generate_response → END
```

```mermaid
sequenceDiagram
    autonumber
    actor U as User (browser)
    participant FE as Next.js + NextAuth
    participant OKTA as Okta OIDC
    participant API as FastAPI /api/chat
    participant ORCH as Orchestrator (LangGraph)
    participant LLM as Anthropic (Claude)
    participant TX as Okta Token Exchange<br/>(ID-JAG + Auth Server)
    participant FGA as Auth0 FGA
    participant OIG as Okta OIG (Governance)
    participant LED as approvals_ledger.json
    participant AGT as Inventory Agent

    U->>FE: "add 650 balls to inventory"
    FE->>OKTA: OIDC login (PKCE)
    OKTA-->>FE: ID token (sub, email, …)
    FE->>API: POST /api/chat (Bearer ID token)

    API->>API: decode ID token → user_info
    API->>ORCH: process(message, user_info)

    rect rgb(240,245,255)
    note over ORCH: Node 1 — router
    ORCH->>LLM: classify intent + scopes
    LLM-->>ORCH: {agents:[inventory], scopes:{inventory:[inventory:write]}}
    end

    rect rgb(240,245,255)
    note over ORCH: Node 2 — exchange_tokens (per agent)
    ORCH->>TX: ID token → ID-JAG (audience = inventory auth server)
    TX-->>ORCH: ID-JAG token
    ORCH->>TX: ID-JAG → Inventory access token<br/>(scope=inventory:write)
    TX-->>ORCH: access_token { Manager, Vacation, Clearance }
    end

    rect rgb(240,245,255)
    note over ORCH: Node 3 — fga_check
    ORCH->>ORCH: extract Manager / Vacation / Clearance from access token
    ORCH->>FGA: ensure manager/clearance tuples (idempotent)
    ORCH->>FGA: check can_update inventory_item:widget-a<br/>contextual: on_vacation if true
    FGA-->>ORCH: allowed=true → agents_to_invoke=[inventory]
    end

    rect rgb(255,248,235)
    note over ORCH: Node 4 — approval_gate
    alt inventory:write AND qty ≥ threshold AND FGA allowed
        ORCH->>ORCH: parse intent (product, quantity_delta=650)
        ORCH->>OIG: POST /governance/api/v1/requests<br/>(approver group, justification, fga_check_id)
        OIG-->>ORCH: request_id (OPEN)
        ORCH->>LED: persist {request_id, intent, status:pending}
        note over ORCH: pending_approval set →<br/>route directly to generate_response
    else FGA denied OR qty < threshold OR no inventory:write
        ORCH->>ORCH: skip gate
    end
    end

    alt no pending_approval
        rect rgb(240,255,240)
        note over ORCH: Node 5 — process_agents
        ORCH->>AGT: invoke(inventory, access_token, scopes)
        AGT->>LLM: tool-using agent call
        LLM-->>AGT: structured result
        AGT-->>ORCH: agent_results
        end
    end

    rect rgb(240,240,240)
    note over ORCH: Node 6 — generate_response
    ORCH->>LLM: synthesize final reply (with agent_flow, fga_checks, token_exchanges, pending_approval)
    LLM-->>ORCH: assistant message
    end

    ORCH-->>API: { response, agent_flow, token_exchanges, fga_checks, pending_approval }
    API-->>FE: 200 JSON
    FE-->>U: chat reply + 4 governance cards (incl. ApprovalStatusCard if pending)

    note over API,OIG: Background — every N seconds
    API->>OIG: list requests (OPEN + RESOLVED)
    OIG-->>API: status / decision / resolver
    API->>LED: update ledger
```

## Notes worth highlighting

- **`exchange_tokens` runs before `fga_check`.** The FGA decision uses claims from the per-agent auth-server access token (`Manager`, `Vacation`, `Clearance`) — not from the user's ID token.
- **`approval_gate` respects FGA.** If FGA already denied the inventory agent, the gate skips OIG creation so we don't queue an approval for an unauthorized action (`orchestrator.py:577–587`).
- **Approval short-circuits agent execution.** `_route_after_approval` (line 209) routes straight to `generate_response` when `pending_approval` is set, so the inventory agent never runs until the OIG request resolves.
- **Vacation is contextual, not stored.** Persistent FGA tuples = managers + clearance. Vacation comes from the Okta access-token claim and is passed as a contextual tuple per request.
- **Out-of-band reconciliation.** `approvals_ledger.json` plus a background poller in `api/main.py` reconcile OIG decisions (`OPEN` and `RESOLVED`) so the UI eventually reflects approver action without the user re-prompting.
