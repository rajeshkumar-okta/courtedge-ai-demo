# Complete FGA Test Matrix - All Parameter Combinations

## Bob's Current Profile
- Email: `bob.manager@atko.email`
- Manager: ✅ **true**
- Vacation: ✅ **true**
- Clearance: **2**

---

## Test Parameters

### Three Variables
| Parameter | Possible Values |
|-----------|-----------------|
| **Manager** | true, false |
| **Vacation** | true, false |
| **Clearance** | 2, 3, 5, 7 |

### Test Actions
| Action | Scope | FGA Permission | Item |
|--------|-------|----------------|------|
| View basketballs | `inventory:read` | `can_view` | widget-a (req clearance 3) |
| Update basketballs | `inventory:write` | `can_update` | widget-a (req clearance 3) |
| View Pro Arena Hoop | `inventory:read` | `can_view` | classified-part (req clearance 7) |
| Update Pro Arena Hoop | `inventory:write` | `can_update` | classified-part (req clearance 7) |

---

## Complete Test Matrix (32 combinations)

### Legend
- ✅ **PASS** - Access granted
- ❌ **FAIL** - Access denied
- 🔴 **Block reason** shown in last column

---

## Group 1: Manager=TRUE, Vacation=FALSE (Active Manager)

| Test | Clearance | Action | Item | Expected | Block Reason | FGA Logic |
|------|-----------|--------|------|----------|--------------|-----------|
| 1.1 | 2 | View | widget-a | ❌ FAIL | Clearance N/A for view BUT clearance 2 user may not be seeded | active_manager ✅, but if clearance tuple missing → may fail |
| 1.2 | 2 | Update | widget-a | ❌ FAIL | 🔴 Clearance (2 < 3) | has_clearance: holder(3) doesn't include clearance 2 |
| 1.3 | 2 | View | classified-part | ❌ FAIL | Same as 1.1 | active_manager ✅, clearance not checked for view |
| 1.4 | 2 | Update | classified-part | ❌ FAIL | 🔴 Clearance (2 < 7) | has_clearance: holder(7) doesn't include clearance 2 |
| 1.5 | 3 | View | widget-a | ✅ PASS | - | active_manager ✅, can_manage ✅ |
| 1.6 | 3 | Update | widget-a | ✅ PASS | - | has_clearance(3) ✅, active_manager ✅ |
| 1.7 | 3 | View | classified-part | ✅ PASS | - | active_manager ✅ (view doesn't check clearance) |
| 1.8 | 3 | Update | classified-part | ❌ FAIL | 🔴 Clearance (3 < 7) | has_clearance: holder(7) doesn't include clearance 3 |
| 1.9 | 5 | View | widget-a | ✅ PASS | - | active_manager ✅ |
| 1.10 | 5 | Update | widget-a | ✅ PASS | - | has_clearance(3): holder includes 5 ✅, active_manager ✅ |
| 1.11 | 5 | View | classified-part | ✅ PASS | - | active_manager ✅ |
| 1.12 | 5 | Update | classified-part | ❌ FAIL | 🔴 Clearance (5 < 7) | has_clearance: holder(7) doesn't include clearance 5 |
| 1.13 | 7 | View | widget-a | ✅ PASS | - | active_manager ✅ |
| 1.14 | 7 | Update | widget-a | ✅ PASS | - | has_clearance(3): holder includes 7 ✅ |
| 1.15 | 7 | View | classified-part | ✅ PASS | - | active_manager ✅ |
| 1.16 | 7 | Update | classified-part | ✅ PASS | - | has_clearance(7): holder includes 7 ✅, active_manager ✅ |

---

## Group 2: Manager=TRUE, Vacation=TRUE (Manager on Vacation)

| Test | Clearance | Action | Item | Expected | Block Reason | FGA Logic |
|------|-----------|--------|------|----------|--------------|-----------|
| 2.1 | 2 | View | widget-a | ❌ FAIL | 🔴 Vacation | active_manager: manager but not on_vacation = {} (EMPTY) |
| 2.2 | 2 | Update | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} (vacation blocks before clearance check) |
| 2.3 | 2 | View | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.4 | 2 | Update | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.5 | 3 | View | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.6 | 3 | Update | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} (vacation blocks even though clearance OK) |
| 2.7 | 3 | View | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.8 | 3 | Update | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.9 | 5 | View | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.10 | 5 | Update | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.11 | 5 | View | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.12 | 5 | Update | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.13 | 7 | View | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.14 | 7 | Update | widget-a | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.15 | 7 | View | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |
| 2.16 | 7 | Update | classified-part | ❌ FAIL | 🔴 Vacation | active_manager = {} |

**Key Insight:** Vacation blocks EVERYTHING when Manager=true + Vacation=true (regardless of clearance)

---

## Group 3: Manager=FALSE, Vacation=FALSE (Not a Manager)

| Test | Clearance | Action | Item | Expected | Block Reason | FGA Logic |
|------|-----------|--------|------|----------|--------------|-----------|
| 3.1 | 2 | View | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist in FGA |
| 3.2 | 2 | Update | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.3 | 2 | View | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.4 | 2 | Update | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.5 | 3 | View | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.6 | 3 | Update | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.7 | 3 | View | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.8 | 3 | Update | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.9 | 5 | View | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.10 | 5 | Update | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.11 | 5 | View | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.12 | 5 | Update | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.13 | 7 | View | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.14 | 7 | Update | widget-a | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.15 | 7 | View | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |
| 3.16 | 7 | Update | classified-part | ❌ FAIL | 🔴 Not Manager | manager tuple doesn't exist |

**Key Insight:** Without manager role, clearance doesn't matter - all denied

---

## Group 4: Manager=FALSE, Vacation=TRUE (Not Manager, On Vacation)

| Test | Clearance | Action | Item | Expected | Block Reason | FGA Logic |
|------|-----------|--------|------|----------|--------------|-----------|
| 4.1-4.16 | Any | Any | Any | ❌ FAIL | 🔴 Not Manager | Same as Group 3 - manager check fails first |

**Key Insight:** Vacation doesn't matter if not a manager

---

## Simplified Decision Tree

```
┌─ Is Manager? ─────────────────────────────────────┐
│                                                    │
NO                                                  YES
│                                                    │
❌ DENIED                                           ├─ On Vacation? ─────┐
(Not Manager)                                       │                    │
                                                   NO                   YES
                                                    │                    │
                                                    ├─ Action? ─┐        ❌ DENIED
                                                    │           │        (Vacation)
                                                   VIEW       UPDATE
                                                    │           │
                                                    ✅         ├─ Clearance? ─┐
                                                   PASS        │              │
                                                               │              │
                                                          Sufficient    Insufficient
                                                               │              │
                                                              ✅            ❌
                                                             PASS          FAIL
                                                                        (Clearance)
```

---

## Test Prompts by Scenario

### Bob's Current State (Manager=true, Vacation=true, Clearance=2)

**All these will FAIL due to vacation:**

| Prompt | Item Target | Scope | Expected | Why |
|--------|-------------|-------|----------|-----|
| "Show me inventory" | widget-a | read | ❌ FAIL | 🔴 Vacation |
| "What basketballs do we have?" | widget-a | read | ❌ FAIL | 🔴 Vacation |
| "Add 100 basketballs" | widget-a | write | ❌ FAIL | 🔴 Vacation |
| "Update basketball stock" | widget-a | write | ❌ FAIL | 🔴 Vacation |
| "Show Pro Arena Hoop" | classified-part | read | ❌ FAIL | 🔴 Vacation |
| "Update Pro Arena Hoop" | classified-part | write | ❌ FAIL | 🔴 Vacation |

---

## Recommended Test Sequence for Bob

### Test 1: Current State (Everything Blocked)
**Profile:** Manager=true, Vacation=true, Clearance=2

| Prompt | Expected | Log Should Show |
|--------|----------|-----------------|
| "Show me basketballs" | ❌ FAIL | `Vacation claim: True`, `contextual_tuples=1`, `can_view -> False`, "on vacation" |
| "Add 100 basketballs" | ❌ FAIL | `Vacation claim: True`, `can_update -> False`, "on vacation" |

---

### Test 2: Return from Vacation (Clearance Still Too Low)
**Change in Okta:** `is_on_vacation` → **false**

| Prompt | Expected | Block Reason | Log Should Show |
|--------|----------|--------------|-----------------|
| "Show me basketballs" | ✅ PASS | - | `Vacation: False`, `can_view -> True` |
| "Add 100 basketballs" | ❌ FAIL | 🔴 Clearance (2 < 3) | `Clearance: 2`, `can_update -> False`, "lacks clearance" |
| "Show Pro Arena Hoop" | ✅ PASS | - | `can_view -> True` (view doesn't check clearance) |
| "Update Pro Arena Hoop" | ❌ FAIL | 🔴 Clearance (2 < 7) | `Clearance: 2`, `can_update -> False` |

---

### Test 3: Clearance Increased to 3 (Minimum for Standard Items)
**Change in Okta:** `clearance_level` → **3**  
**Change in FGA:** 
```bash
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:2
fga tuple write user:bob.manager@atko.email granted_to clearance_level:3
```

| Prompt | Expected | Block Reason | Log Should Show |
|--------|----------|--------------|-----------------|
| "Show me basketballs" | ✅ PASS | - | `Clearance: 3`, `can_view -> True` |
| "Add 100 basketballs" | ✅ PASS | - | `Clearance: 3`, `can_update -> True` (3 >= 3) |
| "Show Pro Arena Hoop" | ✅ PASS | - | `can_view -> True` |
| "Update Pro Arena Hoop" | ❌ FAIL | 🔴 Clearance (3 < 7) | `Clearance: 3`, `can_update -> False` |

---

### Test 4: Clearance Increased to 5 (Mid-Level)
**Change in Okta:** `clearance_level` → **5**  
**Change in FGA:**
```bash
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:3
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5
```

| Prompt | Expected | Block Reason | Log Should Show |
|--------|----------|--------------|-----------------|
| "Show me basketballs" | ✅ PASS | - | `Clearance: 5`, `can_view -> True` |
| "Add 100 basketballs" | ✅ PASS | - | `Clearance: 5`, `can_update -> True` (5 >= 3) |
| "Show Pro Arena Hoop" | ✅ PASS | - | `can_view -> True` |
| "Update Pro Arena Hoop" | ❌ FAIL | 🔴 Clearance (5 < 7) | `Clearance: 5`, `can_update -> False` |

---

### Test 5: Clearance Increased to 7 (Senior Level)
**Change in Okta:** `clearance_level` → **7**  
**Change in FGA:**
```bash
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:5
fga tuple write user:bob.manager@atko.email granted_to clearance_level:7
```

| Prompt | Expected | Block Reason | Log Should Show |
|--------|----------|--------------|-----------------|
| "Show me basketballs" | ✅ PASS | - | `Clearance: 7`, `can_view -> True` |
| "Add 100 basketballs" | ✅ PASS | - | `Clearance: 7`, `can_update -> True` (7 >= 3) |
| "Show Pro Arena Hoop" | ✅ PASS | - | `can_view -> True` |
| "Update Pro Arena Hoop" | ✅ PASS | - | `Clearance: 7`, `can_update -> True` (7 >= 7) |

---

### Test 6: Go Back on Vacation (Everything Blocked Again)
**Change in Okta:** `is_on_vacation` → **true** (keep clearance=7)

| Prompt | Expected | Block Reason | Log Should Show |
|--------|----------|--------------|-----------------|
| "Show me basketballs" | ❌ FAIL | 🔴 Vacation | `Vacation: True`, `contextual_tuples=1`, "on vacation" |
| "Add 100 basketballs" | ❌ FAIL | 🔴 Vacation | `Vacation: True`, "on vacation" |
| "Show Pro Arena Hoop" | ❌ FAIL | 🔴 Vacation | `Vacation: True`, "on vacation" |
| "Update Pro Arena Hoop" | ❌ FAIL | 🔴 Vacation | `Vacation: True`, "on vacation" |

**Key Insight:** Even with highest clearance (7), vacation blocks everything

---

### Test 7: Remove Manager Role (Everything Blocked)
**Change in Okta:** `is_a_manager` → **false**, `is_on_vacation` → **false**, keep clearance=7  
**Change in FGA:**
```bash
fga tuple delete user:bob.manager@atko.email manager inventory_system:warehouse
```

| Prompt | Expected | Block Reason | Log Should Show |
|--------|----------|--------------|-----------------|
| "Show me basketballs" | ❌ FAIL | 🔴 Not Manager | `Manager: False`, "not a manager in FGA" |
| "Add 100 basketballs" | ❌ FAIL | 🔴 Not Manager | `Manager: False`, "not a manager" |

**Key Insight:** Without manager tuple in FGA, access denied regardless of clearance

---

## Master Reference Table

### Clearance Hierarchy (FGA Model)

| User Clearance | Can Update widget-a (req 3) | Can Update classified-part (req 7) |
|----------------|----------------------------|-----------------------------------|
| 2 | ❌ NO | ❌ NO |
| 3 | ✅ YES | ❌ NO |
| 4 | ✅ YES | ❌ NO |
| 5 | ✅ YES | ❌ NO |
| 6 | ✅ YES | ❌ NO |
| 7 | ✅ YES | ✅ YES |
| 8+ | ✅ YES | ✅ YES |

### Access Rules Summary

| Condition | View (can_view) | Update (can_update) |
|-----------|-----------------|---------------------|
| Manager=false | ❌ DENIED | ❌ DENIED |
| Manager=true + Vacation=true | ❌ DENIED | ❌ DENIED |
| Manager=true + Vacation=false + Insufficient clearance | ✅ ALLOWED | ❌ DENIED |
| Manager=true + Vacation=false + Sufficient clearance | ✅ ALLOWED | ✅ ALLOWED |

---

## Test Prompts Organized by Type

### Standard Basketballs (widget-a, requires clearance 3)

**View (inventory:read → can_view):**
- "Show me basketballs"
- "What basketballs do we have in stock?"
- "Check basketball inventory"
- "List basketball products"

**Update (inventory:write → can_update):**
- "Add 100 basketballs"
- "Update basketball inventory"
- "Increase basketball stock by 50"
- "Add 200 Pro Game Basketballs"

---

### Pro Arena Hoop (classified-part, requires clearance 7)

**View (inventory:read → can_view):**
- "Show me Pro Arena Hoop System"
- "What Pro Arena Hoops do we have?"
- "Check Pro Arena inventory"
- "Show high-value items"

**Update (inventory:write → can_update):**
- "Update Pro Arena Hoop System"
- "Add 10 Pro Arena Hoops"
- "Increase Pro Arena Hoop stock"
- "Modify arena equipment inventory"

---

## Bob's Journey - Recommended Demo Flow

### Starting State: Bob on Vacation, Low Clearance
**Profile:** Manager=true, Vacation=true, Clearance=2

1. **"Show me basketballs"** → ❌ FAIL (Vacation)
   - Shows: Vacation blocks everything

2. **Change:** `is_on_vacation` → false
3. **"Show me basketballs"** → ✅ PASS
   - Shows: Vacation is dynamic per request

4. **"Add 100 basketballs"** → ❌ FAIL (Clearance 2 < 3)
   - Shows: Insufficient clearance blocks write

5. **Change:** `clearance_level` → 3 (update FGA tuple)
6. **"Add 100 basketballs"** → ✅ PASS
   - Shows: Minimum clearance met

7. **"Update Pro Arena Hoop"** → ❌ FAIL (Clearance 3 < 7)
   - Shows: High-sensitivity requires higher clearance

8. **"Show Pro Arena Hoop"** → ✅ PASS
   - Shows: Can VIEW high-sensitivity, just can't UPDATE

9. **Change:** `clearance_level` → 7 (update FGA tuple)
10. **"Update Pro Arena Hoop"** → ✅ PASS
    - Shows: Senior clearance unlocks everything

11. **Change:** `is_on_vacation` → true
12. **"Show Pro Arena Hoop"** → ❌ FAIL (Vacation)
    - Shows: Vacation blocks even senior managers

---

## Quick Okta Profile Change Commands

For each test, update Bob's profile in Okta UI or save these for reference:

```
Test 1: Manager=true, Vacation=true, Clearance=2 (CURRENT)
Test 2: Manager=true, Vacation=false, Clearance=2
Test 3: Manager=true, Vacation=false, Clearance=3
Test 4: Manager=true, Vacation=false, Clearance=5
Test 5: Manager=true, Vacation=false, Clearance=7
Test 6: Manager=true, Vacation=true, Clearance=7
Test 7: Manager=false, Vacation=false, Clearance=7
```

---

## Expected UI Indicators by Test

### Test 1 (Current: Vacation=true)
- **Token Exchange:** ✅ Granted
- **FGA Check:** ❌ Denied
- **Agent Flow:** 🔴 Red (Inventory denied)
- **Message:** "Access denied: on vacation"

### Test 2 (Vacation=false, Clearance=2, Update)
- **Token Exchange:** ✅ Granted
- **FGA Check:** ❌ Denied
- **Agent Flow:** 🔴 Red (Inventory denied)
- **Message:** "Access denied: insufficient clearance"

### Test 3 (Vacation=false, Clearance=3, Update widget-a)
- **Token Exchange:** ✅ Granted
- **FGA Check:** ✅ Allowed
- **Agent Flow:** 🟢 Green (Inventory completed)
- **Message:** Inventory update successful

---

*Created: 2026-04-26*
*Complete test matrix with all 32+ parameter combinations*
