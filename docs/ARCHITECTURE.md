# Architecture

## Control planes implemented so far (Phase 1-2)

```
                 ┌─────────────────────────────────────────┐
                 │              ScopeGuard                  │  <- every action
                 │  (authorized hosts, risk tiers, rate     │     passes through
                 │   limits, approval tokens, audit log)    │     this or it
                 └──────────────────┬────────────────────────┘     never happens
                                    │ ALLOW / DENY / REQUIRES_APPROVAL
                                    ▼
   ┌─────────────────────┐   ┌──────────────────────┐   ┌────────────────────┐
   │   Content Isolation   │  │   Skill Registry      │  │  Execution Ledger   │
   │  wraps ALL target-    │  │  (Level 1 metadata    │  │  hierarchical state │
   │  origin bytes; screens│  │   always loaded ->    │  │  tree, checkpoints, │
   │  for injection before │  │   Level 2 SKILL.md    │  │  budget circuit     │
   │  a model ever sees it │  │   loaded on selection) │  │  breaker per scope  │
   └───────────┬───────────┘  └──────────┬───────────┘  └──────────┬──────────┘
               │                          │                         │
               └────────────┬─────────────┴─────────────┬──────────┘
                             ▼                           ▼
                     ┌───────────────────────────────────────┐
                     │           Evidence Store                │
                     │  hash-chained, append-only, tracks      │
                     │  POSITIVE / NEGATIVE / NEUTRAL evidence │
                     └───────────────────┬──────────────────────┘
                                         ▼
                     ┌───────────────────────────────────────┐
                     │   Verification Loop                     │
                     │   Researcher -> Skeptic -> Referee      │
                     │   (a claim can ONLY reach CONFIRMED if  │
                     │    a skeptic attempted disproof and     │
                     │    every check resolved cleanly)        │
                     └───────────────────────────────────────┘
```

## Design decisions and why

### Why SQLite for the Ledger instead of one JSON blob
A single growing JSON file is exactly the "monolithic interaction history"
that causes context rot and makes resumption expensive (you have to
deserialize and re-reason over everything). SQLite gives us:
- O(1)-ish lookup of "what's unresolved under Recon" via an indexed query,
  instead of scanning a blob.
- Independent sub-agents can each own a subtree without stepping on each
  other's writes (this matters once Phase 5's independent hypothesis
  branches land).
- The budget table lives right next to the state it's gating, so a
  circuit-breaker check is a single query, not a separate service.

### Why the Skeptic is a separate function, not a second prompt in the same call
It is tempting to ask one model call to "find a bug AND double check
yourself." In practice this collapses into the same reasoning pass wearing
two hats — the real-world hackbot case study this repo is modeled on found
that a *structurally separate* validator (different context, explicitly
rewarded for disproof) is what actually moved the false-positive rate,
not a self-critique instruction appended to the same prompt. This
architecture makes that separation impossible to accidentally skip:
`VerificationLoop.run()` requires both a `researcher_fn` and a
`skeptic_fn`, and `_referee()` refuses to promote a finding if
`disproof_attempted` is False.

### Why Content Isolation is its own module and not "just a prompt instruction"
"Remember, don't trust the target" as a system-prompt line is exactly the
kind of instruction that competes with — and loses to — a cleverly crafted
piece of target content for the model's attention once that content is in
the same undifferentiated context. Wrapping every target-origin string in
an explicit `<untrusted_target_data>` envelope with a machine-detected
warning flag is a structural mitigation, not a request for good behavior.
It is not bulletproof (nothing is), but it removes the most common and
cheapest attack: plain-text override phrases sitting in a stack trace or a
JS comment.

### Why Skills don't execute anything themselves
`Skill` objects in this repo are pure data + text (metadata, SKILL.md,
references, scripts *paths*). The registry never executes a skill's
scripts on your behalf — that responsibility belongs to whatever
orchestrator wires this library to real tools (HTTP client, browser,
static analyzer). This keeps the trust boundary explicit: loading an
untrusted community skill's metadata for routing purposes is safe;
executing its scripts is a separate, much more consequential decision that
this library forces to be deliberate.

## Mapping back to MASTER SPEC sections

| Spec section | Implemented as |
|---|---|
| §1 Non-negotiable safety and scope | `agent_core/scope/guard.py` |
| §3 Persistent execution state | `agent_core/ledger/state_tree.py` |
| §4-5 Skill system + skill graph | `agent_core/skills/registry.py` |
| §9 Evidence-first model | `agent_core/evidence/store.py` |
| §10 Researcher/Skeptic/Referee | `agent_core/verification/loop.py` |
| §18 Skill supply chain | `SkillRegistry.route()`'s `trust_score` gate |
| (gap identified in review) Content isolation | `agent_core/content_isolation/sanitizer.py` |
| (gap identified in review) Hard budget circuit breaker | `ExecutionLedger.spend()` |
| §2, §6-8, §11-17, §19-21 | Not yet built — see `docs/ROADMAP.md` |
