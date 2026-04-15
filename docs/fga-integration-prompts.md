# FGA Integration Prompts

This document captures the prompts and instructions used to implement Auth0 FGA integration in the ProGear Sales AI demo.

---

## Session Context

**Date**: April 2026
**Goal**: Integrate Auth0 FGA with Okta to demonstrate "Better Together" - fine-grained authorization using Okta token claims

---

## Prompt 1: Initial Understanding

```
Hey Claude, looking at this code and wait for my ask - please read the docs and understand
the demo's value to Okta for AI Agents and the Workload Principal.
```

**Action**: Read codebase, O4AA documentation, understand demo architecture.

---

## Prompt 2: Read FGA Integration Plan

```
in the docs folder can you read purrfect-mapping-hare.md our plan to install the FGA SDK.
Please be sure to ask clarifying questions to ensure I can build out the best demo with
the Auth0 FGA that I have full access to. Customers have been asking for us to show this
with demo and its value. Remember its all about showing Okta and FGA better together
```

**Action**: Read the FGA integration plan, ask clarifying questions about:
- FGA credentials (ready?)
- Agent scope (inventory only vs all agents)
- Vacation status source (Okta claim vs UI toggle)
- UI changes (FGA explanation panel)

---

## Prompt 3: Implement FGA Integration

```
yes (proceed with implementation)
```

**Action**: Implemented:
1. `backend/auth/fga_client.py` - FGA SDK client
2. `backend/auth/fga_seed.py` - Seed script
3. Modified `backend/orchestrator/orchestrator.py` - Added FGA check node
4. Updated `.env.example` - FGA env vars
5. Created `FGAExplanationCard.tsx` - Frontend component
6. Updated `page.tsx` - Wired FGA panel

---

## Prompt 4: Debug LLM Routing Error

```
why I am getting this WARNING:orchestrator.orchestrator:LLM routing failed,
using keyword fallback: Expecting value: line 1 column 1 (char 0)
```

**Action**: Diagnosed JSON parsing issue with LLM response.

---

## Prompt 5: Switch to Raw Anthropic SDK

```
CAN YOU change the code to use antropic key and comment out other method for llm interaction.
Please share the details before making changes
```

**Action**: Proposed switching from `langchain-anthropic` to raw `anthropic` SDK.

**Follow-up**: `A` (confirm Option A - raw SDK)

**Changes**:
- Replaced `ChatAnthropic` with `anthropic.Anthropic`
- Updated `_router_node` and `_generate_response_node`
- Removed unused `langchain-anthropic`, `langchain-openai`, `openai` dependencies

---

## Prompt 6: Remove Unused Code

```
is this the only file need change for antropic llm interaction?
```

**Action**: Checked for other LangChain usages.

```
can you remove the unused
```

**Action**: Removed `backend/agents/` folder (unused agent classes), cleaned `requirements.txt`.

---

## Prompt 7: Debug FGA Denying All Users

```
getting this INFO:auth.fga_client:FGA check: user:bob.manager@atko.email manager
inventory_system:main_db (vacation=False) -> False
```

**Diagnosis**: FGA tuples only contained `mike.manager@atko.email`, not `bob.manager@atko.email`.

---

## Prompt 8: Dynamic FGA Using Token Claims

```
I do not want you to hard code the user instead I want you to read the token of the
authenticated user and then check the tuple. can you share your plan before you make changes
```

**Action**: Proposed claims-based FGA evaluation instead of tuple lookup.

**Plan**:
1. Read `is_a_manager` and `is_on_vacation` from Okta ID token claims
2. Evaluate FGA model logic locally using these claims
3. No FGA API calls needed, works for any authenticated user

```
yes (proceed)
```

**Changes**:
- Rewrote `backend/auth/fga_client.py` - Claims-based evaluation
- Updated `_fga_check_node` to read claims from `user_info`

---

## Prompt 9: Save Context

```
capture all the context and memory for next time if we need to restart the conversation.
Also create a file with all the prompts
```

**Action**: Created memory files and this prompts document.

---

## Key Implementation Decisions

### 1. Claims-Based FGA (Not Tuple Lookup)

**Problem**: FGA tuples require pre-seeding every user email.

**Solution**: Evaluate FGA model logic using Okta token claims:
```python
is_a_manager = user_info.get("is_a_manager", user_info.get("Manager", False))
is_on_vacation = user_info.get("is_on_vacation", user_info.get("Vacation", False))

# FGA logic: manager AND NOT on_vacation
if not is_a_manager:
    denied
elif is_on_vacation:
    denied
else:
    allowed
```

### 2. Raw Anthropic SDK (Not LangChain)

**Problem**: LangChain wrapper obscured errors.

**Solution**: Direct `anthropic` SDK:
```python
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model=LLM_MODEL_NAME,
    max_tokens=500,
    messages=[{"role": "user", "content": prompt}]
)
result = response.content[0].text
```

### 3. Required Okta Claims

On **Org Authorization Server** (ID Token):

| Claim Name | Value | Purpose |
|------------|-------|---------|
| `Manager` | `user.is_a_manager` | User has manager role |
| `Vacation` | `user.is_on_vacation` | User on vacation |

**Path**: Okta Admin → Security → API → Authorization Servers → Claims → Add Claim

---

## Files Modified

| File | Change |
|------|--------|
| `backend/auth/fga_client.py` | Rewritten for claims-based FGA |
| `backend/auth/fga_seed.py` | Created (reference only) |
| `backend/orchestrator/orchestrator.py` | Raw Anthropic SDK, FGA check node |
| `backend/requirements.txt` | Removed unused LangChain deps |
| `backend/agents/` | Deleted (unused) |
| `.env.example` | Added FGA env vars |
| `packages/.../FGAExplanationCard.tsx` | Created FGA UI panel |
| `packages/.../page.tsx` | Added FGA card to dashboard |

---

## Testing Checklist

1. [ ] Ensure `ANTHROPIC_API_KEY` is set
2. [ ] Ensure Okta claims (`Manager`, `Vacation`) are on Org Auth Server
3. [ ] Set user's `is_a_manager` attribute in Okta user profile
4. [ ] Test: Manager not on vacation → Inventory access ALLOWED
5. [ ] Test: Manager on vacation → Inventory access DENIED
6. [ ] Test: Non-manager → Inventory access DENIED
7. [ ] Verify FGA panel shows decision reason in UI
