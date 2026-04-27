# FGA Test Scenarios and Demonstration Guide

## Test Environment Setup

### Required FGA Store
- **Store Name:** ProGear New
- **Store ID:** `01KQ391VCMRKCD0G5XE92HVTQY`
- **Status:** Model and base tuples already seeded

### Test Users in Okta

Create/configure these test users for comprehensive testing:

| User Email | Manager | Vacation | Clearance | Purpose |
|------------|---------|----------|-----------|---------|
| `alice@atko.email` | ✅ true | ❌ false | 5 | Active manager, mid-clearance |
| `bob.manager@atko.email` | ✅ true | ✅ true | 5 | Manager on vacation |
| `charlie@atko.email` | ✅ true | ❌ false | 5 | Pre-seeded in FGA (for comparison) |
| `low-clearance@atko.email` | ✅ true | ❌ false | 3 | Manager with low clearance |
| `high-clearance@atko.email` | ✅ true | ❌ false | 7 | Manager with high clearance |
| `no-manager@atko.email` | ❌ false | ❌ false | 5 | Not a manager (should be denied) |

---

## Okta User Profile Configuration

### 1. Add Custom Attributes (Directory → Profile Editor → Okta User)

If not already added:

| Attribute | Variable Name | Data Type | Description |
|-----------|---------------|-----------|-------------|
| Is a Manager | `is_a_manager` | boolean | User has manager role |
| Is On Vacation | `is_on_vacation` | boolean | User is currently on vacation |
| Clearance Level | `clearance_level` | integer | User's security clearance (1-10) |

### 2. Set Attribute Values Per User

**For each test user, edit their profile:**

Directory → People → [Select User] → Profile → Edit

#### Alice (alice@atko.email)
- `is_a_manager`: ✅ **true**
- `is_on_vacation`: ❌ **false**
- `clearance_level`: **5**

#### Bob Manager (bob.manager@atko.email)
- `is_a_manager`: ✅ **true**
- `is_on_vacation`: ✅ **true**
- `clearance_level`: **5**

#### Charlie (charlie@atko.email)
- `is_a_manager`: ✅ **true**
- `is_on_vacation`: ❌ **false**
- `clearance_level`: **5**

#### Low Clearance User (low-clearance@atko.email)
- `is_a_manager`: ✅ **true**
- `is_on_vacation`: ❌ **false**
- `clearance_level`: **3**

#### High Clearance User (high-clearance@atko.email)
- `is_a_manager`: ✅ **true**
- `is_on_vacation`: ❌ **false**
- `clearance_level`: **7**

#### No Manager (no-manager@atko.email)
- `is_a_manager`: ❌ **false**
- `is_on_vacation`: ❌ **false**
- `clearance_level`: **5**

---

## FGA Store - User Tuple Requirements

### Pre-seed Manager Tuples in FGA

For each user who should be a manager, add this tuple:

```bash
# Using fga CLI
cd /Users/rajeshkumar
fga tuple write user:alice@atko.email manager inventory_system:warehouse
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
fga tuple write user:charlie@atko.email manager inventory_system:warehouse
fga tuple write user:low-clearance@atko.email manager inventory_system:warehouse
fga tuple write user:high-clearance@atko.email manager inventory_system:warehouse
```

### Pre-seed Clearance Tuples in FGA

For each user, add their clearance level tuple:

```bash
# Clearance level 3
fga tuple write user:low-clearance@atko.email granted_to clearance_level:3

# Clearance level 5
fga tuple write user:alice@atko.email granted_to clearance_level:5
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5
fga tuple write user:charlie@atko.email granted_to clearance_level:5
fga tuple write user:no-manager@atko.email granted_to clearance_level:5

# Clearance level 7
fga tuple write user:high-clearance@atko.email granted_to clearance_level:7
```

---

## Test Scenarios

### Scenario 1: Active Manager Views Inventory (✅ PASS)

**User:** alice@atko.email  
**Okta Profile:**
- Manager: true
- Vacation: false
- Clearance: 5

**User Action:** "Show me inventory" or "What's in stock?"

**Expected Flow:**
1. Router detects `inventory:read` scope
2. Token exchange gets Access Token with claims
3. FGA check: `can_view` on `inventory_item:widget-a`
4. Vacation contextual tuple: **NOT sent** (vacation=false)
5. FGA evaluates: `active_manager` = `manager but not on_vacation`
   - Manager tuple exists ✅
   - Vacation tuple NOT present ✅
   - Result: **ALLOWED**

**Expected Result:** ✅ **Access granted**, inventory data displayed

**Logs to verify:**
```
Extracted Manager claim: True
Extracted Vacation claim: False
FGA API check: user:alice@atko.email can_view inventory_item:widget-a (vacation=False) -> True
```

---

### Scenario 2: Manager on Vacation Views Inventory (❌ DENIED)

**User:** bob.manager@atko.email  
**Okta Profile:**
- Manager: true
- Vacation: **true**
- Clearance: 5

**User Action:** "Show me inventory"

**Expected Flow:**
1. Router detects `inventory:read` scope
2. Token exchange gets Access Token with claims
3. FGA check: `can_view` on `inventory_item:widget-a`
4. Vacation contextual tuple: **SENT** (vacation=true)
   ```
   user:bob.manager@atko.email -> on_vacation -> inventory_system:warehouse
   ```
5. FGA evaluates: `active_manager` = `manager but not on_vacation`
   - Manager tuple exists ✅
   - Vacation tuple present ✅
   - `manager but not on_vacation` = {} (EMPTY)
   - Result: **DENIED**

**Expected Result:** ❌ **Access denied: user is on vacation**

**Logs to verify:**
```
Extracted Vacation claim: True
FGA API check: user:bob.manager@atko.email can_view inventory_item:widget-a (vacation=True, contextual_tuples=1) -> False
Access denied: bob.manager@atko.email is on vacation (active_manager exclusion)
```

**UI Display:**
- Token Exchange: ✅ Granted (token issued successfully)
- FGA Check: ❌ Denied (vacation blocked)
- Agent Flow: 🔴 Red (denied)

---

### Scenario 3: Manager Updates Low-Sensitivity Item (✅ PASS)

**User:** alice@atko.email  
**Okta Profile:**
- Manager: true
- Vacation: false
- Clearance: **5**

**User Action:** "Add 100 basketballs" (write operation)

**Expected Flow:**
1. Router detects `inventory:write` scope
2. Token exchange gets Access Token
3. FGA check: `can_update` on `inventory_item:widget-a`
   - widget-a requires clearance 3 (in FGA)
4. FGA evaluates:
   - `has_clearance`: holder from required_clearance
     - Required: level 3
     - User has: level 5
     - Hierarchy walk: holder(3) includes users granted 3, 4, **5**, ...
     - Result: ✅ Alice is in the set
   - `can_manage from parent`: active_manager
     - Manager: ✅ exists
     - Vacation: ❌ no contextual tuple
     - Result: ✅ Allowed
   - `AND` both sides: ✅ **ALLOWED**

**Expected Result:** ✅ **Access granted**, inventory update performed

**Logs to verify:**
```
Clearance claim: 5
FGA API check: user:alice@atko.email can_update inventory_item:widget-a -> True
```

---

### Scenario 4: Manager Lacks Clearance for High-Sensitivity Item (❌ DENIED)

**User:** alice@atko.email (clearance 5)  
**OR:** low-clearance@atko.email (clearance 3)

**Okta Profile:**
- Manager: true
- Vacation: false
- Clearance: **5** (or 3)

**User Action:** "Update classified part" (targeting high-sensitivity item)

**Expected Flow:**
1. Router detects `inventory:write` scope
2. FGA check: `can_update` on `inventory_item:classified-part`
   - classified-part requires clearance **7** (in FGA)
3. FGA evaluates:
   - `has_clearance`: holder from required_clearance
     - Required: level 7
     - User has: level 5
     - Hierarchy walk: holder(7) includes users granted 7, 8, 9, 10
     - Alice (level 5) NOT in the set
     - Result: ❌ EMPTY
   - `AND` fails because has_clearance is empty
   - Result: **DENIED**

**Expected Result:** ❌ **Access denied: insufficient clearance**

**Logs to verify:**
```
Clearance claim: 5
FGA API check: user:alice@atko.email can_update inventory_item:classified-part -> False
Access denied: alice@atko.email lacks clearance or manager status
```

---

### Scenario 5: High-Clearance Manager Updates Classified Item (✅ PASS)

**User:** high-clearance@atko.email  
**Okta Profile:**
- Manager: true
- Vacation: false
- Clearance: **7**

**User Action:** "Update classified part"

**Expected Flow:**
1. Router detects `inventory:write` scope
2. FGA check: `can_update` on `inventory_item:classified-part`
   - classified-part requires clearance 7
3. FGA evaluates:
   - `has_clearance`: holder(7)
     - User granted level 7 ✅
     - Result: ✅ User in set
   - `can_manage from parent`: active_manager ✅
   - `AND` both sides: ✅ **ALLOWED**

**Expected Result:** ✅ **Access granted**

---

### Scenario 6: Non-Manager Cannot Access (❌ DENIED)

**User:** no-manager@atko.email  
**Okta Profile:**
- Manager: **false**
- Vacation: false
- Clearance: 5

**User Action:** "Show me inventory"

**Expected Flow:**
1. Router detects `inventory:read` scope
2. FGA check: `can_view` on `inventory_item:widget-a`
3. FGA evaluates:
   - `can_manage from parent`: active_manager
     - `manager but not on_vacation`
     - Manager tuple: ❌ NOT in FGA (user not seeded as manager)
     - Result: ❌ EMPTY
   - Result: **DENIED**

**Expected Result:** ❌ **Access denied: not a manager**

---

### Scenario 7: Manager on Vacation Cannot Update (❌ DENIED)

**User:** bob.manager@atko.email  
**Okta Profile:**
- Manager: true
- Vacation: **true**
- Clearance: 5

**User Action:** "Add 100 basketballs" (write operation)

**Expected Flow:**
1. Router detects `inventory:write` scope
2. Vacation contextual tuple sent
3. FGA check: `can_update` on `inventory_item:widget-a`
4. FGA evaluates:
   - `has_clearance`: ✅ (clearance 5 >= required 3)
   - `can_manage from parent`: active_manager
     - `manager but not on_vacation`
     - Manager: ✅ exists
     - Vacation: ✅ contextual tuple present
     - Result: ❌ EMPTY (excluded by "but not")
   - `AND` fails: ✅ AND ❌ = ❌
   - Result: **DENIED**

**Expected Result:** ❌ **Access denied: on vacation**

**Key Insight:** Vacation blocks BOTH view AND update operations

---

## Test Matrix

| User | Manager | Vacation | Clearance | Action | Item | Expected |
|------|---------|----------|-----------|--------|------|----------|
| alice | ✅ | ❌ | 5 | View | widget-a | ✅ Pass |
| alice | ✅ | ❌ | 5 | Update | widget-a (req 3) | ✅ Pass |
| alice | ✅ | ❌ | 5 | Update | classified-part (req 7) | ❌ Fail (clearance) |
| bob.manager | ✅ | ✅ | 5 | View | widget-a | ❌ Fail (vacation) |
| bob.manager | ✅ | ✅ | 5 | Update | widget-a | ❌ Fail (vacation) |
| low-clearance | ✅ | ❌ | 3 | View | widget-a | ✅ Pass |
| low-clearance | ✅ | ❌ | 3 | Update | widget-a (req 3) | ✅ Pass |
| low-clearance | ✅ | ❌ | 3 | Update | classified-part (req 7) | ❌ Fail (clearance) |
| high-clearance | ✅ | ❌ | 7 | Update | classified-part (req 7) | ✅ Pass |
| no-manager | ❌ | ❌ | 5 | View | widget-a | ❌ Fail (not manager) |
| no-manager | ❌ | ❌ | 5 | Update | widget-a | ❌ Fail (not manager) |

---

## Step-by-Step Test Instructions

### Test 1: Active Manager Views Inventory ✅

**Goal:** Verify basic manager access with no blocks

1. **Okta Setup:**
   - User: alice@atko.email
   - Set `is_a_manager` = **true**
   - Set `is_on_vacation` = **false**
   - Set `clearance_level` = **5**

2. **FGA Setup:**
   ```bash
   cd /Users/rajeshkumar
   # Ensure manager tuple exists
   fga tuple write user:alice@atko.email manager inventory_system:warehouse
   # Ensure clearance tuple exists
   fga tuple write user:alice@atko.email granted_to clearance_level:5
   ```

3. **Test Action:**
   - Login as alice@atko.email
   - Enter: **"Show me inventory"** or **"What basketballs do we have?"**

4. **Expected Outcome:**
   - ✅ Token exchange: Granted
   - ✅ FGA check: Allowed (`can_view`)
   - ✅ Response: Inventory data displayed

5. **Verify in Logs:**
   ```
   Extracted Manager claim: True
   Extracted Vacation claim: False
   Extracted Clearance claim: 5
   FGA API check: can_view inventory_item:widget-a -> True
   ```

---

### Test 2: Vacation Blocks View and Update ❌

**Goal:** Verify vacation status blocks all operations

1. **Okta Setup:**
   - User: bob.manager@atko.email
   - Set `is_a_manager` = **true**
   - Set `is_on_vacation` = **true** ⬅️ KEY CHANGE
   - Set `clearance_level` = **5**

2. **FGA Setup:**
   ```bash
   # Ensure manager tuple exists
   fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
   # Ensure clearance tuple exists
   fga tuple write user:bob.manager@atko.email granted_to clearance_level:5
   ```

3. **Test Action A (View):**
   - Login as bob.manager@atko.email
   - Enter: **"Show me inventory"**

4. **Expected Outcome A:**
   - ✅ Token exchange: Granted
   - ❌ FGA check: Denied (`can_view` blocked by vacation)
   - ❌ Response: "Access denied: user is on vacation"

5. **Test Action B (Update):**
   - Enter: **"Add 100 basketballs"**

6. **Expected Outcome B:**
   - ✅ Token exchange: Granted
   - ❌ FGA check: Denied (`can_update` blocked by vacation)
   - ❌ Response: "Access denied: on vacation"

7. **Verify in Logs:**
   ```
   Extracted Vacation claim: True
   contextual_tuples=1
   FGA API check: can_view -> False
   Access denied: bob.manager@atko.email is on vacation
   ```

---

### Test 3: Insufficient Clearance Blocks Update ❌

**Goal:** User can view but cannot update high-sensitivity item

1. **Okta Setup:**
   - User: alice@atko.email (or low-clearance@atko.email)
   - Set `is_a_manager` = **true**
   - Set `is_on_vacation` = **false**
   - Set `clearance_level` = **5** (or 3 for low-clearance user)

2. **FGA Setup:**
   ```bash
   fga tuple write user:alice@atko.email manager inventory_system:warehouse
   fga tuple write user:alice@atko.email granted_to clearance_level:5
   
   # Ensure classified-part exists with clearance 7 requirement
   fga tuple write inventory_system:warehouse parent inventory_item:classified-part
   fga tuple write clearance_level:7 required_clearance inventory_item:classified-part
   ```

3. **Test Action A (View - should pass):**
   - Login as alice@atko.email
   - Enter: **"Show me classified-part"**

4. **Expected Outcome A:**
   - ✅ FGA check: Allowed (`can_view` doesn't require clearance)
   - ✅ Response: Can see the item exists

5. **Test Action B (Update - should fail):**
   - Enter: **"Update classified-part"** or **"Add 50 classified-part"**

6. **Expected Outcome B:**
   - ✅ Token exchange: Granted
   - ❌ FGA check: Denied (`can_update` requires clearance 7, user has 5)
   - ❌ Response: "Access denied: insufficient clearance"

7. **Verify in Logs:**
   ```
   Clearance claim: 5
   FGA API check: can_update inventory_item:classified-part -> False
   Access denied: lacks clearance or manager status
   ```

---

### Test 4: High-Clearance Manager Updates Classified Item ✅

**Goal:** Adequate clearance allows update of high-sensitivity item

1. **Okta Setup:**
   - User: high-clearance@atko.email
   - Set `is_a_manager` = **true**
   - Set `is_on_vacation` = **false**
   - Set `clearance_level` = **7** ⬅️ Meets requirement

2. **FGA Setup:**
   ```bash
   fga tuple write user:high-clearance@atko.email manager inventory_system:warehouse
   fga tuple write user:high-clearance@atko.email granted_to clearance_level:7
   ```

3. **Test Action:**
   - Login as high-clearance@atko.email
   - Enter: **"Update classified-part"**

4. **Expected Outcome:**
   - ✅ Token exchange: Granted
   - ✅ FGA check: Allowed (`has_clearance` satisfied, clearance 7 >= required 7)
   - ✅ Response: Update successful

5. **Verify in Logs:**
   ```
   Clearance claim: 7
   FGA API check: can_update inventory_item:classified-part -> True
   ```

---

### Test 5: Non-Manager Denied ❌

**Goal:** Users without manager role cannot access inventory

1. **Okta Setup:**
   - User: no-manager@atko.email
   - Set `is_a_manager` = **false** ⬅️ Not a manager
   - Set `is_on_vacation` = **false**
   - Set `clearance_level` = **5**

2. **FGA Setup:**
   ```bash
   # Ensure clearance tuple exists (but NO manager tuple)
   fga tuple write user:no-manager@atko.email granted_to clearance_level:5
   
   # Verify manager tuple does NOT exist:
   fga tuple read --user user:no-manager@atko.email --relation manager --object inventory_system:warehouse
   # Should return: no tuples found
   ```

3. **Test Action:**
   - Login as no-manager@atko.email
   - Enter: **"Show me inventory"**

4. **Expected Outcome:**
   - ✅ Token exchange: Granted (Okta policy allows based on group)
   - ❌ FGA check: Denied (no manager tuple in FGA)
   - ❌ Response: "Access denied: not a manager"

---

### Test 6: Low-Clearance Manager Updates Low-Sensitivity Item ✅

**Goal:** Users with minimum required clearance can update

1. **Okta Setup:**
   - User: low-clearance@atko.email
   - Set `is_a_manager` = **true**
   - Set `is_on_vacation` = **false**
   - Set `clearance_level` = **3** ⬅️ Exactly meets requirement

2. **FGA Setup:**
   ```bash
   fga tuple write user:low-clearance@atko.email manager inventory_system:warehouse
   fga tuple write user:low-clearance@atko.email granted_to clearance_level:3
   ```

3. **Test Action:**
   - Login as low-clearance@atko.email
   - Enter: **"Add 100 basketballs"** (widget-a requires clearance 3)

4. **Expected Outcome:**
   - ✅ FGA check: Allowed (clearance 3 >= required 3)
   - ✅ Response: Update successful

---

### Test 7: Toggle Vacation Status (Dynamic Test)

**Goal:** Show vacation status is evaluated per request (not cached)

1. **Initial State:**
   - User: alice@atko.email
   - Vacation: **false**

2. **Test Action 1:**
   - Login as alice
   - Enter: **"Show me inventory"**
   - ✅ Should PASS

3. **Change Vacation Status:**
   - Go to Okta: Directory → People → alice@atko.email → Profile → Edit
   - Set `is_on_vacation` = **true**
   - Save

4. **Test Action 2 (SAME request):**
   - In the app, enter: **"Show me inventory"** again
   - ❌ Should now FAIL

5. **Expected Outcome:**
   - First request: ✅ Allowed
   - Second request: ❌ Denied (vacation tuple sent this time)
   - This proves contextual tuples are evaluated per request

6. **Change Back:**
   - Set `is_on_vacation` = **false**
   - Test again: ✅ Should PASS

---

## Demo Flow Recommendation

### Sequence for Best Impact

1. **Start with success** - alice views inventory (Scenario 1)
2. **Show vacation block** - bob on vacation tries to view (Scenario 2)
3. **Show clearance** - alice tries classified item (Scenario 4)
4. **Show high clearance works** - high-clearance user updates classified (Scenario 5)
5. **Show non-manager block** - no-manager denied (Scenario 5)
6. **Dynamic vacation toggle** - show real-time contextual evaluation (Scenario 7)

---

## Quick Reference: User Setup Commands

```bash
# Navigate to fga config
cd /Users/rajeshkumar

# Alice - active manager, clearance 5
fga tuple write user:alice@atko.email manager inventory_system:warehouse
fga tuple write user:alice@atko.email granted_to clearance_level:5

# Bob - manager on vacation, clearance 5
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5

# Low clearance - manager, clearance 3
fga tuple write user:low-clearance@atko.email manager inventory_system:warehouse
fga tuple write user:low-clearance@atko.email granted_to clearance_level:3

# High clearance - manager, clearance 7
fga tuple write user:high-clearance@atko.email manager inventory_system:warehouse
fga tuple write user:high-clearance@atko.email granted_to clearance_level:7

# No manager - clearance 5 but no manager role
fga tuple write user:no-manager@atko.email granted_to clearance_level:5
# (intentionally NO manager tuple)

# Verify items exist with clearance requirements
fga tuple write inventory_system:warehouse parent inventory_item:widget-a
fga tuple write clearance_level:3 required_clearance inventory_item:widget-a

fga tuple write inventory_system:warehouse parent inventory_item:classified-part
fga tuple write clearance_level:7 required_clearance inventory_item:classified-part
```

---

## Verification Checklist

Before testing, verify:

- [ ] All test users exist in Okta
- [ ] User profile attributes set correctly
- [ ] `Clearance` claim added to Inventory Auth Server
- [ ] Manager tuples seeded in FGA for test users
- [ ] Clearance tuples seeded in FGA for test users
- [ ] Clearance chain seeded (levels 1-10)
- [ ] Item hierarchy seeded (warehouse → items)
- [ ] Item clearance requirements seeded
- [ ] Render environment variables updated
- [ ] Code deployed to Render

---

*Created: 2026-04-26*
