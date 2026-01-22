# ProGear AI Agent Architecture

This document explains how the ProGear AI Agent demo works. Read this if you need to understand the system without deploying it.

For deployment instructions, see [implementation-guide.md](./implementation-guide.md).

---

## System Overview

ProGear is a multi-agent AI system where a single orchestrator coordinates 4 specialized agents. Each agent has its own authorization server and scopes, enabling fine-grained access control based on user roles.

```
┌───────────────────────────────────────────────────────────────┐
│                        User Browser                           │
│                   (Next.js on Vercel)                         │
└─────────────────────────────┬─────────────────────────────────┘
                              │
                              │ 1. User logs in via Okta
                              │ 2. Sends queries to backend
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                        Backend API                            │
│                    (FastAPI on Render)                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                     Orchestrator                        │  │
│  │              (Routes queries to agents)                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              │                                │
│         ┌────────────────────┼────────────────────┐           │
│         ▼                    ▼                    ▼           │
│    ┌─────────┐         ┌─────────┐         ┌─────────┐        │
│    │  Sales  │         │Inventory│         │Customer │  ...   │
│    │  Agent  │         │  Agent  │         │  Agent  │        │
│    └─────────┘         └─────────┘         └─────────┘        │
│                                                               │
└───────────────────────────────────────────────────────────────┘
                              │
                              │ Token Exchange (ID-JAG)
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                           Okta                                │
│                                                               │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│    │ Sales Auth   │  │Inventory Auth│  │Customer Auth │  ...  │
│    │   Server     │  │    Server    │  │    Server    │       │
│    └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                               │
│    ┌──────────────┐  ┌──────────────┐                         │
│    │   AI Agent   │  │   OIDC App   │                         │
│    │   (wlp...)   │  │   (0oa...)   │                         │
│    └──────────────┘  └──────────────┘                         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## The Four Agents

Each agent specializes in a domain of business data:

| Agent | Purpose | Scopes |
|-------|---------|--------|
| **Sales** | Orders, quotes, pipeline | `sales:read`, `sales:quote`, `sales:order` |
| **Inventory** | Stock levels, products | `inventory:read`, `inventory:write`, `inventory:alert` |
| **Customer** | Accounts, contacts, history | `customer:read`, `customer:lookup`, `customer:history` |
| **Pricing** | Margins, discounts | `pricing:read`, `pricing:margin`, `pricing:discount` |

Each agent has its own Okta Authorization Server with policies that control which users can access which scopes.

---

## Token Exchange Flow (ID-JAG)

This is the core of how AI Agent governance works. The agent doesn't use the user's token directly - it exchanges it for scoped tokens.

### The Two-Step Exchange

```
User logs in via Org Authorization Server
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: ID Token → ID-JAG                                  │
│                                                             │
│  WHERE: Org Authorization Server                            │
│         (https://your-org.okta.com/oauth2/v1/token)         │
│                                                             │
│  INPUT:  User's ID token from login                         │
│  OUTPUT: ID-JAG (Identity Assertion JWT)                    │
│                                                             │
│  The ID-JAG represents "Agent X acting on behalf of User Y" │
│                                                             │
│  IMPORTANT: The Okta AI SDK always performs Step 1 at the   │
│  Org AS. This is by design per the ID-JAG specification.    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: ID-JAG → Agent Access Token                        │
│                                                             │
│  WHERE: Target Custom Authorization Server                  │
│         (https://your-org.okta.com/oauth2/{aus...}/v1/token)│
│                                                             │
│  INPUT:  ID-JAG from Step 1                                 │
│  OUTPUT: Scoped access token for that agent's domain        │
│                                                             │
│  Okta checks: Does this user have access to these scopes?   │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
Agent uses scoped token to access resources
```

### Why Two Steps?

1. **Step 1 establishes delegation** - The ID-JAG proves the agent is acting on behalf of a specific user
2. **Step 2 enforces authorization** - Each auth server checks its policies before granting scopes

This separation allows:
- Central governance of which agents can act for which users
- Per-domain access control (user might have Sales access but not Pricing)
- Full audit trail of agent actions

---

## How the Okta AI SDK Handles Token Exchange

The Okta AI SDK handles the two-step token exchange automatically:

### Step 1: Always at the Org Authorization Server

The SDK **always** performs Step 1 (ID Token → ID-JAG) at the Org Authorization Server endpoint:
```
POST https://your-org.okta.com/oauth2/v1/token
```

This is by design, per the ID-JAG specification. The Org AS issues the ID-JAG token that can then be presented to any Custom Authorization Server in the same org.

### Step 2: At the Target Custom Authorization Server

The SDK performs Step 2 (ID-JAG → Access Token) at each MCP's Custom Authorization Server:
```
POST https://your-org.okta.com/oauth2/{auth_server_id}/v1/token
```

### Critical: User Login Must Use the Org Authorization Server

Because Step 1 always happens at the Org AS, **users must log in via the Org AS** so that their ID token's issuer matches where the SDK performs the exchange.

### The Configuration

```
NEXT_PUBLIC_OKTA_ISSUER = https://your-org.okta.com  ← Org AS (no auth server ID)
```

**Do NOT include an auth server ID in the issuer URL.** If users log in via a Custom Authorization Server, their ID tokens will have a different issuer than the Org AS, and the token exchange will fail.

---

## RBAC: Role-Based Access Control

Access is controlled by Okta group membership:

| Group | Sales | Inventory | Customer | Pricing |
|-------|-------|-----------|----------|---------|
| **ProGear-Sales** | Full | Read | Full | Full |
| **ProGear-Warehouse** | None | Full | None | None |
| **ProGear-Finance** | None | None | None | Full |

When a user queries the system:
1. Orchestrator routes the query to relevant agents
2. Each agent attempts a token exchange
3. Okta checks if the user's groups allow those scopes
4. If denied, the agent returns "access denied" (not an error)

### Demo Users

| User | Group | What They Can Access |
|------|-------|---------------------|
| Sarah Sales | ProGear-Sales | All 4 agents |
| Mike Manager | ProGear-Warehouse | Inventory only |
| Frank Finance | ProGear-Finance | Pricing only |

---

## Okta Components

### AI Agent (Workload Principal)

The AI Agent is registered in Okta's AI Agent Directory. It represents the agent's identity.

- **ID**: Starts with `wlp...`
- **Authentication**: JWK private key (no client secret)
- **Purpose**: Identifies which agent is acting on behalf of users

### OIDC Application

The OAuth/OIDC application that users log into.

- **ID**: Starts with `0oa...`
- **Linked to**: AI Agent
- **Grant types**: Authorization Code, Refresh Token, Token Exchange

### Authorization Servers

Custom authorization servers that issue tokens for specific domains.

- **ID**: Starts with `aus...`
- **Each has**: Scopes, Access Policies, Policy Rules
- **Policies specify**: Which clients (including AI Agent) can request which scopes for which users

---

## Access Policy Configuration

Each authorization server has policies that control token issuance.

### Policy Structure

```
Authorization Server: ProGear Sales MCP
│
└── Access Policy: Sales Agent Policy
    │   Assigned to: AI Agent + OIDC App
    │
    └── Rule: Sales Group Access
        IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
        AND User is member of: ProGear-Sales
        THEN Grant scopes: sales:read, sales:quote, sales:order
```

### Critical: AI Agent Must Be Assigned

The AI Agent entity (`wlp...`) must be added to "Assigned clients" on each policy. This is the #1 cause of token exchange failures.

---

## Request Flow Example

**User**: Sarah Sales (ProGear-Sales group)
**Query**: "What basketballs do we have in stock?"

```
1. Sarah logs in via Okta
   └── Gets ID token from Org Authorization Server

2. Sarah sends query to backend

3. Orchestrator analyzes query
   └── Determines: needs Inventory Agent

4. Inventory Agent requests token exchange
   │
   ├── Step 1: ID Token → ID-JAG (at Org AS)
   │   └── SDK calls: POST /oauth2/v1/token
   │   └── Success: Agent can act on behalf of Sarah
   │
   └── Step 2: ID-JAG → Inventory Token (at Inventory Custom AS)
       └── SDK calls: POST /oauth2/{inventory_auth_server_id}/v1/token
       └── Okta checks: Is Sarah in a group that allows inventory:read?
       └── Yes (ProGear-Sales has inventory:read)
       └── Returns: Scoped access token

5. Inventory Agent uses token to query inventory data

6. Response returned to Sarah
```

**If Mike Manager (ProGear-Warehouse) asked about pricing:**

```
4. Pricing Agent requests token exchange
   │
   ├── Step 1: ID Token → ID-JAG (at Org AS)
   │   └── Success
   │
   └── Step 2: ID-JAG → Pricing Token (at Pricing Custom AS)
       └── Okta checks: Is Mike in a group that allows pricing:read?
       └── No (ProGear-Warehouse has no pricing access)
       └── Returns: access_denied

5. Pricing Agent returns "Access denied" (not an error)

6. Orchestrator responds without pricing data
```

---

## Security Model

### What the Agent Never Sees

- User's password
- User's session tokens
- Long-lived credentials

### What the Agent Gets

- Short-lived, scoped access tokens
- Only the scopes the user is authorized for
- Tokens that can be audited and revoked

### Audit Trail

Every token exchange is logged in Okta:
- Which agent requested access
- On behalf of which user
- To which authorization server
- Which scopes were granted or denied

---

## Further Reading

- [Implementation Guide](./implementation-guide.md) - Step-by-step deployment instructions
- [Okta AI Agent Documentation](https://developer.okta.com/docs/guides/ai-agent-governance/) - Official Okta docs
- [IETF ID-JAG Specification](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/) - Identity Assertion JWT Authorization Grant draft
