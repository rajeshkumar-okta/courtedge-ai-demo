# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

ProGear Sales AI — a demo of Okta AI Agent Governance using Cross App Access (XAA) / ID-JAG token exchange, plus Auth0 FGA for fine-grained authorization. The repo is a three-tier project with one shared `.env` at the root:

- `backend/` — FastAPI + LangGraph multi-agent orchestrator (Python, deployed to Render).
- `packages/progear-sales-agent/` — Next.js 14 frontend with NextAuth/Okta (deployed to Vercel).
- `packages/progear-sales-mcp-server/` — standalone MCP server (TypeScript, not the primary demo surface).

The root `vercel.json` sets `ignoreCommand: "exit 0"` — the frontend lives in a workspace, so the root build is a no-op on Vercel. Actual deploy config lives in `packages/progear-sales-agent/vercel.json`.

## Commands

### Frontend (Next.js, root or `packages/progear-sales-agent/`)

```bash
npm run dev      # from repo root — proxies to the progear-sales-agent workspace
npm run build    # builds BOTH progear-sales-agent AND progear-sales-mcp-server
npm run lint     # run inside packages/progear-sales-agent — `next lint`
```

### Backend (FastAPI, from `backend/`)

```bash
# activate the repo-root venv first: source .venv/bin/activate
cd backend && uvicorn api.main:app --reload          # local dev (port 8000)
python -m auth.fga_seed                              # seed FGA tuples (managers + clearance)
```

Backend has no test suite and no linter configured — don't invent one.

### MCP server (`packages/progear-sales-mcp-server/`)

```bash
npm run dev      # tsx watch
npm run build    # tsc → dist/
npm run build:mcp  # same, from repo root
```

## Architecture

### End-to-end request flow

The demo's value is the **token chain**, not the chat. Every user query fans out through this pipeline in `backend/orchestrator/orchestrator.py`:

```
user_msg → router (LLM intent + scope detection)
        → FGA check (contextual tuples: vacation, clearance)
        → ID-JAG token exchange per agent (Okta)
        → per-agent MCP access token (Okta auth servers)
        → agent execution
        → unified response + audit trail (agent_flow, token_exchanges, fga_checks)
```

State is threaded through `WorkflowState` (a `TypedDict`) across LangGraph nodes. `agent_flow`, `token_exchanges`, and `fga_checks` are surfaced in the chat response so the UI can visualize the governance decisions — these fields are load-bearing for the demo, not debug scaffolding.

### Multi-agent layout

Four agents in `backend/agents/` (`sales`, `inventory`, `customer`, `pricing`), each bound to its own Okta authorization server and scope set. Configuration lives in `backend/auth/agent_config.py`. Scope-to-intent mapping is in `SCOPE_DEFINITIONS` inside `orchestrator.py` — add new operations there, not in the agents.

### Auth layers (order matters)

1. **NextAuth/Okta OIDC** (frontend) — issues user ID token.
2. **ID-JAG token exchange** (`backend/auth/multi_agent_auth.py`) — exchanges user ID token + agent JWT assertion (`OKTA_AI_AGENT_PRIVATE_KEY`, RS256) for a per-MCP access token. This is the XAA pattern.
3. **FGA check** (`backend/auth/fga_client.py`) — runs *after* Okta exchange produces claims, using contextual tuples. Vacation status is **never stored in FGA**; it's passed per-request as a contextual tuple derived from the Okta access-token claim. Managers and clearance grants are pre-seeded via `fga_seed.py`.

FGA model summary (full model in `fga_client.py` docstring):
- `inventory:read` → `can_view` (requires `active_manager` = manager AND NOT on vacation)
- `inventory:write` → `can_update` (requires `active_manager` AND sufficient `clearance_level`)
- `inventory:alert` → no FGA check

### Frontend structure

- `src/app/page.tsx` — chat UI; renders the four visualization cards (`AgentFlowCard`, `TokenExchangeCard`, `FGAExplanationCard`, `OktaSystemLog`) from backend response fields.
- `src/app/architecture/` — static architecture explainer page.
- `src/app/api/auth/` — NextAuth handler; tokens are stashed on the session so API calls forward the Okta ID token to the backend.
- `src/lib/auth.ts` — NextAuth config; uses `OKTA_CLIENT_SECRET || 'placeholder-for-pkce'` (PKCE flow — do not assume a real secret is required).

## Environment

A single `.env` at the repo root is loaded by both `backend/api/main.py` (via `python-dotenv`) and the Next.js app. `.env.example` is the canonical list. Key non-obvious vars:

- `OKTA_AI_AGENT_PRIVATE_KEY` — JWK JSON string, used for JWT Bearer assertion (no client secret).
- `FGA_STORE_ID` / `FGA_MODEL_ID` — point to the "ProGear New" store running the full `o4aa-fga-example` model (clearance + delegation).
- `OKTA_MAIN_AUTH_SERVER_ID` vs `OKTA_MCP_AUTH_SERVER_ID` — separate servers for user auth vs MCP API access.

## Conventions specific to this repo

- **Use the raw Anthropic SDK**, not LangChain's Anthropic wrapper. LangGraph is used for orchestration only; the LLM call in `orchestrator.py` goes through `anthropic.Anthropic()` directly.
- `agent_flow` / `token_exchanges` / `fga_checks` on responses are the demo's product surface — preserve their shape when editing orchestrator nodes.
- FGA tuples: managers and clearance are **pre-seeded** (persistent), vacation is **contextual** (per-request). Don't write vacation tuples.
- The root-level `vercel.json` intentionally disables builds; the active Vercel config is in `packages/progear-sales-agent/vercel.json`.
