# ProGear Sales AI — Demo Video Script

**Runtime target:** 4–6 minutes (~5:10)
**Audience:** Mixed / executive (security buyers, IAM leaders, curious CTOs)
**Theme:** Governing AI agents with Okta + Auth0 FGA — identity decides *who*, FGA decides *what they can do right now*.

> Narration lines are in quotes. `[ACTION]` cues describe what to do on screen. `[B-ROLL]` cues call out inserts. `[LOWER THIRD]` calls out on-screen text.

---

## Demo context & tone

Use this section to frame the demo — either as opening slides before Scene 1, a written intro on the landing page, or as the presenter's mental model while recording.

### The world we're in

Enterprises are deploying AI agents faster than they're governing them. An agent that can "check inventory" today can "update inventory" tomorrow — and every action it takes is really an action taken on behalf of a specific human, with a specific role, a specific status, and a specific clearance. The gap between **who the human is** and **what the agent just did** is where governance either holds or breaks.

### What this demo is — and isn't

- **It is**: a live, working multi-agent app (ProGear Sales AI) showing identity and fine-grained authorization working together in real time. Every decision you'll see — allow or deny — is rendered from actual Okta tokens and actual Auth0 FGA checks. Nothing is faked for the video.
- **It isn't**: a product pitch, a model-accuracy demo, or an agent-framework comparison. The AI is the vehicle; the point is the **governance layer underneath**.

### The mental model to hold

Two questions, two systems, one decision:

| Question | Answered by | Example |
|---|---|---|
| *Who is this user, and which agent can act for them?* | **Okta** (identity, token exchange, scopes) | Bob gets an ID-JAG token; backend swaps it for an Inventory-agent access token |
| *Given their relationships and current context, can they do **this** to **this** right now?* | **Auth0 FGA** (fine-grained authorization) | "Active manager" means manager *and not on vacation* — evaluated per request |

If you take nothing else from the demo, take this: **identity decides who, FGA decides what they can do right now.**

### Tone for narration

- Confident, not salesy. The software does the talking — let the right-hand panel land the point.
- Plain English. Say "allowed" and "denied," not "policy evaluation succeeded."
- Pause after each FGA decision. Let viewers read the card.
- When something is denied, **celebrate it** — that's the feature working, not a bug.

### Who should watch

- **Security & IAM leaders** evaluating how to govern AI agents without rebuilding their stack
- **CTOs & platform architects** weighing build-vs-buy on authorization
- **Developers** looking for a reference pattern: Okta tokens in, FGA checks before action, audit trail out

---

## Pre-recording checklist

- [ ] Okta profile for Bob set to baseline: `Manager=true, Vacation=false, Clearance=5`
- [ ] Okta admin tab open in a separate browser window, ready to toggle Bob's profile
- [ ] Frontend running (`/` chat page) and `/architecture` page pre-loaded in a second tab
- [ ] Browser zoom ~110%, right-side panel (Agent Flow / Token / FGA) expanded
- [ ] Chat history cleared; bookmark bar hidden; notifications off
- [ ] Record at 1080p minimum; mic levels checked; background quiet

**Reset after recording:** restore Bob to `Manager=true, Vacation=false, Clearance=5`.

---

## Scene 1 — Hook (0:00 – 0:25)

`[B-ROLL]` Fast montage: AI agent headlines, a chat UI taking action, a security alert. 3–4 seconds.

`[LOWER THIRD]` *"AI agents are the new employees — who governs what they can do?"*

> "AI agents are becoming digital co-workers. They read data, call APIs, and take action for real people. The problem: the human's role, status, and clearance has to follow every agent action — or you've just given a tireless new employee unchecked access."
>
> "In the next five minutes, I'll show how **Okta** and **Auth0 FGA** solve this together, live."

---

## Scene 2 — Meet the app (0:25 – 0:55)

`[ACTION]` Cut to the ProGear chat UI at `/`. Pan across interface once.

`[LOWER THIRD]` *"Four specialist agents, one governed workflow."*

> "This is ProGear Sales AI — a multi-agent assistant for a sporting goods company. A sales rep types a request in plain English, and a router picks the right specialist: **Sales**, **Inventory**, **Customer**, or **Pricing**."
>
> "The right-hand panel makes the whole decision visible — which agent ran, which tokens were exchanged, which scopes were granted, and whether FGA allowed or blocked the action."

---

## Scene 3 — How it works in 30 seconds (0:55 – 1:30)

`[ACTION]` Switch to the `/architecture` tab. Draw attention with cursor.

> "Under the hood: Okta authenticates the user and issues an ID-JAG token. For each specialist agent, the backend exchanges that token for a narrower, purpose-built access token — one agent, one audience, one set of scopes. That's **Okta's job**: *who is this user, and which agent can act for them?*"
>
> "Then — before the Inventory agent does anything sensitive — we ask **Auth0 FGA** a second question: *given this user's relationships and current context, are they allowed to perform this specific action on this specific resource?* That's fine-grained authorization."

`[LOWER THIRD]` *"Okta = who. FGA = what, on which resource, right now."*

---

## Scene 4 — Happy path (1:30 – 2:30)

`[ACTION]` Back to the chat UI. Show Bob's identity card: Manager ✓, Vacation ✗, Clearance 5.

> "Meet Bob — warehouse manager at ProGear. In Okta: manager, not on vacation, clearance five. Let's watch him work."

`[ACTION]` Type: **"How many basketballs do we have in stock?"**

`[ACTION]` As response streams, point to right pane: green Inventory flow, ID-JAG → access token swap, FGA `can_view` → **ALLOWED**. Let it breathe 2–3 seconds.

> "Router picks Inventory. Okta issues a scoped access token. FGA checks `can_view` — allowed, because Bob is an active manager: manager *and* not on vacation."

`[ACTION]` Type: **"Add 50 basketballs to widget-a."**

`[ACTION]` Point at FGA card showing `can_update` allowed, clearance 5 ≥ required 3.

> "Now Bob wants to write, not just read. `can_update` also checks clearance. Bob has five; widget-a requires three. Approved — and the right pane shows exactly which rule fired."

---

## Scene 5 — The vacation moment (2:30 – 3:40)

`[LOWER THIRD]` *"What happens when Bob goes on vacation?"*

`[ACTION]` Switch to the Okta admin tab. Zoom in on Bob's profile.

> "Here's where it gets interesting. In most systems, revoking access means deprovisioning — a ticket, a script, a delay. Watch this."

`[ACTION]` Toggle `is_on_vacation` → **true**. Save.

> "One attribute flipped. No code deployed. No tokens revoked. No FGA tuples rewritten."

`[ACTION]` Back to chat. Type: **"Add 25 basketballs to widget-a."**

`[ACTION]` Response denied. Agent Flow red. FGA card shows contextual tuple `on_vacation` and rule `active_manager = manager but not on_vacation` → **denied**.

> "Denied instantly. FGA evaluated a **contextual tuple** — vacation passed in with the request, not stored. Bob is still a manager, still cleared — but the policy says an active manager isn't on vacation. Right now, he isn't active."
>
> "Flip it back when he returns, and access returns with him. That's dynamic, real-time authorization."

`[ACTION]` Toggle vacation back to **false** for the next scene.

---

## Scene 6 — View vs modify (3:40 – 4:40)

`[LOWER THIRD]` *"Not every action needs the same clearance."*

`[ACTION]` In Okta, drop Bob's `clearance_level` to **2**. Save.

> "One more scenario. ProGear has a classified part that requires clearance seven to modify. Let's drop Bob to clearance two."

`[ACTION]` Back to chat. Type: **"What classified parts do we have?"**

`[ACTION]` Allowed. Point to FGA card: `can_view` allowed, clearance not evaluated for reads.

> "He can *see* them. `can_view` only needs an active manager — reading the inventory list is fine."

`[ACTION]` Type: **"Update classified-part quantity to 10."**

`[ACTION]` Denied. FGA card shows clearance 2 < required 7 in red.

> "But modifying? Denied. `can_update` needs clearance *plus* active manager. Level two is below the required seven — and FGA tells us exactly why. That's the audit trail security teams have been asking for."

`[ACTION]` Reset Bob's clearance to 5.

---

## Scene 7 — Close (4:40 – 5:10)

`[LOWER THIRD]` *"Okta + Auth0 FGA — governance for the agentic era."*

> "Three things enterprises struggle with — solved in under five minutes. An AI agent that inherits real-time identity posture. Authorization that lives outside the application, so a profile toggle updates policy everywhere. And a visible audit trail on every decision."
>
> "Okta gives you identity. Auth0 FGA gives you fine-grained control. Together, they let you say yes to AI agents without giving up control."

`[B-ROLL]` End card: Okta logo, Auth0 FGA logo, CTA link.

---

## Timing summary

| Scene | Start | End | Duration |
|-------|-------|-----|----------|
| 1. Hook | 0:00 | 0:25 | 0:25 |
| 2. The app | 0:25 | 0:55 | 0:30 |
| 3. How it works | 0:55 | 1:30 | 0:35 |
| 4. Happy path | 1:30 | 2:30 | 1:00 |
| 5. Vacation moment | 2:30 | 3:40 | 1:10 |
| 6. View vs modify | 3:40 | 4:40 | 1:00 |
| 7. Close | 4:40 | 5:10 | 0:30 |
| **Total** | | | **~5:10** |

Buffer: ~30 seconds for pauses and transitions. To trim to 4 min, drop Scene 3 (or cut it to 15s of narration over the chat UI). To stretch to 6 min, linger longer on each FGA card after a decision and read the rules aloud.

---

## Fallback / recovery cues

| If… | Do this |
|-----|---------|
| Chat response is slow | Don't fill silence — narrate what the right pane *will* show |
| Okta change hasn't propagated | Wait ~20 seconds; the access token caches briefly. Hard-refresh the chat if needed |
| Unexpected result | Point to the FGA explanation card and say: "This is the audit trail at work — let's look at why." Cut in post if needed |

---

*Companion docs: `DEMO_SCRIPT.md` (scenario reference) and `DEMO_SCRIPT_DETAILED.md` (long-form technical walkthrough).*
