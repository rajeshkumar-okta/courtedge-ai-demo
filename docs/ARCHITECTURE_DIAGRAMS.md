# ProGear Sales AI - Architecture Diagrams
## Okta + Auth0 FGA Integration

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ProGear Sales AI Platform                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌──────────────┐         ┌──────────────────────────────────────────────┐    │
│   │              │         │              Backend Orchestrator             │    │
│   │    React     │  REST   │  ┌────────────┐  ┌────────────┐  ┌────────┐ │    │
│   │    Frontend  │◄───────►│  │   Router   │  │   Token    │  │  FGA   │ │    │
│   │              │         │  │   Agent    │  │  Exchange  │  │ Client │ │    │
│   │  • Chat UI   │         │  └─────┬──────┘  └─────┬──────┘  └───┬────┘ │    │
│   │  • Agent Flow│         │        │              │              │      │    │
│   │  • FGA Card  │         │        ▼              ▼              ▼      │    │
│   │  • Tokens    │         │  ┌─────────────────────────────────────────┐│    │
│   │              │         │  │            AI Agents (Claude)           ││    │
│   └──────────────┘         │  │  Sales │ Inventory │ Customer │ Pricing ││    │
│                            │  └─────────────────────────────────────────┘│    │
│                            └──────────────────────────────────────────────┘    │
│                                        │              │                        │
│                                        │              │                        │
└────────────────────────────────────────┼──────────────┼────────────────────────┘
                                         │              │
                    ┌────────────────────┘              └────────────────────┐
                    │                                                        │
                    ▼                                                        ▼
    ┌───────────────────────────────┐                    ┌───────────────────────────────┐
    │            OKTA               │                    │         AUTH0 FGA             │
    │                               │                    │                               │
    │  ┌─────────────────────────┐  │                    │  ┌─────────────────────────┐  │
    │  │   Org Auth Server       │  │                    │  │    Authorization Model  │  │
    │  │   (Identity/Groups)     │  │                    │  │    • inventory_system   │  │
    │  └─────────────────────────┘  │                    │  │    • inventory_item     │  │
    │                               │                    │  │    • clearance_level    │  │
    │  ┌─────────────────────────┐  │                    │  └─────────────────────────┘  │
    │  │ Custom Auth Servers     │  │                    │                               │
    │  │ • Sales    • Inventory  │  │                    │  ┌─────────────────────────┐  │
    │  │ • Customer • Pricing    │  │                    │  │    Relationship Tuples  │  │
    │  │                         │  │                    │  │    • manager → system   │  │
    │  │ Claims:                 │  │                    │  │    • clearance grants   │  │
    │  │ • Manager               │  │    ─────────────►  │  │    • item hierarchies   │  │
    │  │ • Vacation              │  │    Tuple Sync      │  └─────────────────────────┘  │
    │  │ • Clearance             │  │                    │                               │
    │  └─────────────────────────┘  │                    │  ┌─────────────────────────┐  │
    │                               │                    │  │    Check API            │  │
    │  ┌─────────────────────────┐  │                    │  │    + Contextual Tuples  │  │
    │  │   User Directory        │  │                    │  │    (vacation status)    │  │
    │  │   (bob.manager@atko)    │  │                    │  └─────────────────────────┘  │
    │  └─────────────────────────┘  │                    │                               │
    └───────────────────────────────┘                    └───────────────────────────────┘
```

---

## 2. Token Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           3-Token Authentication Flow                           │
└─────────────────────────────────────────────────────────────────────────────────┘

    User                    Frontend                 Backend                 Okta
     │                         │                       │                       │
     │  1. Login              │                       │                       │
     │ ───────────────────────►                       │                       │
     │                         │  2. OIDC Auth        │                       │
     │                         │ ──────────────────────────────────────────────►
     │                         │                       │                       │
     │                         │  3. ID Token (Org Auth Server)                │
     │                         │ ◄──────────────────────────────────────────────
     │                         │                       │                       │
     │                         │  4. Token Exchange Request                    │
     │                         │ ──────────────────────►                       │
     │                         │                       │  5. Exchange ID Token │
     │                         │                       │ ──────────────────────►
     │                         │                       │                       │
     │                         │                       │  6. ID-JAG Token      │
     │                         │                       │ ◄──────────────────────
     │                         │                       │                       │
     │                         │                       │  7. Exchange for      │
     │                         │                       │     Agent Scopes      │
     │                         │                       │ ──────────────────────►
     │                         │                       │                       │
     │                         │                       │  8. Access Token      │
     │                         │                       │  (with custom claims) │
     │                         │                       │ ◄──────────────────────
     │                         │                       │                       │


┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Token Types                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────┐  │
│  │    ID Token      │    │   ID-JAG Token   │    │     Access Token         │  │
│  │  (Org Server)    │───►│  (Intermediate)  │───►│  (Custom Auth Server)    │  │
│  ├──────────────────┤    ├──────────────────┤    ├──────────────────────────┤  │
│  │ • sub            │    │ • sub            │    │ • sub                    │  │
│  │ • email          │    │ • email          │    │ • email                  │  │
│  │ • groups         │    │ • aud (JAG)      │    │ • scp (agent scopes)     │  │
│  │ • name           │    │                  │    │ • Manager    ◄── Custom  │  │
│  │                  │    │                  │    │ • Vacation   ◄── Claims  │  │
│  │                  │    │                  │    │ • Clearance  ◄── From    │  │
│  │                  │    │                  │    │                  Okta    │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────────────┘  │
│         │                                                    │                  │
│         │              Identity                               │  Authorization  │
│         └────────────────────────────────────────────────────┘                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. FGA Authorization Model

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Auth0 FGA Model: ProGear New                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TYPE: user                                         │
│                         (Human principals)                                      │
│                                                                                 │
│                     ┌─────────────────────────┐                                 │
│                     │  user:bob.manager@atko  │                                 │
│                     └───────────┬─────────────┘                                 │
│                                 │                                               │
│               ┌─────────────────┼─────────────────┐                             │
│               │                 │                 │                             │
│               ▼                 ▼                 ▼                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐
│ TYPE: inventory_    │    │ TYPE: clearance_    │    │ TYPE: inventory_item    │
│       system        │    │       level         │    │                         │
├─────────────────────┤    ├─────────────────────┤    ├─────────────────────────┤
│                     │    │                     │    │                         │
│ RELATIONS:          │    │ RELATIONS:          │    │ RELATIONS:              │
│                     │    │                     │    │                         │
│ • manager [user]    │    │ • next_higher       │    │ • parent [inv_system]   │
│                     │    │   [clearance_level] │    │                         │
│ • on_vacation [user]│    │                     │    │ • required_clearance    │
│   (contextual)      │    │ • granted_to [user] │    │   [clearance_level]     │
│                     │    │                     │    │                         │
│ • active_manager:   │    │ • holder:           │    │ • has_clearance:        │
│   manager BUT NOT   │    │   granted_to OR     │    │   holder FROM           │
│   on_vacation       │    │   holder FROM       │    │   required_clearance    │
│                     │    │   next_higher       │    │                         │
│ • can_manage:       │    │                     │    │ • can_view:             │
│   active_manager    │    │   ▲                 │    │   can_manage FROM parent│
│                     │    │   │ HIERARCHY       │    │                         │
└─────────────────────┘    │   │                 │    │ • can_update:           │
         │                 └───┼─────────────────┘    │   has_clearance AND     │
         │                     │                      │   can_manage FROM parent│
         │                     │                      │                         │
         └─────────────────────┼──────────────────────┤                         │
                               │                      └─────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────────────────────┐
│                         CLEARANCE HIERARCHY                                     │
│                                                                                 │
│    ┌───┐     ┌───┐     ┌───┐     ┌───┐     ┌───┐     ┌───┐     ┌───┐          │
│    │ 1 │◄────│ 2 │◄────│ 3 │◄────│ 4 │◄────│ 5 │◄────│ 6 │◄────│ 7 │ ...      │
│    └───┘     └───┘     └───┘     └───┘     └───┘     └───┘     └───┘          │
│      ▲                                       ▲                                  │
│      │                                       │                                  │
│      │         If user has level 5           │                                  │
│      └───────────────────────────────────────┘                                  │
│                 They get access to                                              │
│                 levels 1, 2, 3, 4, 5                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Permission Evaluation Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FGA Permission Check: can_update                           │
└─────────────────────────────────────────────────────────────────────────────────┘

  User Request: "Add 50 widgets to inventory"
        │
        ▼
┌───────────────────┐
│  Extract Claims   │
│  from Access Token│
├───────────────────┤
│ Manager: true     │
│ Vacation: false   │
│ Clearance: 5      │
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                        FGA Check Request                                       │
│                                                                                │
│   User:     user:bob.manager@atko.email                                       │
│   Relation: can_update                                                         │
│   Object:   inventory_item:widget-a                                           │
│                                                                                │
│   Contextual Tuples: (if vacation=true)                                       │
│   └─► user:bob... → on_vacation → inventory_system:warehouse                  │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                        FGA Evaluation Tree                                     │
│                                                                                │
│   can_update on inventory_item:widget-a ?                                     │
│        │                                                                       │
│        ├──► has_clearance ?                                                   │
│        │         │                                                             │
│        │         └──► holder FROM required_clearance ?                        │
│        │                    │                                                  │
│        │                    └──► widget-a requires clearance_level:3          │
│        │                              │                                        │
│        │                              └──► Does Bob hold level 3?             │
│        │                                        │                              │
│        │                                        └──► Bob has level 5          │
│        │                                              │                        │
│        │                                              └──► Walk hierarchy:    │
│        │                                                   5 → 4 → 3 ✓        │
│        │                                                                       │
│        │         ┌──────────────────────────────────────────────────┐         │
│        │         │ has_clearance = TRUE (5 grants access to 3)      │         │
│        │         └──────────────────────────────────────────────────┘         │
│        │                                                                       │
│        └──► can_manage FROM parent ?                                          │
│                  │                                                             │
│                  └──► parent = inventory_system:warehouse                     │
│                            │                                                   │
│                            └──► active_manager on warehouse ?                 │
│                                      │                                         │
│                                      ├──► manager ? ✓ (tuple exists)          │
│                                      │                                         │
│                                      └──► NOT on_vacation ?                   │
│                                                 │                              │
│                                                 └──► No contextual tuple      │
│                                                      (vacation=false)         │
│                                                      ✓ NOT on_vacation        │
│                                                                                │
│                  ┌──────────────────────────────────────────────────┐         │
│                  │ can_manage = TRUE (active manager)               │         │
│                  └──────────────────────────────────────────────────┘         │
│                                                                                │
│   ┌────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                        │  │
│   │   RESULT: can_update = has_clearance AND can_manage                   │  │
│   │                      = TRUE AND TRUE                                   │  │
│   │                      = TRUE ✓ ALLOWED                                  │  │
│   │                                                                        │  │
│   └────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Request Sequence Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        End-to-End Request Flow                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

 User        Frontend      Backend       Okta Auth      FGA API      AI Agent
  │             │            │           Servers          │             │
  │             │            │              │             │             │
  │  "Add 50    │            │              │             │             │
  │  widgets"   │            │              │             │             │
  │────────────►│            │              │             │             │
  │             │            │              │             │             │
  │             │  POST /chat│              │             │             │
  │             │  + ID Token│              │             │             │
  │             │───────────►│              │             │             │
  │             │            │              │             │             │
  │             │            │  1. Exchange │              │             │
  │             │            │     ID→JAG   │              │             │
  │             │            │─────────────►│              │             │
  │             │            │◄─────────────│              │             │
  │             │            │              │             │             │
  │             │            │  2. Route to Inventory     │             │
  │             │            │     (detect "add")         │             │
  │             │            │              │             │             │
  │             │            │  3. Exchange │              │             │
  │             │            │     JAG→Access             │             │
  │             │            │─────────────►│              │             │
  │             │            │◄─────────────│              │             │
  │             │            │   (Manager,  │             │             │
  │             │            │    Vacation, │             │             │
  │             │            │    Clearance)│             │             │
  │             │            │              │             │             │
  │             │            │  4. Ensure Manager Tuple   │             │
  │             │            │────────────────────────────►│             │
  │             │            │◄────────────────────────────│             │
  │             │            │              │             │             │
  │             │            │  5. Ensure Clearance Tuple │             │
  │             │            │────────────────────────────►│             │
  │             │            │◄────────────────────────────│             │
  │             │            │              │             │             │
  │             │            │  6. Check can_update       │             │
  │             │            │     + contextual tuples    │             │
  │             │            │────────────────────────────►│             │
  │             │            │◄────────────────────────────│             │
  │             │            │     allowed: true          │             │
  │             │            │              │             │             │
  │             │            │  7. Invoke Agent           │             │
  │             │            │────────────────────────────────────────────►
  │             │            │◄────────────────────────────────────────────
  │             │            │              │             │             │
  │             │  Response  │              │             │             │
  │             │  + flow    │              │             │             │
  │             │  + FGA info│              │             │             │
  │             │◄───────────│              │             │             │
  │             │            │              │             │             │
  │  Display    │            │              │             │             │
  │  result     │            │              │             │             │
  │◄────────────│            │              │             │             │
  │             │            │              │             │             │
```

---

## 6. Tuple Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     Dynamic Tuple Management                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

                              OKTA PROFILE CHANGE
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   ┌─────────────────────┐         ┌─────────────────────┐                      │
│   │  Manager: true→false│         │  Clearance: 5→2     │                      │
│   └──────────┬──────────┘         └──────────┬──────────┘                      │
│              │                               │                                  │
│              ▼                               ▼                                  │
│   ┌─────────────────────┐         ┌─────────────────────┐                      │
│   │ ensure_manager_     │         │ ensure_clearance_   │                      │
│   │ relationship()      │         │ tuple()             │                      │
│   └──────────┬──────────┘         └──────────┬──────────┘                      │
│              │                               │                                  │
│              ▼                               ▼                                  │
│   ┌─────────────────────┐         ┌─────────────────────┐                      │
│   │ DELETE tuple:       │         │ DELETE levels 1-10  │                      │
│   │ bob → manager →     │         │ EXCEPT level 2      │                      │
│   │ warehouse           │         │                     │                      │
│   └─────────────────────┘         │ CREATE:             │                      │
│                                   │ bob → granted_to →  │                      │
│                                   │ clearance_level:2   │                      │
│                                   └─────────────────────┘                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                        TUPLE TYPES                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STORED TUPLES (Persistent in FGA)          CONTEXTUAL TUPLES (Per-Request)    │
│  ─────────────────────────────────          ───────────────────────────────    │
│                                                                                 │
│  ┌─────────────────────────────┐            ┌─────────────────────────────┐    │
│  │ Manager Relationship        │            │ Vacation Status             │    │
│  │                             │            │                             │    │
│  │ user:bob                    │            │ Passed with each FGA check  │    │
│  │   ↓ manager                 │            │ if user.is_on_vacation=true │    │
│  │ inventory_system:warehouse  │            │                             │    │
│  │                             │            │ user:bob                    │    │
│  │ Created/Deleted based on    │            │   ↓ on_vacation             │    │
│  │ Okta Manager claim          │            │ inventory_system:warehouse  │    │
│  └─────────────────────────────┘            │                             │    │
│                                             │ NOT stored - evaluated      │    │
│  ┌─────────────────────────────┐            │ in real-time                │    │
│  │ Clearance Grant             │            └─────────────────────────────┘    │
│  │                             │                                                │
│  │ user:bob                    │            WHY CONTEXTUAL?                     │
│  │   ↓ granted_to              │            ─────────────────                   │
│  │ clearance_level:5           │            • Immediate effect                  │
│  │                             │            • No sync delay                     │
│  │ Single tuple per user       │            • No stale data                     │
│  │ (old levels deleted)        │            • Real-time condition               │
│  └─────────────────────────────┘                                                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Security Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Security Boundaries                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  PUBLIC ZONE                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         React Frontend                                     │ │
│  │                     (Browser - Untrusted)                                  │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                    │ HTTPS + ID Token                          │
└────────────────────────────────────┼────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BACKEND ZONE (Trusted)                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │ │
│  │   │  Validate   │    │   Token     │    │    FGA      │                  │ │
│  │   │  ID Token   │───►│  Exchange   │───►│   Checks    │                  │ │
│  │   │  (Okta SDK) │    │  (OAuth2)   │    │  (FGA SDK)  │                  │ │
│  │   └─────────────┘    └─────────────┘    └─────────────┘                  │ │
│  │                                                │                          │ │
│  │                                                ▼                          │ │
│  │   ┌───────────────────────────────────────────────────────────────────┐  │ │
│  │   │                    AI Agent Invocation                            │  │ │
│  │   │              (Only if FGA check passes)                           │  │ │
│  │   └───────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                    │                                    │                       │
└────────────────────┼────────────────────────────────────┼───────────────────────┘
                     │                                    │
        mTLS/OAuth2  │                         Client     │
                     │                         Credentials│
                     ▼                                    ▼
┌─────────────────────────────┐          ┌─────────────────────────────┐
│      OKTA CLOUD             │          │       FGA CLOUD             │
│  ┌───────────────────────┐  │          │  ┌───────────────────────┐  │
│  │ • Token Validation    │  │          │  │ • Tuple Storage       │  │
│  │ • Token Exchange      │  │          │  │ • Permission Checks   │  │
│  │ • Claims Issuance     │  │          │  │ • Audit Logs          │  │
│  │ • User Directory      │  │          │  │ • Model Evaluation    │  │
│  └───────────────────────┘  │          │  └───────────────────────┘  │
└─────────────────────────────┘          └─────────────────────────────┘
```

---

## 8. Component Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Component Responsibilities                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────┬───────────────────────────────────────────────────────────┐
│    COMPONENT      │                    RESPONSIBILITY                         │
├───────────────────┼───────────────────────────────────────────────────────────┤
│                   │                                                           │
│  OKTA ORG         │  • User authentication (OIDC)                            │
│  AUTH SERVER      │  • ID Token issuance                                      │
│                   │  • Group membership (RBAC)                                │
│                   │                                                           │
├───────────────────┼───────────────────────────────────────────────────────────┤
│                   │                                                           │
│  OKTA CUSTOM      │  • Agent-specific scopes                                  │
│  AUTH SERVERS     │  • Custom claims (Manager, Vacation, Clearance)           │
│  (4 servers)      │  • Access token for each agent domain                     │
│                   │                                                           │
├───────────────────┼───────────────────────────────────────────────────────────┤
│                   │                                                           │
│  AUTH0 FGA        │  • Relationship storage (tuples)                          │
│                   │  • Permission evaluation (ReBAC + ABAC)                   │
│                   │  • Hierarchy traversal (clearance levels)                 │
│                   │  • Contextual condition evaluation                        │
│                   │                                                           │
├───────────────────┼───────────────────────────────────────────────────────────┤
│                   │                                                           │
│  BACKEND          │  • Token exchange orchestration                           │
│  ORCHESTRATOR     │  • Claim extraction                                       │
│                   │  • Tuple synchronization                                  │
│                   │  • FGA check coordination                                 │
│                   │  • Agent routing and invocation                           │
│                   │                                                           │
├───────────────────┼───────────────────────────────────────────────────────────┤
│                   │                                                           │
│  FRONTEND         │  • User interaction (chat)                                │
│                   │  • Token flow visualization                               │
│                   │  • FGA decision display                                   │
│                   │  • Agent status indicators                                │
│                   │                                                           │
└───────────────────┴───────────────────────────────────────────────────────────┘
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        OKTA + FGA QUICK REFERENCE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  OKTA DOES:                        FGA DOES:                                   │
│  ──────────                        ─────────                                   │
│  ✓ "Who is this user?"             ✓ "Can user X do action Y on resource Z?"  │
│  ✓ "What groups are they in?"      ✓ "Walk relationship hierarchy"            │
│  ✓ "Issue scoped tokens"           ✓ "Evaluate contextual conditions"         │
│  ✓ "Provide custom claims"         ✓ "Audit every decision"                   │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PERMISSION MATRIX:                                                             │
│  ─────────────────                                                              │
│  ┌──────────────────┬─────────────┬───────────────────────────────────────┐    │
│  │ Operation        │ FGA Check   │ Requirements                          │    │
│  ├──────────────────┼─────────────┼───────────────────────────────────────┤    │
│  │ View Inventory   │ can_view    │ active_manager (not on vacation)      │    │
│  │ Update Inventory │ can_update  │ active_manager + clearance ≥ required │    │
│  │ Alerts           │ (none)      │ Okta RBAC only                        │    │
│  └──────────────────┴─────────────┴───────────────────────────────────────┘    │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  TUPLE TYPES:                                                                   │
│  ────────────                                                                   │
│  Stored:      manager → warehouse, clearance → level N                         │
│  Contextual:  on_vacation (passed per-request, not stored)                     │
│  Structural:  clearance chain (1→2→3...10), item→parent, item→required_level  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```
