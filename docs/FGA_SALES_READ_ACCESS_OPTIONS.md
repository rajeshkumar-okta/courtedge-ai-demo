# FGA Sales Read Access - Design Options

## Problem Statement

Users with `Manager=false` but with a sales role cannot read inventory because the current FGA model requires:
```
can_view → can_manage from parent → active_manager → manager
```

**Requirement:** Allow sales role users (non-managers) to READ inventory while maintaining FGA control for WRITE operations.

---

## Option 1: Skip FGA for Read Operations (Simplest)

### Description
Only run FGA check for `inventory:write`, not `inventory:read`. Rely on Okta RBAC/scopes for read access control.

### Logic Flow
```
inventory:read  → No FGA check (Okta RBAC/scopes only)
inventory:write → FGA check: can_update (manager + clearance)
```

### Changes Required

**File:** `backend/auth/fga_client.py`
```python
# In check_agent_access()
# Add early return for read operations
if "inventory:read" in scopes and "inventory:write" not in scopes:
    return FGACheckResult(
        allowed=True,
        relation="n/a",
        reason="Read operations use Okta RBAC only",
        ...
    )
```

### Pros
- No FGA model changes needed
- Simple code change (5-10 lines)
- Okta scopes already control who can read
- Fast to implement

### Cons
- Less granular control over read access
- No FGA audit trail for read operations
- Doesn't demonstrate full FGA capabilities

### Best For
- Quick demos
- When Okta RBAC is sufficient for read access

---

## Option 2: Add "viewer" Relation to FGA Model (Recommended for Production)

### Description
Update FGA model to add a `viewer` relation that allows read access without requiring manager status.

### FGA Model Changes
```fga
type inventory_system
  relations
    define viewer: [user]                              # NEW
    define manager: [user]
    define on_vacation: [user]
    define active_manager: manager but not on_vacation
    define active_viewer: viewer but not on_vacation   # NEW
    define can_manage: active_manager
    define can_read: active_manager or active_viewer   # NEW

type inventory_item
  relations
    define can_view: can_read from parent              # CHANGED (was: can_manage from parent)
    define can_update: has_clearance and can_manage from parent
```

### Backend Changes

**File:** `backend/auth/fga_client.py`

Add functions:
```python
async def check_viewer_tuple_exists(user_email, system_id="warehouse") -> bool
async def write_viewer_tuple(user_email, system_id="warehouse") -> bool
async def delete_viewer_tuple(user_email, system_id="warehouse") -> bool
async def ensure_viewer_relationship(user_email, is_viewer, system_id="warehouse") -> dict
```

**File:** `backend/orchestrator/orchestrator.py`

Add viewer tuple management:
```python
# Determine if user should be a viewer (e.g., from Okta claim or group)
is_viewer = # logic to determine viewer status

# Ensure viewer tuple
viewer_result = await ensure_viewer_relationship(user_email, is_viewer)
```

### Tuple Examples
```
user:sarah.sales@atko.email  viewer  inventory_system:warehouse
```

### Permission Matrix After Change

| User State | can_view | can_update |
|------------|----------|------------|
| Manager=true, Vacation=false | ✓ | ✓ (with clearance) |
| Manager=false, Viewer=true, Vacation=false | ✓ | ✗ |
| Manager=false, Viewer=false | ✗ | ✗ |
| Any, Vacation=true | ✗ | ✗ |

### Pros
- Full FGA control over who can read
- Complete audit trail for all operations
- Demonstrates full FGA capabilities
- Vacation still blocks viewers (consistent policy)

### Cons
- Requires FGA model change (need to redeploy model)
- More tuples to manage
- Need to determine viewer status (claim, group, or manual)

### Best For
- Production deployments
- Full governance requirements
- Demonstrating "Okta + FGA Better Together"

---

## Option 3: Add "Sales" Claim to Okta + Dynamic Tuple

### Description
Add a `Sales` claim from Okta Custom Auth Server, create viewer tuples dynamically based on the claim.

### Okta Setup
1. Go to Okta Admin → Security → API → Inventory Auth Server
2. Add claim:
   - Name: `Sales`
   - Include in: Access Token
   - Value type: Expression
   - Value: `user.isSales` or `Groups.contains("Sales")`

### FGA Model Changes
Same as Option 2

### Backend Changes
```python
# Extract Sales claim from Access Token
sales_claim = auth_token_claims.get("Sales", False)

# Ensure viewer tuple based on Sales claim
await ensure_viewer_relationship(user_email, is_viewer=sales_claim)
```

### Pros
- Claims-driven, consistent with Manager/Vacation/Clearance pattern
- Dynamic tuple management (same pattern as existing code)
- Single source of truth (Okta profile)

### Cons
- Requires Okta Auth Server claim setup
- Requires FGA model change
- Another claim to manage in Okta

### Best For
- When sales role is defined in Okta user profile
- Consistent claim-driven architecture

---

## Option 4: Use Okta Groups in FGA (Most Flexible)

### Description
Reference Okta groups directly in FGA using usersets. Map group membership to FGA relations.

### FGA Model Changes
```fga
type group
  relations
    define member: [user]

type inventory_system
  relations
    define viewer: [group#member]  # Anyone in the group can view
    define manager: [user]
    define on_vacation: [user]
    define active_manager: manager but not on_vacation
    define can_manage: active_manager
    define can_read: active_manager or viewer
```

### Tuple Examples
```
# One-time setup: link group to viewer relation
inventory_system:warehouse  viewer  group:sales-team#member

# Per-user: add to group (or sync from Okta)
group:sales-team  member  user:sarah.sales@atko.email
group:sales-team  member  user:john.sales@atko.email
```

### Backend Changes
- Sync Okta group membership to FGA group tuples
- Or manually manage group membership in FGA

### Pros
- Maps naturally to Okta groups
- One tuple grants access to entire group
- Scales well (add user to group, not individual tuples)

### Cons
- Most complex to implement
- Need to sync Okta groups to FGA (or manage separately)
- Requires understanding of usersets

### Best For
- Large organizations with established group structure
- When access is group-based, not individual

---

## Comparison Matrix

| Criteria | Option 1 | Option 2 | Option 3 | Option 4 |
|----------|----------|----------|----------|----------|
| Implementation Time | 30 min | 2-3 hrs | 3-4 hrs | 4-6 hrs |
| FGA Model Change | No | Yes | Yes | Yes |
| Okta Change | No | No | Yes | No |
| Audit Trail | Partial | Full | Full | Full |
| Scalability | Good | Good | Good | Best |
| Complexity | Low | Medium | Medium | High |
| Demo Value | Low | High | High | Highest |

---

## Recommendation Summary

| Scenario | Recommended Option |
|----------|-------------------|
| Quick fix / Demo | Option 1 |
| Production with full audit | **Option 2** |
| Consistent with existing claims pattern | Option 3 |
| Large org with group-based access | Option 4 |

---

## Implementation Notes

### For Option 2 (Selected)

1. **Update FGA Model** via CLI or FGA dashboard
2. **Add viewer tuple management** functions to `fga_client.py`
3. **Determine viewer status** - options:
   - Hardcode for demo (if user has inventory:read scope but not manager, make viewer)
   - Add a claim (becomes Option 3)
   - Check Okta group membership
4. **Update orchestrator** to call `ensure_viewer_relationship()`
5. **Test** with sarah.sales@atko.email

### Viewer Status Logic (Simple Approach for Demo)
```python
# If user has inventory scope but is not a manager, make them a viewer
is_viewer = not is_manager and "inventory" in requested_agents
```

This ensures:
- Managers are not also viewers (redundant)
- Non-managers who need inventory access get viewer status
- Vacation still blocks both managers and viewers
