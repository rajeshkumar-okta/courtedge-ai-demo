# FGA Test Scenarios - Single User (Bob) All Combinations

## Test Strategy

Use **ONE user** (bob.manager@atko.email) and change his Okta profile attributes between tests to demonstrate all scenarios.

---

## Pre-requisites

### FGA Store Setup (One-time)

```bash
cd /Users/rajeshkumar

# Seed manager tuple for Bob
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse

# Seed clearance tuples for all levels Bob might use
fga tuple write user:bob.manager@atko.email granted_to clearance_level:3
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5
fga tuple write user:bob.manager@atko.email granted_to clearance_level:7

# Verify items exist with clearance requirements
fga tuple write inventory_system:warehouse parent inventory_item:widget-a
fga tuple write clearance_level:3 required_clearance inventory_item:widget-a

fga tuple write inventory_system:warehouse parent inventory_item:classified-part
fga tuple write clearance_level:7 required_clearance inventory_item:classified-part
```

**Note:** Clearance tuples will be read from highest to lowest by FGA's `holder from next_higher` chain. Seed all levels Bob might need.

---

## Test Scenarios (Bob's Journey)

### Scenario 1: Active Manager with Mid-Clearance Views Inventory ✅

**Test Goal:** Baseline success case

**Okta Profile Settings:**
| Attribute | Value | Location in Okta |
|-----------|-------|------------------|
| `is_a_manager` | ✅ **true** | Directory → People → bob.manager@atko.email → Profile → Edit |
| `is_on_vacation` | ❌ **false** | Directory → People → bob.manager@atko.email → Profile → Edit |
| `clearance_level` | **5** | Directory → People → bob.manager@atko.email → Profile → Edit |

**Steps:**
1. In Okta, verify Bob's profile shows above values
2. Login to CourtEdge as bob.manager@atko.email
3. Enter: **"Show me inventory"** or **"What basketballs do we have?"**

**Expected Result:**
- ✅ Token Exchange: Granted
- ✅ FGA Check: Allowed (`can_view` on widget-a)
- ✅ Response: Inventory data displayed

**Expected Logs:**
```
Extracted Manager claim: True
Extracted Vacation claim: False
Extracted Clearance claim: 5
FGA API check: user:bob.manager@atko.email can_view inventory_item:widget-a (vacation=False, contextual_tuples=0) -> True
Access granted
```

**UI Indicators:**
- Agent Flow: 🟢 Green (Inventory Agent completed)
- FGA Section: ✅ Allowed
- Raw Tokens: Vacation=false, Manager=true, Clearance=5

---

### Scenario 2: Manager on Vacation - Views Blocked ❌

**Test Goal:** Vacation blocks view operations

**Okta Profile Settings - CHANGE THIS:**
| Attribute | Value | Change |
|-----------|-------|--------|
| `is_a_manager` | ✅ **true** | No change |
| `is_on_vacation` | ✅ **true** | ⬅️ **CHANGE to true** |
| `clearance_level` | **5** | No change |

**Steps:**
1. **In Okta:** Directory → People → bob.manager@atko.email → Profile → Edit
2. Change `is_on_vacation` from false to **true**
3. Click **Save**
4. **In CourtEdge:** Enter: **"Show me inventory"**

**Expected Result:**
- ✅ Token Exchange: Granted (Okta allows token exchange)
- ❌ FGA Check: Denied (`can_view` blocked by vacation)
- ❌ Response: "Access denied: user is on vacation"

**Expected Logs:**
```
Extracted Vacation claim: True
contextual_tuples=1
FGA API check: user:bob.manager@atko.email can_view inventory_item:widget-a (vacation=True, contextual_tuples=1) -> False
Access denied: bob.manager@atko.email is on vacation (active_manager exclusion)
```

**UI Indicators:**
- Agent Flow: 🔴 Red (Inventory Agent denied)
- FGA Section: ❌ Denied - "is_on_vacation = true"
- Raw Tokens: Vacation=true (contextual tuple sent)

---

### Scenario 3: Manager on Vacation - Updates Also Blocked ❌

**Test Goal:** Vacation blocks write operations too

**Okta Profile Settings:**
| Attribute | Value |
|-----------|-------|
| `is_a_manager` | ✅ **true** |
| `is_on_vacation` | ✅ **true** (keep from Scenario 2) |
| `clearance_level` | **5** |

**Steps:**
1. Profile unchanged from Scenario 2 (still on vacation)
2. **In CourtEdge:** Enter: **"Add 100 basketballs"**

**Expected Result:**
- ✅ Token Exchange: Granted
- ❌ FGA Check: Denied (`can_update` blocked by vacation)
- ❌ Response: "Cannot update: user is on vacation"

**Expected Logs:**
```
Extracted Vacation claim: True
FGA API check: user:bob.manager@atko.email can_update inventory_item:widget-a (vacation=True, contextual_tuples=1) -> False
```

---

### Scenario 4: Manager Returns from Vacation - Access Restored ✅

**Test Goal:** Vacation is dynamic (per-request contextual tuple)

**Okta Profile Settings - CHANGE THIS:**
| Attribute | Value | Change |
|-----------|-------|--------|
| `is_a_manager` | ✅ **true** | No change |
| `is_on_vacation` | ❌ **false** | ⬅️ **CHANGE back to false** |
| `clearance_level` | **5** | No change |

**Steps:**
1. **In Okta:** Directory → People → bob.manager@atko.email → Profile → Edit
2. Change `is_on_vacation` from true to **false**
3. Click **Save**
4. **In CourtEdge:** Enter: **"Show me inventory"** (same request as Scenario 2)

**Expected Result:**
- ✅ FGA Check: Allowed (no vacation contextual tuple sent)
- ✅ Response: Inventory data displayed

**Key Insight:** Same user, same request, different result based on real-time Okta claim

---

### Scenario 5: Manager Updates Low-Sensitivity Item ✅

**Test Goal:** Adequate clearance allows update

**Okta Profile Settings:**
| Attribute | Value |
|-----------|-------|
| `is_a_manager` | ✅ **true** |
| `is_on_vacation` | ❌ **false** (keep from Scenario 4) |
| `clearance_level` | **5** |

**Steps:**
1. Profile unchanged from Scenario 4
2. **In CourtEdge:** Enter: **"Add 100 basketballs"** or **"Update widget-a"**

**Expected Result:**
- ✅ Token Exchange: Granted
- ✅ FGA Check: Allowed (`can_update` on widget-a)
  - widget-a requires clearance 3
  - Bob has clearance 5
  - 5 >= 3 ✅
- ✅ Response: Inventory update successful

**Expected Logs:**
```
Extracted Clearance claim: 5
FGA API check: user:bob.manager@atko.email can_update inventory_item:widget-a -> True
Access granted
```

---

### Scenario 6: Manager Lacks Clearance for High-Sensitivity Item ❌

**Test Goal:** Insufficient clearance blocks update

**Okta Profile Settings:**
| Attribute | Value | Same as Scenario 5 |
|-----------|-------|-------------------|
| `is_a_manager` | ✅ **true** | No change |
| `is_on_vacation` | ❌ **false** | No change |
| `clearance_level` | **5** | ⬅️ Too low for classified-part |

**Steps:**
1. Profile unchanged (clearance still 5)
2. **In CourtEdge:** Enter: **"Update classified-part"** or **"Add 50 classified parts"**

**Expected Result:**
- ✅ Token Exchange: Granted
- ❌ FGA Check: Denied (`can_update` on classified-part)
  - classified-part requires clearance 7
  - Bob has clearance 5
  - 5 < 7 ❌
- ❌ Response: "Access denied: insufficient clearance"

**Expected Logs:**
```
Extracted Clearance claim: 5
FGA API check: user:bob.manager@atko.email can_update inventory_item:classified-part -> False
Access denied: bob.manager@atko.email lacks clearance or manager status
```

**Key Insight:** Bob can VIEW classified-part (viewing doesn't check clearance) but cannot UPDATE it

---

### Scenario 7: Manager Gets Promoted - Clearance Increased ✅

**Test Goal:** Higher clearance unlocks high-sensitivity items

**Okta Profile Settings - CHANGE THIS:**
| Attribute | Value | Change |
|-----------|-------|--------|
| `is_a_manager` | ✅ **true** | No change |
| `is_on_vacation` | ❌ **false** | No change |
| `clearance_level` | **7** | ⬅️ **CHANGE from 5 to 7** |

**Steps:**
1. **In Okta:** Directory → People → bob.manager@atko.email → Profile → Edit
2. Change `clearance_level` from 5 to **7**
3. Click **Save**
4. **In FGA:** Update clearance tuple (if needed)
   ```bash
   cd /Users/rajeshkumar
   # Remove old clearance
   fga tuple delete user:bob.manager@atko.email granted_to clearance_level:5
   # Add new clearance
   fga tuple write user:bob.manager@atko.email granted_to clearance_level:7
   ```
5. **In CourtEdge:** Enter: **"Update classified-part"** (same request as Scenario 6)

**Expected Result:**
- ✅ FGA Check: Allowed (`can_update` on classified-part)
  - Now clearance 7 >= required 7 ✅
- ✅ Response: Update successful

**Key Insight:** Same user, same request, different clearance → different result

---

### Scenario 8: Manager Role Removed ❌

**Test Goal:** Non-managers cannot access inventory

**Okta Profile Settings - CHANGE THIS:**
| Attribute | Value | Change |
|-----------|-------|--------|
| `is_a_manager` | ❌ **false** | ⬅️ **CHANGE to false** |
| `is_on_vacation` | ❌ **false** | No change |
| `clearance_level` | **7** | Keep high clearance |

**Steps:**
1. **In Okta:** Directory → People → bob.manager@atko.email → Profile → Edit
2. Change `is_a_manager` from true to **false**
3. Click **Save**
4. **In FGA:** Remove manager tuple
   ```bash
   cd /Users/rajeshkumar
   fga tuple delete user:bob.manager@atko.email manager inventory_system:warehouse
   ```
5. **In CourtEdge:** Enter: **"Show me inventory"**

**Expected Result:**
- ✅ Token Exchange: Granted (Okta policy may still allow based on groups)
- ❌ FGA Check: Denied (no manager tuple in FGA)
- ❌ Response: "Access denied: not a manager"

**Expected Logs:**
```
Extracted Manager claim: False
FGA API check: user:bob.manager@atko.email can_view -> False
Access denied: does not have can_view (not a manager in FGA)
```

**Key Insight:** Even with high clearance (7), without manager role → denied

---

### Scenario 9: Low Clearance - Can Update Widget but Not Classified ✅/❌

**Test Goal:** Show clearance-based item sensitivity

**Okta Profile Settings - CHANGE THIS:**
| Attribute | Value | Change |
|-----------|-------|--------|
| `is_a_manager` | ✅ **true** | ⬅️ **CHANGE back to true** |
| `is_on_vacation` | ❌ **false** | No change |
| `clearance_level` | **3** | ⬅️ **CHANGE to 3 (lowest)** |

**Steps:**
1. **In Okta:** Set clearance_level = **3**
2. **In FGA:** Update clearance tuple
   ```bash
   cd /Users/rajeshkumar
   fga tuple delete user:bob.manager@atko.email granted_to clearance_level:7
   fga tuple write user:bob.manager@atko.email granted_to clearance_level:3
   fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
   ```
3. **Test A - Low-sensitivity item:**
   - Enter: **"Add 100 basketballs"** (widget-a, requires clearance 3)
   - ✅ Expected: **PASS** (clearance 3 >= required 3)

4. **Test B - High-sensitivity item:**
   - Enter: **"Update classified-part"** (requires clearance 7)
   - ❌ Expected: **DENIED** (clearance 3 < required 7)

**Expected Results:**

| Action | Item | Required Clearance | Bob's Clearance | Result |
|--------|------|-------------------|-----------------|--------|
| Update | widget-a | 3 | 3 | ✅ Pass |
| Update | classified-part | 7 | 3 | ❌ Fail |
| View | widget-a | n/a | 3 | ✅ Pass |
| View | classified-part | n/a | 3 | ✅ Pass |

**Key Insight:** Viewing doesn't check clearance, updating does

---

### Scenario 10: Combined - Vacation + Low Clearance ❌

**Test Goal:** Multiple blocks can apply simultaneously

**Okta Profile Settings - CHANGE THIS:**
| Attribute | Value | Change |
|-----------|-------|--------|
| `is_a_manager` | ✅ **true** | No change |
| `is_on_vacation` | ✅ **true** | ⬅️ **CHANGE to true** |
| `clearance_level` | **3** | Keep low |

**Steps:**
1. **In Okta:** Set `is_on_vacation` = **true**
2. **Test A:** Enter: **"Show me inventory"**
   - ❌ Expected: **DENIED** by vacation (before clearance even checked)
3. **Test B:** Enter: **"Add 100 basketballs"**
   - ❌ Expected: **DENIED** by vacation

**Expected Logs:**
```
Extracted Vacation claim: True
Extracted Clearance claim: 3
contextual_tuples=1 (on_vacation tuple sent)
FGA API check: can_view -> False
Access denied: on vacation
```

**Key Insight:** Vacation is checked first (at system level), blocks everything

---

## Complete Test Matrix for Bob

| # | Manager | Vacation | Clearance | Action | Item | Expected | Reason |
|---|---------|----------|-----------|--------|------|----------|--------|
| 1 | ✅ | ❌ | 5 | View | widget-a | ✅ Pass | Active manager |
| 2 | ✅ | ✅ | 5 | View | widget-a | ❌ Fail | On vacation |
| 3 | ✅ | ✅ | 5 | Update | widget-a | ❌ Fail | On vacation |
| 4 | ✅ | ❌ | 5 | Update | widget-a | ✅ Pass | Clearance sufficient |
| 5 | ✅ | ❌ | 5 | View | classified-part | ✅ Pass | View doesn't check clearance |
| 6 | ✅ | ❌ | 5 | Update | classified-part | ❌ Fail | Clearance insufficient (5 < 7) |
| 7 | ✅ | ❌ | 7 | Update | classified-part | ✅ Pass | Clearance sufficient (7 >= 7) |
| 8 | ❌ | ❌ | 7 | View | widget-a | ❌ Fail | Not a manager |
| 9 | ✅ | ❌ | 3 | Update | widget-a | ✅ Pass | Clearance sufficient (3 >= 3) |
| 10 | ✅ | ✅ | 3 | View | widget-a | ❌ Fail | On vacation |

---

## Step-by-Step Testing Flow

### Setup (Once)
```bash
# 1. Navigate to FGA config
cd /Users/rajeshkumar

# 2. Seed all tuples for Bob
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5

# 3. Verify items are seeded
fga tuple read --store-id 01KQ391VCMRKCD0G5XE92HVTQY | grep widget-a
fga tuple read --store-id 01KQ391VCMRKCD0G5XE92HVTQY | grep classified-part
```

---

### Test Sequence (Recommended Order)

#### Test 1: Baseline Success ✅
**Okta:** Manager=true, Vacation=false, Clearance=5  
**Action:** "Show me inventory"  
**Verify:** ✅ Access granted

#### Test 2: Enable Vacation ❌
**Change in Okta:** `is_on_vacation` → **true**  
**Action:** "Show me inventory" (same request)  
**Verify:** ❌ Access denied (vacation)  
**Observe:** Contextual tuple sent in logs

#### Test 3: Vacation Blocks Update Too ❌
**Keep:** Vacation=true  
**Action:** "Add 100 basketballs"  
**Verify:** ❌ Access denied (vacation)

#### Test 4: Disable Vacation ✅
**Change in Okta:** `is_on_vacation` → **false**  
**Action:** "Add 100 basketballs" (same request)  
**Verify:** ✅ Access granted  
**Observe:** No contextual tuple sent

#### Test 5: Try High-Sensitivity Item ❌
**Keep:** Manager=true, Vacation=false, Clearance=5  
**Action:** "Update classified-part"  
**Verify:** ❌ Access denied (clearance 5 < required 7)

#### Test 6: View High-Sensitivity Item ✅
**Keep:** Same profile  
**Action:** "Show me classified-part"  
**Verify:** ✅ Access granted (view doesn't check clearance)

#### Test 7: Increase Clearance ✅
**Change in Okta:** `clearance_level` → **7**  
**Change in FGA:**
```bash
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:5
fga tuple write user:bob.manager@atko.email granted_to clearance_level:7
```
**Action:** "Update classified-part" (same request as Test 5)  
**Verify:** ✅ Access granted (now clearance sufficient)

#### Test 8: Lower Clearance ✅/❌
**Change in Okta:** `clearance_level` → **3**  
**Change in FGA:**
```bash
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:7
fga tuple write user:bob.manager@atko.email granted_to clearance_level:3
```
**Action A:** "Add 100 basketballs" (widget-a, req 3)  
**Verify:** ✅ Pass (3 >= 3)  
**Action B:** "Update classified-part" (req 7)  
**Verify:** ❌ Fail (3 < 7)

#### Test 9: Remove Manager Role ❌
**Change in Okta:** `is_a_manager` → **false**  
**Change in FGA:**
```bash
fga tuple delete user:bob.manager@atko.email manager inventory_system:warehouse
```
**Action:** "Show me inventory"  
**Verify:** ❌ Access denied (not a manager)  
**Observe:** Even with clearance, no manager role = no access

#### Test 10: Restore Manager Role ✅
**Change in Okta:** `is_a_manager` → **true**  
**Change in FGA:**
```bash
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
```
**Action:** "Show me inventory"  
**Verify:** ✅ Access granted

---

## Quick Change Reference

### Okta Profile Changes (Directory → People → bob.manager@atko.email → Edit)

| Test | is_a_manager | is_on_vacation | clearance_level |
|------|--------------|----------------|-----------------|
| 1 | ✅ true | ❌ false | 5 |
| 2-3 | ✅ true | ✅ **true** | 5 |
| 4-6 | ✅ true | ❌ **false** | 5 |
| 7 | ✅ true | ❌ false | **7** |
| 8 | ✅ true | ❌ false | **3** |
| 9 | ❌ **false** | ❌ false | 3 |
| 10 | ✅ **true** | ❌ false | 5 |

### FGA Tuple Changes (When Okta Clearance Changes)

```bash
cd /Users/rajeshkumar

# When changing clearance, delete old and add new:
# Clearance 3
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:5
fga tuple write user:bob.manager@atko.email granted_to clearance_level:3

# Clearance 5
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:3
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5

# Clearance 7
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:5
fga tuple write user:bob.manager@atko.email granted_to clearance_level:7

# When removing manager role
fga tuple delete user:bob.manager@atko.email manager inventory_system:warehouse

# When restoring manager role
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
```

---

## User Actions for Each Test

### Read Operations (Trigger inventory:read)
- "Show me inventory"
- "What basketballs do we have in stock?"
- "Check inventory levels"
- "What's available?"

### Write Operations (Trigger inventory:write)
- "Add 100 basketballs"
- "Update inventory"
- "Increase stock by 50"
- "Add 30 units"

### Targeting Specific Items
- "Show me widget-a" → low-sensitivity (clearance 3)
- "Show me classified-part" → high-sensitivity (clearance 7)
- "Update widget-a" → requires clearance 3
- "Update classified-part" → requires clearance 7

---

## Expected UI Changes Per Scenario

### Scenario 1 (Success)
- **Agent Flow:** 🟢 Green - Inventory Agent completed
- **Token Exchange:** ✅ Granted
- **FGA Section:** ✅ Allowed - "can_view"
- **Raw Tokens:** Manager=true, Vacation=false, Clearance=5

### Scenario 2 (Vacation Block)
- **Agent Flow:** 🔴 Red - Inventory Agent denied
- **Token Exchange:** ✅ Granted (token issued)
- **FGA Section:** ❌ Denied - "is_on_vacation = true"
- **Raw Tokens:** Vacation=true visible in Access Token

### Scenario 6 (Clearance Block)
- **Agent Flow:** 🔴 Red - Inventory Agent denied
- **Token Exchange:** ✅ Granted
- **FGA Section:** ❌ Denied - "lacks clearance"
- **Raw Tokens:** Clearance=5 but item requires 7

---

## Demo Script (5-Minute Presentation)

### Minute 1: Setup
"Bob is a warehouse manager with clearance level 5."

### Minute 2: Success Case
**Show:** Bob views inventory → ✅ Success  
**Explain:** Manager role + not on vacation = access granted

### Minute 3: Vacation Block
**Change:** Set vacation=true in Okta  
**Show:** Bob views inventory → ❌ Denied  
**Explain:** Contextual tuple sent per request, vacation excludes from active_manager

### Minute 4: Clearance Hierarchy
**Change:** Set vacation=false  
**Show A:** Bob updates widget-a (req 3) → ✅ Success (clearance 5 >= 3)  
**Show B:** Bob updates classified-part (req 7) → ❌ Denied (clearance 5 < 7)  
**Explain:** Clearance hierarchy walk in FGA

### Minute 5: Promotion
**Change:** Set clearance=7 in Okta + FGA  
**Show:** Bob updates classified-part → ✅ Success  
**Explain:** Higher clearance unlocks high-sensitivity items

---

## Troubleshooting

### Scenario Doesn't Match Expected Result

1. **Check Okta profile values:**
   - Directory → People → bob.manager@atko.email → Profile
   - Verify is_a_manager, is_on_vacation, clearance_level

2. **Check FGA tuples:**
   ```bash
   cd /Users/rajeshkumar
   # Check manager tuple
   fga tuple read --user user:bob.manager@atko.email --relation manager
   # Check clearance tuple
   fga tuple read --user user:bob.manager@atko.email --relation granted_to
   ```

3. **Check Access Token claims:**
   - In UI, expand "Raw Tokens" card
   - Verify Inventory Agent Token shows: Manager, Vacation, Clearance claims

4. **Check logs:**
   - Look for "Extracted Manager claim", "Extracted Vacation claim", "Extracted Clearance claim"
   - Verify values match Okta profile

---

## Reset Bob to Default State

After testing, reset Bob to baseline:

**Okta:**
- `is_a_manager` = **true**
- `is_on_vacation` = **false**
- `clearance_level` = **5**

**FGA:**
```bash
cd /Users/rajeshkumar
fga tuple write user:bob.manager@atko.email manager inventory_system:warehouse
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:3
fga tuple delete user:bob.manager@atko.email granted_to clearance_level:7
fga tuple write user:bob.manager@atko.email granted_to clearance_level:5
```

---

*Created: 2026-04-26*
*Single-user comprehensive testing guide*
