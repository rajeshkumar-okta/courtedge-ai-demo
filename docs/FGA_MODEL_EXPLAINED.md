# FGA Authorization Model Explained
## ProGear New Store - Complete Reference

---

## Model Overview

This FGA model implements **ReBAC + ABAC** (Relationship-Based Access Control with Attribute-Based conditions) for the ProGear Sales AI application. It demonstrates the "Okta + FGA Better Together" pattern.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FGA Model: ProGear New                                   │
│                                                                                 │
│   ┌──────────┐                                                                  │
│   │   user   │ ─────────────────────────────────────────────┐                  │
│   └──────────┘                                               │                  │
│        │                                                     │                  │
│        │ acts_for                                            │                  │
│        ▼                                                     │                  │
│   ┌──────────┐          ┌─────────────┐          ┌──────────────────┐          │
│   │  agent   │──────────│ delegation  │──────────│ inventory_system │          │
│   └──────────┘          └─────────────┘          └──────────────────┘          │
│                               │                          │                      │
│                               │                          │ parent               │
│                               │                          ▼                      │
│   ┌─────────────────┐         │               ┌──────────────────┐             │
│   │ clearance_level │─────────┴───────────────│  inventory_item  │             │
│   └─────────────────┘                         └──────────────────┘             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Type Definitions

### 1. `user` - Human Principals

```fga
type user
```

**Purpose:** Represents human users (employees, managers) who interact with the system.

**Example:** `user:bob.manager@atko.email`

**No relations defined** - users are referenced by other types.

---

### 2. `agent` - AI Agents

```fga
type agent
  relations
    define acts_for: [user]
```

**Purpose:** Represents AI agents that can act on behalf of users.

**Relations:**
| Relation | Type | Description |
|----------|------|-------------|
| `acts_for` | `[user]` | Which user this agent represents |

**Diagram:**
```
┌─────────────────────┐
│       agent         │
│  (AI Sales Agent)   │
├─────────────────────┤
│                     │
│  acts_for ──────────┼───► user:bob@atko.email
│                     │
└─────────────────────┘
```

---

### 3. `delegation` - Agent Delegation Records

```fga
type delegation
  relations
    define agent: [agent]
    define principal: [user]
```

**Purpose:** Links an agent to a user for delegation purposes. Used with the `agent_request_valid` condition.

**Relations:**
| Relation | Type | Description |
|----------|------|-------------|
| `agent` | `[agent]` | The AI agent being delegated to |
| `principal` | `[user]` | The user delegating authority |

**Diagram:**
```
┌─────────────────────────────────────────────────────────┐
│                      delegation                          │
│               (delegation:order-123)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  agent ─────────► agent:sales-bot                       │
│                                                          │
│  principal ─────► user:bob@atko.email                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

### 4. `clearance_level` - Hierarchical Clearance Tiers

```fga
type clearance_level
  relations
    define granted_to: [user]
    define holder: granted_to or holder from next_higher
    define next_higher: [clearance_level]
```

**Purpose:** Implements a hierarchical clearance system where higher levels include access to all lower levels.

**Relations:**
| Relation | Type | Description |
|----------|------|-------------|
| `granted_to` | `[user]` | Direct grant of this clearance level |
| `next_higher` | `[clearance_level]` | Points to the next higher level (chain) |
| `holder` | computed | Anyone with this level OR anyone holding higher levels |

**The Magic:** The `holder` relation uses **relationship traversal** (`holder from next_higher`) to walk up the hierarchy.

**Hierarchy Diagram:**
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CLEARANCE HIERARCHY                                     │
│                                                                                 │
│   Level 1        Level 2        Level 3        Level 4        Level 5          │
│  ┌───────┐      ┌───────┐      ┌───────┐      ┌───────┐      ┌───────┐         │
│  │   1   │◄─────│   2   │◄─────│   3   │◄─────│   4   │◄─────│   5   │  ...    │
│  └───────┘      └───────┘      └───────┘      └───────┘      └───────┘         │
│     ▲           next_higher    next_higher    next_higher    next_higher       │
│     │                                                              │            │
│     │                                                              │            │
│     │              User with Level 5 is a "holder" of              │            │
│     └──────────────────── levels 1, 2, 3, 4, 5 ────────────────────┘            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Example Tuples:**
```
clearance_level:1  next_higher  clearance_level:2
clearance_level:2  next_higher  clearance_level:3
clearance_level:3  next_higher  clearance_level:4
...
clearance_level:5  granted_to   user:bob@atko.email
```

**Query:** `check user:bob holder clearance_level:3` → **TRUE** (because Bob has level 5, which is higher)

---

### 5. `inventory_system` - Top-Level Resource Container

```fga
type inventory_system
  relations
    define manager: [user]
    define on_vacation: [user]
    define active_manager: manager but not on_vacation
    define can_manage: active_manager
    define active_delegation: [delegation with agent_request_valid]
    define delegated_principal: principal from active_delegation
    define can_manage_via_delegation: active_manager and delegated_principal
```

**Purpose:** Represents the inventory system (e.g., warehouse) and defines who can manage it.

**Relations:**

| Relation | Type | Description |
|----------|------|-------------|
| `manager` | `[user]` | Users assigned as managers (stored tuple) |
| `on_vacation` | `[user]` | Users currently on vacation (**contextual tuple**) |
| `active_manager` | computed | `manager but not on_vacation` |
| `can_manage` | computed | Same as `active_manager` |
| `active_delegation` | `[delegation]` | Active delegations with valid conditions |
| `delegated_principal` | computed | Principal from active delegation |
| `can_manage_via_delegation` | computed | For agent delegation scenarios |

**Key Concept: `active_manager`**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   active_manager = manager BUT NOT on_vacation                                 │
│                                                                                 │
│   ┌─────────────────┐                     ┌─────────────────┐                  │
│   │    manager      │         AND NOT     │   on_vacation   │                  │
│   │   (stored)      │                     │  (contextual)   │                  │
│   └─────────────────┘                     └─────────────────┘                  │
│           │                                       │                             │
│           │                                       │                             │
│           ▼                                       ▼                             │
│   ┌─────────────────────────────────────────────────────────────────────┐      │
│   │                                                                     │      │
│   │   Bob is manager=TRUE, vacation=FALSE  →  active_manager = TRUE    │      │
│   │   Bob is manager=TRUE, vacation=TRUE   →  active_manager = FALSE   │      │
│   │   Bob is manager=FALSE, vacation=FALSE →  active_manager = FALSE   │      │
│   │                                                                     │      │
│   └─────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 6. `inventory_item` - Individual Inventory Items

```fga
type inventory_item
  relations
    define parent: [inventory_system]
    define required_clearance: [clearance_level]
    define has_clearance: holder from required_clearance
    define can_view: can_manage from parent
    define can_update: has_clearance and can_manage from parent
    define can_view_via_delegation: can_manage_via_delegation from parent
    define can_update_via_delegation: has_clearance and can_manage_via_delegation from parent
```

**Purpose:** Represents individual inventory items with clearance requirements.

**Relations:**

| Relation | Type | Description |
|----------|------|-------------|
| `parent` | `[inventory_system]` | Which system this item belongs to |
| `required_clearance` | `[clearance_level]` | Minimum clearance needed to update |
| `has_clearance` | computed | User is holder of required_clearance |
| `can_view` | computed | `can_manage from parent` (walk to parent, check can_manage) |
| `can_update` | computed | `has_clearance AND can_manage from parent` |

**Permission Diagram:**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      inventory_item:widget-a                                    │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                          can_view                                        │  │
│   │                                                                          │  │
│   │   can_manage from parent                                                │  │
│   │          │                                                               │  │
│   │          ▼                                                               │  │
│   │   parent = inventory_system:warehouse                                   │  │
│   │          │                                                               │  │
│   │          ▼                                                               │  │
│   │   can_manage = active_manager                                           │  │
│   │          │                                                               │  │
│   │          ▼                                                               │  │
│   │   manager BUT NOT on_vacation                                           │  │
│   │                                                                          │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                          can_update                                      │  │
│   │                                                                          │  │
│   │   has_clearance AND can_manage from parent                              │  │
│   │        │                      │                                          │  │
│   │        │                      └──► (same as can_view)                   │  │
│   │        │                                                                 │  │
│   │        ▼                                                                 │  │
│   │   holder from required_clearance                                        │  │
│   │        │                                                                 │  │
│   │        ▼                                                                 │  │
│   │   required_clearance = clearance_level:3                                │  │
│   │        │                                                                 │  │
│   │        ▼                                                                 │  │
│   │   Does user hold level 3? (hierarchy check)                             │  │
│   │                                                                          │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Condition: `agent_request_valid`

```fga
condition agent_request_valid(
  budget_limit: int,
  current_time: timestamp,
  delegation_end: timestamp,
  delegation_purpose: string,
  delegation_start: timestamp,
  request_amount: int,
  request_purpose: string
) {
  current_time >= delegation_start &&
  current_time <= delegation_end &&
  request_purpose == delegation_purpose &&
  request_amount <= budget_limit
}
```

**Purpose:** CEL-based condition for validating agent delegation requests.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `budget_limit` | int | Maximum amount the agent can transact |
| `current_time` | timestamp | Current request time |
| `delegation_start` | timestamp | When delegation became active |
| `delegation_end` | timestamp | When delegation expires |
| `delegation_purpose` | string | Authorized purpose (e.g., "inventory_check") |
| `request_purpose` | string | Purpose of current request |
| `request_amount` | int | Amount requested |

**Evaluation:**
```
                        agent_request_valid
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    Time in range?     Purpose matches?    Within budget?
           │                  │                  │
           ▼                  ▼                  ▼
   start <= now <= end   req == del       amount <= limit
           │                  │                  │
           └──────────────────┼──────────────────┘
                              │
                              ▼
                       ALL must be TRUE
```

---

## Complete Permission Check Flow

### Example: `can user:bob can_update inventory_item:widget-a`

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   CHECK: user:bob.manager@atko.email can_update inventory_item:widget-a        │
│                                                                                 │
│   Step 1: Evaluate can_update                                                  │
│   ─────────────────────────────                                                │
│   can_update = has_clearance AND can_manage from parent                        │
│                     │                      │                                    │
│                     │                      │                                    │
│   Step 2: Check has_clearance              │                                    │
│   ───────────────────────────              │                                    │
│   has_clearance = holder from required_clearance                               │
│                          │                                                      │
│                          ▼                                                      │
│   required_clearance = clearance_level:3                                       │
│                          │                                                      │
│                          ▼                                                      │
│   Is bob a "holder" of clearance_level:3?                                      │
│                          │                                                      │
│                          ▼                                                      │
│   holder = granted_to OR holder from next_higher                               │
│                          │                                                      │
│                          ▼                                                      │
│   Bob has clearance_level:5 granted_to                                         │
│   Walk hierarchy: 5 → 4 → 3 ✓                                                  │
│                          │                                                      │
│                          ▼                                                      │
│   has_clearance = TRUE ✓                                                       │
│                                                                                 │
│   Step 3: Check can_manage from parent     │                                    │
│   ────────────────────────────────         │                                    │
│                                            ▼                                    │
│   parent = inventory_system:warehouse                                          │
│                          │                                                      │
│                          ▼                                                      │
│   can_manage = active_manager                                                  │
│                          │                                                      │
│                          ▼                                                      │
│   active_manager = manager BUT NOT on_vacation                                 │
│                          │                                                      │
│        ┌─────────────────┴─────────────────┐                                   │
│        │                                   │                                    │
│        ▼                                   ▼                                    │
│   manager tuple exists?           on_vacation tuple exists?                    │
│   bob → manager → warehouse       bob → on_vacation → warehouse                │
│        │                                   │                                    │
│        ▼                                   ▼                                    │
│   YES (stored tuple)              NO (no contextual tuple)                     │
│        │                                   │                                    │
│        └─────────────────┬─────────────────┘                                   │
│                          │                                                      │
│                          ▼                                                      │
│   active_manager = TRUE ✓                                                      │
│                                                                                 │
│   Step 4: Final Result                                                         │
│   ────────────────────                                                         │
│   can_update = has_clearance AND can_manage from parent                        │
│              = TRUE AND TRUE                                                    │
│              = TRUE ✓                                                          │
│                                                                                 │
│   ═══════════════════════════════════════════════════════════════════════════  │
│   RESULT: ALLOWED                                                              │
│   ═══════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Tuple Summary

### Stored Tuples (Persistent)

| Object | Relation | User/Object | Description |
|--------|----------|-------------|-------------|
| `inventory_system:warehouse` | `manager` | `user:bob@...` | Bob is a manager |
| `clearance_level:5` | `granted_to` | `user:bob@...` | Bob has level 5 |
| `clearance_level:1` | `next_higher` | `clearance_level:2` | Hierarchy chain |
| `inventory_item:widget-a` | `parent` | `inventory_system:warehouse` | Item belongs to warehouse |
| `inventory_item:widget-a` | `required_clearance` | `clearance_level:3` | Item requires level 3 |

### Contextual Tuples (Per-Request)

| Object | Relation | User | When Passed |
|--------|----------|------|-------------|
| `inventory_system:warehouse` | `on_vacation` | `user:bob@...` | If Okta Vacation=true |

---

## Permission Matrix

| User State | can_view | can_update (level 3 item) | can_update (level 7 item) |
|------------|----------|---------------------------|---------------------------|
| Manager=true, Vacation=false, Clearance=5 | ✓ | ✓ | ✗ |
| Manager=true, Vacation=false, Clearance=2 | ✓ | ✗ | ✗ |
| Manager=true, Vacation=true, Clearance=10 | ✗ | ✗ | ✗ |
| Manager=false, Vacation=false, Clearance=10 | ✗ | ✗ | ✗ |

---

## Key Design Patterns

### 1. Exclusion Pattern (`but not`)
```fga
active_manager: manager but not on_vacation
```
Use for temporary exclusions (vacation, suspension, etc.)

### 2. Hierarchy Pattern (`holder from next_higher`)
```fga
holder: granted_to or holder from next_higher
```
Use for tiered access levels, org hierarchies

### 3. Parent Traversal (`from parent`)
```fga
can_view: can_manage from parent
```
Use for inheriting permissions from container objects

### 4. Compound Permissions (`and`)
```fga
can_update: has_clearance and can_manage from parent
```
Use when multiple conditions must be met

### 5. Conditional Tuples (`with condition`)
```fga
active_delegation: [delegation with agent_request_valid]
```
Use for time-bound, budget-limited, or context-sensitive access
