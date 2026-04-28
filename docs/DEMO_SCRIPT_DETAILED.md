# ProGear Sales AI Demo Script
## Okta + Auth0 FGA: Better Together

---

## Introduction (30 seconds)

**Opening Statement:**
> "Today I'll demonstrate how Okta's identity platform combines with Auth0 Fine-Grained Authorization (FGA) to provide complete governance for AI agent operations. We'll see how identity claims from Okta flow into relationship-based authorization decisions in real-time."

**Key Value Proposition:**
- **Okta** handles: Identity, Authentication, Coarse-grained RBAC (groups), Custom Claims
- **FGA** handles: Fine-grained permissions, Relationship hierarchies, Contextual conditions

---

## The Demo Application: ProGear Sales AI

**What it does:**
ProGear is a sporting goods company with an AI-powered sales assistant. Sales reps can:
- Check inventory levels
- Update stock quantities
- Get pricing information
- Access customer data

**Why FGA matters:**
Not all managers should have the same access. A manager on vacation shouldn't modify inventory. A manager with low clearance shouldn't update sensitive items. FGA enforces these rules dynamically.

---

## Architecture Overview (1 minute)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Okta      │     │   Backend   │     │  Auth0 FGA  │
│             │     │             │     │             │
│ • Identity  │────▶│ • Extract   │────▶│ • Check     │
│ • Claims    │     │   Claims    │     │   Relations │
│ • Tokens    │     │ • Manage    │     │ • Evaluate  │
│             │     │   Tuples    │     │   Conditions│
└─────────────┘     └─────────────┘     └─────────────┘

Claims Flow:
┌────────────────────────────────────────────────────┐
│ Okta Custom Auth Server (Inventory)                │
│                                                    │
│ Claims:                                            │
│   • Manager (user.is_a_manager) ──▶ FGA Tuple     │
│   • Vacation (user.is_on_vacation) ──▶ Contextual │
│   • Clearance (user.clearance_level) ──▶ FGA Tuple│
└────────────────────────────────────────────────────┘
```

**Key Concepts:**
1. **Stored Tuples**: Manager and Clearance relationships are stored in FGA
2. **Contextual Tuples**: Vacation status is passed per-request (not stored)
3. **Hierarchy**: Clearance level 5 automatically grants access to items requiring level 3 or lower

---

## FGA Authorization Model

```
type inventory_item
  relations
    can_view: can_manage from parent
    can_update: has_clearance AND can_manage from parent

type inventory_system
  relations
    active_manager: manager but not on_vacation
    can_manage: active_manager

type clearance_level
  relations
    holder: granted_to or holder from next_higher  ← Hierarchy!
```

**Permission Matrix:**

| Operation | FGA Permission | Requirements |
|-----------|---------------|--------------|
| View Inventory | `can_view` | Active manager (not on vacation) |
| Update Inventory | `can_update` | Active manager + Sufficient clearance |
| Alerts | None | Okta RBAC only |

---

## Demo User: Bob

| Profile Field | Okta Attribute | What it Controls |
|--------------|----------------|------------------|
| Manager | `user.is_a_manager` | FGA manager tuple |
| Vacation | `user.is_on_vacation` | Contextual denial |
| Clearance | `user.clearance_level` | FGA clearance tuple |

**Inventory Items:**
| Item | Required Clearance | Description |
|------|-------------------|-------------|
| widget-a | 3 | Standard inventory item |
| classified-part | 7 | Sensitive military contract item |

---

## Live Demo Scenarios

### Demo 1: Successful View (Baseline)

**Setup in Okta:**
```
Manager:   true
Vacation:  false
Clearance: 5
```

**Prompt:** "How many basketballs do we have in stock?"

**What Happens:**
1. Okta authenticates Bob, issues ID-JAG token
2. Backend exchanges for Inventory Auth Server token
3. Claims extracted: Manager=true, Vacation=false, Clearance=5
4. FGA check: `can_view` on `inventory_item:widget-a`
5. Result: **ALLOWED** (active manager, not on vacation)

**UI Shows:**
- Green agent flow
- FGA section: Manager ✓, Vacation ✓, Clearance 5
- "Access Allowed: Active manager (not on vacation)"

---

### Demo 2: Successful Update (With Clearance)

**Setup in Okta:** (same as Demo 1)
```
Manager:   true
Vacation:  false
Clearance: 5
```

**Prompt:** "Add 50 basketballs to inventory"

**What Happens:**
1. Router detects "add" → requests `inventory:write` scope
2. FGA check: `can_update` on `inventory_item:widget-a`
3. Clearance check: User has 5, item requires 3
4. Result: **ALLOWED** (active manager + clearance 5 ≥ 3)

**UI Shows:**
- Green agent flow
- "Active manager with clearance 5 (item needs 3)"

**Key Point:** 
> "Notice the clearance hierarchy - Bob has level 5, which automatically grants access to any item requiring level 5 or below. This is ReBAC in action."

---

### Demo 3: Vacation Blocks Everything

**Setup in Okta:**
```
Manager:   true
Vacation:  true  ← CHANGED
Clearance: 5
```

**Prompt:** "How many basketballs do we have in stock?"

**What Happens:**
1. Claims extracted: Manager=true, **Vacation=true**, Clearance=5
2. Backend passes `on_vacation` as **contextual tuple**
3. FGA evaluates: `active_manager = manager but not on_vacation`
4. Result: **DENIED** (vacation blocks active_manager)

**UI Shows:**
- RED agent flow
- FGA section: Manager ✓, Vacation ⚠ (orange)
- "Vacation blocks access - active_manager requires NOT on_vacation"
- Contextual tuple: `on_vacation (per-request)`

**Key Point:**
> "This is the power of contextual tuples. Vacation status isn't stored in FGA - it's passed with each request. This means the moment Bob returns from vacation and updates his Okta profile, access is immediately restored without any FGA changes."

---

### Demo 4: Insufficient Clearance

**Setup in Okta:**
```
Manager:   true
Vacation:  false
Clearance: 2  ← CHANGED (lowered)
```

**Prompt:** "Update the classified-part quantity to 100"

**What Happens:**
1. Router detects "update classified" → `inventory:write` scope
2. FGA check: `can_update` on `inventory_item:classified-part`
3. Clearance check: User has 2, **item requires 7**
4. Result: **DENIED** (clearance insufficient)

**UI Shows:**
- RED agent flow
- FGA section: Clearance 2 (yellow warning), Item needs 7
- "Insufficient clearance - level 2 < required 7"

**Key Point:**
> "Bob can still VIEW inventory, but cannot UPDATE sensitive items. This is the 'has_clearance AND can_manage' rule in action - both conditions must be true for write operations."

---

### Demo 5: View Still Works with Low Clearance

**Setup in Okta:** (same as Demo 4)
```
Manager:   true
Vacation:  false
Clearance: 2
```

**Prompt:** "What classified parts do we have?"

**What Happens:**
1. Router detects read operation → `inventory:read` scope
2. FGA check: `can_view` (not `can_update`)
3. `can_view` only requires `active_manager`
4. Result: **ALLOWED** (clearance not checked for view)

**UI Shows:**
- Green agent flow
- "Access Allowed: Active manager (not on vacation)"

**Key Point:**
> "Notice that clearance only applies to UPDATE operations. Bob can see that classified parts exist, but cannot modify them. This is a common pattern - visibility vs modification rights."

---

### Demo 6: Non-Manager Access

**Setup in Okta:**
```
Manager:   false  ← CHANGED
Vacation:  false
Clearance: 10
```

**Prompt:** "How many basketballs do we have?"

**What Happens:**
1. Claims extracted: **Manager=false**
2. Backend calls `ensure_manager_relationship()` → **deletes** manager tuple
3. FGA check: No manager relationship exists
4. Result: **DENIED** (not a manager)

**UI Shows:**
- RED agent flow
- FGA section: Manager ✗ (red)
- "Not a manager - no manager relationship in FGA"
- Stored tuples: none for manager

**Key Point:**
> "Even with maximum clearance (level 10), Bob cannot access inventory without the manager role. This shows how Okta claims drive FGA relationships dynamically."

---

## Summary Slide

| Scenario | Manager | Vacation | Clearance | Action | Result |
|----------|---------|----------|-----------|--------|--------|
| 1. View baseline | ✓ | ✗ | 5 | View | ✓ Allowed |
| 2. Update with clearance | ✓ | ✗ | 5 | Update | ✓ Allowed |
| 3. On vacation | ✓ | ✓ | 5 | View | ✗ Denied |
| 4. Low clearance | ✓ | ✗ | 2 | Update classified | ✗ Denied |
| 5. View with low clearance | ✓ | ✗ | 2 | View | ✓ Allowed |
| 6. Not a manager | ✗ | ✗ | 10 | View | ✗ Denied |

---

## Key Takeaways

### 1. Dynamic Authorization
> "FGA tuples are managed dynamically based on Okta claims. When Bob's role changes in Okta, his FGA relationships update automatically on the next request."

### 2. Contextual Conditions
> "Vacation status is a contextual tuple - not stored, just passed per-request. This provides real-time condition evaluation without data synchronization."

### 3. Hierarchical Access
> "Clearance levels use FGA's relationship traversal. Level 7 automatically includes levels 1-6. No need to grant each level separately."

### 4. Separation of Concerns
> "Okta answers 'Who is this?' and 'What groups are they in?' FGA answers 'Can they do THIS specific action on THIS specific resource?'"

### 5. Audit Trail
> "Every FGA check is logged with full context - who, what, when, and why allowed/denied. This provides complete governance visibility."

---

## Q&A Prompts

**If asked about performance:**
> "FGA checks add ~10-50ms latency. The SDK handles connection pooling and caching. For high-throughput scenarios, batch checks are available."

**If asked about sync:**
> "We use a 'just-in-time' sync pattern. Claims are read from Okta tokens, and FGA tuples are created/updated on each request. No background sync jobs needed."

**If asked about scale:**
> "Auth0 FGA is built on Google Zanzibar principles. It scales to billions of relationships with consistent sub-100ms response times."

---

## Reset for Next Demo

After the demo, reset Bob's profile to baseline:
```
Manager:   true
Vacation:  false
Clearance: 5
```

This ensures the next demo starts with a working state.
