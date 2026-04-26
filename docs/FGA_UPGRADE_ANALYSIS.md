# FGA Model Upgrade Analysis

## Source Reference
Analysis based on: `/Users/rajeshkumar/Documents/AI/workspace/o4aa-fga-example-main`

---

## Current State (CourtEdge Demo)

### Current FGA Model
```fga
type user

type inventory_system
  relations
    define manager: [user]
    define on_vacation: [user]
    define can_increase_inventory: manager but not on_vacation
```

### Current Okta Claims
| Claim | Okta Attribute | Purpose |
|-------|----------------|---------|
| `Manager` | `user.is_a_manager` | Dynamic manager tuple creation |
| `Vacation` | `user.is_on_vacation` | Contextual tuple for vacation check |

### Current Scope-Based Logic
| Scope | FGA Check |
|-------|-----------|
| `inventory:read` | No FGA check (always allowed) |
| `inventory:write` | FGA check (`can_increase_inventory`) |
| `inventory:alert` | No FGA check (always allowed) |

### Current Issues
- Manager tuple write fails with 403 (FGA client lacks write permissions)
- Simple model doesn't support clearance levels or agent delegation

---

## New Model (from o4aa-fga-example-main)

### Model Overview

The new model combines **ReBAC** (Relationship-Based Access Control) with **ABAC** (Attribute-Based Access Control).

```
user ──manager──► inventory_system ──parent──► inventory_item
                        │                           │
                   on_vacation                required_clearance
                   (but not)                        │
                        │                    clearance_level
                  active_delegation          (chained hierarchy)
                        │
                   delegation ──principal──► user
                        │
                      agent
```

### Types

| Type | Purpose |
|------|---------|
| `user` | Human principals (managers) |
| `agent` | AI/software agents that act on behalf of users |
| `delegation` | Binds an agent to a principal with time/purpose/budget constraints |
| `clearance_level` | Discrete clearance tiers forming a chain (level 5 subsumes levels 1-4) |
| `inventory_system` | Top-level resource (e.g., a warehouse) |
| `inventory_item` | Individual items, children of a system |

### Full FGA Model (DSL)

```fga
model
  schema 1.1

type user

type agent
  relations
    define acts_for: [user]

type delegation
  relations
    define agent: [agent]
    define principal: [user]

type clearance_level
  relations
    define next_higher: [clearance_level]
    define granted_to: [user]
    define holder: granted_to or holder from next_higher

type inventory_system
  relations
    define manager: [user]
    define on_vacation: [user]
    define active_manager: manager but not on_vacation
    define active_delegation: [delegation with agent_request_valid]
    define delegated_principal: principal from active_delegation
    define can_manage: active_manager
    define can_manage_via_delegation: active_manager and delegated_principal

type inventory_item
  relations
    define parent: [inventory_system]
    define required_clearance: [clearance_level]
    define has_clearance: holder from required_clearance
    define can_view: can_manage from parent
    define can_update: has_clearance and can_manage from parent
    define can_view_via_delegation: can_manage_via_delegation from parent
    define can_update_via_delegation: has_clearance and can_manage_via_delegation from parent

condition agent_request_valid(current_time: timestamp, delegation_start: timestamp, delegation_end: timestamp, request_purpose: string, delegation_purpose: string, request_amount: int, budget_limit: int) {
  current_time >= delegation_start && current_time <= delegation_end && request_purpose == delegation_purpose && request_amount <= budget_limit
}
```

---

## Key Features of New Model

### 1. Vacation Exclusion (but not)
```fga
define active_manager: manager but not on_vacation
```
- Application reads vacation status from Okta at request time
- Sends `on_vacation` as **contextual tuple** when user is on vacation
- No data sync needed - evaluated per request

### 2. Clearance Level Hierarchy
```fga
type clearance_level
  relations
    define next_higher: [clearance_level]
    define granted_to: [user]
    define holder: granted_to or holder from next_higher
```
- Levels form a chain: `level:2 → level:1`, `level:3 → level:2`, etc.
- User with clearance 5 passes level-3 check but fails level-7 check
- No numeric comparison needed - hierarchy encodes "greater than or equal" structurally

### 3. Agent Delegation with CEL Condition
```fga
condition agent_request_valid(
  current_time: timestamp,        # from check context (request time)
  delegation_start: timestamp,    # from tuple context (stored)
  delegation_end: timestamp,      # from tuple context (stored)
  request_purpose: string,        # from check context (request)
  delegation_purpose: string,     # from tuple context (stored)
  request_amount: int,            # from check context (request)
  budget_limit: int               # from tuple context (stored)
)
```
- Time window, purpose match, and budget ceiling evaluated at runtime
- Each delegation is a unique object (allows multiple envelopes per agent)

---

## Permission Matrix

| Permission | Requirements | Use Case |
|------------|--------------|----------|
| `can_view` | `active_manager` (manager + not on vacation) | View inventory items |
| `can_update` | `active_manager` + `has_clearance` | Modify inventory (clearance required) |
| `can_view_via_delegation` | `active_manager` + valid delegation | Agent views on behalf of user |
| `can_update_via_delegation` | `active_manager` + `has_clearance` + valid delegation | Agent modifies on behalf of user |

---

## Use Cases Covered

### Use Case 1: Manager Checks Inventory
- Pure ReBAC
- Manager tuple acts as role binding
- No vacation tuple = access granted

### Use Case 2: Vacation Blocks Manager
- ReBAC + ABAC
- Vacation status from Okta sent as contextual tuple
- `manager but not on_vacation` excludes user

### Use Case 3: Clearance Blocks High-Sensitivity Item
- ReBAC + ABAC
- Clearance hierarchy walk at query time
- User with clearance 5 cannot update item requiring clearance 7

### Use Case 4: Agent Acts Within Delegation Envelope
- ReBAC + ABAC
- Time window, purpose, budget all checked via CEL condition
- Multiple delegations possible for same agent

### Use Case 5: Agent Exceeds Budget
- ABAC decides
- ReBAC chain valid, but budget ceiling fails
- Direct user access still works

### Use Case 6: Vacation Blocks Agent Too
- Delegation valid, agent conditions pass
- Principal's vacation status flows through `active_manager` check
- Vacation attribute propagates denial through ReBAC chain

---

## Required Okta Configuration

### User Profile Attributes (Directory → Profile Editor → Okta User)

| Attribute | Variable Name | Type | Description |
|-----------|---------------|------|-------------|
| Is Manager | `is_a_manager` | boolean | User has manager role |
| Is On Vacation | `is_on_vacation` | boolean | User is currently on vacation |
| Clearance Level | `clearance_level` | integer | User's clearance level (1-10) |

### Custom Auth Server Claims (Security → API → Authorization Servers)

| Claim Name | Include in | Value Type | Value (Expression) | Include in Scope |
|------------|------------|------------|-------------------|------------------|
| `Manager` | Access Token | Expression | `user.is_a_manager` | Any scope |
| `Vacation` | Access Token | Expression | `user.is_on_vacation` | Any scope |
| `Clearance` | Access Token | Expression | `user.clearance_level` | Any scope |

---

## Required FGA Tuples (Pre-seeded)

### 1. Clearance Level Chain (One-time Setup)
```yaml
- user: clearance_level:2
  relation: next_higher
  object: clearance_level:1
- user: clearance_level:3
  relation: next_higher
  object: clearance_level:2
# ... continue to level 10
```

### 2. Inventory Hierarchy
```yaml
# widget-a belongs to warehouse, requires clearance 3
- user: inventory_system:warehouse
  relation: parent
  object: inventory_item:widget-a
- user: clearance_level:3
  relation: required_clearance
  object: inventory_item:widget-a

# classified-part requires clearance 7
- user: inventory_system:warehouse
  relation: parent
  object: inventory_item:classified-part
- user: clearance_level:7
  relation: required_clearance
  object: inventory_item:classified-part
```

### 3. User Setup (Dynamic or Pre-seeded)
```yaml
# Manager role binding
- user: user:bob.manager@atko.email
  relation: manager
  object: inventory_system:warehouse

# User clearance grant
- user: user:bob.manager@atko.email
  relation: granted_to
  object: clearance_level:5
```

### 4. Agent Delegation (If Using Agents)
```yaml
# Agent acts for user
- user: user:alice
  relation: acts_for
  object: agent:bot-1

# Delegation envelope
- user: agent:bot-1
  relation: agent
  object: delegation:alice-bot1-june-restock
- user: user:alice
  relation: principal
  object: delegation:alice-bot1-june-restock
- user: delegation:alice-bot1-june-restock
  relation: active_delegation
  object: inventory_system:warehouse
  condition:
    name: agent_request_valid
    context:
      delegation_start: "2024-06-01T00:00:00Z"
      delegation_end: "2024-06-30T23:59:59Z"
      delegation_purpose: "restock"
      budget_limit: 10000
```

---

## Scope to Permission Mapping

| Okta Scope | FGA Permission | Contextual Data Needed |
|------------|----------------|------------------------|
| `inventory:read` | `can_view` | `on_vacation` (if true) |
| `inventory:write` | `can_update` | `on_vacation` (if true), clearance check |
| `inventory:alert` | `can_view` | `on_vacation` (if true) |

---

## Code Changes Required

### 1. `backend/auth/fga_client.py`
- Update FGA model reference in docstring
- Add clearance check logic
- Update `check_agent_access()` to use new permissions
- Add `check_clearance()` function
- Update contextual tuple logic

### 2. `backend/orchestrator/orchestrator.py`
- Extract `Clearance` claim from access token
- Map scopes to FGA permissions (`can_view`, `can_update`)
- Pass clearance level to FGA check
- Update FGA check node logic

### 3. `backend/api/main.py`
- Extract `Clearance` claim alongside `Manager` and `Vacation`
- Pass to user_info

### 4. `backend/auth/fga_seed.py`
- Update to seed clearance chain
- Update to seed inventory items with required_clearance

---

## Decision Points

### 1. Scope of Implementation
- **Minimal**: Just fix current model (manager + vacation)
- **Medium**: Add clearance levels (no agent delegation)
- **Full**: Complete model with agent delegation

### 2. FGA Store
- **Update existing**: Modify current FGA store/model
- **Create new**: Fresh FGA store with new model

### 3. Tuple Management
- **Dynamic**: Create tuples from Okta claims at runtime
- **Pre-seeded**: Admin seeds tuples, Okta provides contextual data only
- **Hybrid**: Manager/clearance from claims, vacation as contextual

### 4. Clearance Source
- **From Okta claim**: `Clearance` claim in access token
- **Pre-seeded in FGA**: Sync user clearance to FGA tuples

---

## Next Steps (Awaiting Instructions)

1. Confirm scope of implementation (minimal/medium/full)
2. Confirm FGA store approach (update/new)
3. Confirm tuple management strategy
4. Add required Okta attributes and claims
5. Update/create FGA model
6. Seed required tuples
7. Update CourtEdge code
8. Test end-to-end

---

*Analysis created: 2026-04-26*
*Source: o4aa-fga-example-main*
