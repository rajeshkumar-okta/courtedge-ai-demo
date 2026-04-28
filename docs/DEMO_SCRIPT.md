# ProGear Sales AI Demo Script

**Theme:** Okta + FGA Better Together

This demo showcases how Okta identity (RBAC, claims) combines with OpenFGA (ReBAC + ABAC) to provide fine-grained authorization for AI agent operations.

---

## Demo User: Bob

| Attribute | Okta Profile Field | Current Value |
|-----------|-------------------|---------------|
| Email | bob.manager@atko.email | - |
| Manager | user.is_a_manager | Toggle in Okta |
| Vacation | user.is_on_vacation | Toggle in Okta |
| Clearance | user.clearance_level | 1-10 in Okta |

**FGA Items:**
- `widget-a` - requires clearance level 3
- `classified-part` - requires clearance level 7

---

## Demo Scenarios

### Success Scenarios (Green Flow)

#### 1. View Inventory (Active Manager)
**Setup:** Manager=true, Vacation=false, Clearance=any  
**Prompt:** "Check inventory for basketballs"  
**Expected:** Allowed - active_manager grants can_view  
**Key Point:** Managers can always VIEW when not on vacation

#### 2. Update Low-Clearance Item
**Setup:** Manager=true, Vacation=false, Clearance=5  
**Prompt:** "Add 50 units of widget-a to inventory"  
**Expected:** Allowed - clearance 5 > required 3, plus active_manager  
**Key Point:** Clearance hierarchy - level 5 grants access to items requiring 3 or lower

#### 3. Update High-Clearance Item
**Setup:** Manager=true, Vacation=false, Clearance=8  
**Prompt:** "Update classified-part quantity to 10"  
**Expected:** Allowed - clearance 8 > required 7, plus active_manager  
**Key Point:** Only users with sufficient clearance can modify sensitive items

#### 4. Non-Inventory Agent (No FGA)
**Setup:** Any user profile  
**Prompt:** "What's the current price for basketballs?"  
**Expected:** Allowed - Pricing agent uses Okta RBAC only, no FGA check  
**Key Point:** FGA enforcement is scope-specific (only inventory write operations)

---

### Failure Scenarios (Red Flow)

#### 5. Vacation Blocks View
**Setup:** Manager=true, Vacation=true, Clearance=any  
**Prompt:** "Check inventory for basketballs"  
**Expected:** DENIED - on_vacation blocks active_manager  
**Key Point:** Vacation is contextual tuple - not stored, passed per request

#### 6. Vacation Blocks Update
**Setup:** Manager=true, Vacation=true, Clearance=10  
**Prompt:** "Add 100 units of widget-a"  
**Expected:** DENIED - on_vacation blocks active_manager (even with max clearance)  
**Key Point:** Must be ACTIVE manager to modify inventory

#### 7. Insufficient Clearance
**Setup:** Manager=true, Vacation=false, Clearance=2  
**Prompt:** "Update classified-part quantity to 10"  
**Expected:** DENIED - clearance 2 < required 7  
**Key Point:** Can VIEW but cannot UPDATE high-sensitivity items

#### 8. Non-Manager Access
**Setup:** Manager=false, Vacation=false, Clearance=10  
**Prompt:** "Check inventory for basketballs"  
**Expected:** DENIED - no manager tuple = no access  
**Key Point:** FGA requires manager relationship even for view

---

## Quick Demo Flow (5 minutes)

1. **Show Success:** Bob as active manager (Manager=true, Vacation=false, Clearance=5)
   - "Check inventory for basketballs" → Allowed (view)
   - "Add 50 widgets" → Allowed (update with clearance)

2. **Toggle Vacation:** Change Vacation=true in Okta
   - Same prompt → DENIED (red agent flow)
   - Show FGA Explanation Card: "on_vacation contextual tuple"

3. **Reset Vacation, Lower Clearance:** Vacation=false, Clearance=2
   - "Check inventory" → Allowed (view still works)
   - "Update classified-part" → DENIED (clearance too low)

4. **Toggle Manager:** Manager=false
   - Any inventory prompt → DENIED (no manager relationship)

---

## Key Talking Points

| Okta Does | FGA Does |
|-----------|----------|
| Identity (ID-JAG tokens) | Relationship-based access |
| Coarse RBAC (groups) | Fine-grained permissions |
| Claims (Manager, Vacation, Clearance) | Hierarchies (clearance chain) |
| Token exchange per agent | Contextual conditions (vacation) |

**Why Both?**
- Okta: "Who is this user and what groups/claims do they have?"
- FGA: "Given their relationships, can they perform this specific action on this specific resource?"

**Demo Value:**
- Dynamic authorization without redeploying
- Audit trail of all access decisions
- Separation of identity (Okta) from authorization logic (FGA)

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| All requests denied | Verify FGA store/model env vars on Render |
| Clearance not working | FGA structural tuples (clearance chain, item requirements) |
| Manager tuple issues | `fga tuple read` to verify user relationships |
| Wrong claims | Check Custom Auth Server (Inventory) claim mappings |
