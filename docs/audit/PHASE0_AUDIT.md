# Phase 0 Audit — security-research-agent vs V2 Spec

**Date:** 2026-09-22  
**Repo:** Tawffik/security-research-agent  
**Tests at audit:** 35 passed  
**Branch baseline:** main (shallow)

---

## 1. What already exists (keep and freeze)

| Component | Path | Status | Notes |
|-----------|------|--------|-------|
| ScopeGuard | `src/agent_core/scope/guard.py` | ✅ Solid | RiskTier, ApprovalToken, fail-closed, audit log |
| Content Isolation | `src/agent_core/content_isolation/sanitizer.py` | ✅ Solid | UntrustedBlock, injection heuristics |
| Execution Ledger | `src/agent_core/ledger/state_tree.py` | ✅ Solid | SQLite, NodeStatus, budget circuit breaker, resume |
| Evidence Store | `src/agent_core/evidence/store.py` | ✅ Solid | Hash chain, polarity, FindingStatus lifecycle |
| Verification Loop | `src/agent_core/verification/loop.py` | ✅ Solid | Researcher / Skeptic / Referee separation |
| Skill Registry | `src/agent_core/skills/registry.py` | ✅ Solid | Progressive disclosure, trust_score gate, deps |
| Orchestrator | `src/agent_core/orchestrator/engagement.py` | ✅ Thin Phase A | Scope + budget + skills + verification |
| Transport | `src/agent_core/orchestrator/transport.py` | ✅ Opt-in HTTP | Mock default; HttpTransport gated |
| Skills (3) | `skills/` | ✅ Examples | recon-js-surface, authz-idor-analysis, report-generator |
| CI | `.github/workflows/ci.yml` | ✅ Present | |
| Tests | `tests/` | ✅ 35 green | |

**Non-negotiables already enforced (do not regress):**
1. Every outbound action through `ScopeGuard.authorize()`
2. Every claim traces to Evidence; CONFIRMED requires Skeptic disproof attempt
3. Target content is never instruction (`wrap_target_content`)
4. Skill trust_score gate for RiskTier
5. Negative evidence / rejected nodes retained

---

## 2. Gaps vs V2 Spec (ordered by Sprint priority)

### Sprint 1 (this sprint) — Schemas / Contracts
- [ ] Canonical Pydantic schemas: Engagement, Actor, Resource, Hypothesis, Experiment, Decision, Finding, Opportunity, Unknown, Belief
- [ ] Contract tests for schema validation
- [ ] Document freeze of foundation APIs

### Sprint 2 — Recon Adapter + Target Model
- [ ] `ReconResultAdapter` (normalize BugBountyCI artifacts)
- [ ] Target Model (Actor / Role / Resource / Endpoint / Workflow / State)
- [ ] Target Graph (Actor → Action → Resource → Condition)

### Sprint 3 — Opportunity / Unknown / Belief
- [ ] Opportunity Engine (surface ranking without live traffic)
- [ ] Unknown Engine
- [ ] Belief State + contradictions + staleness

### Sprint 4–6 — Hypothesis / Experiment / JEV
- [ ] Multi-hypothesis portfolio + alternative explanations
- [ ] Experiment Designer (minimum discriminating experiment)
- [ ] Information gain scoring
- [ ] JEV structured decision layer (cannot override Scope/Risk/Budget)

### Sprint 7–9 — Tools + Real HTTP loop
- [ ] Tool Registry with risk/cost/side_effects contracts
- [ ] Tool retrieval (not dump 50 tools into context)
- [ ] Research loop with mock → authorized live HTTP

### Sprint 10–14 — Authz / Workflow / Verify / Root cause / PoC
- [ ] Authorization Engine (Actor-Action-Resource-Condition)
- [ ] Workflow Miner + State Machine + Invariants
- [ ] Verifier upgrades (HTTP / Graph / State / Scope)
- [ ] Root Cause Engine + Variant Hunter
- [ ] PoC Minimizer + Finding dedup + Report

### Sprint 15–17 — Memory / Eval / Skill evolution
- [ ] Episodic + Semantic memory + WriteGuard
- [ ] Research Episodes benchmark + Replay
- [ ] Skill Quality Gate + Differential evaluation + Promotion

### Later
- Browser / GraphQL / Mobile / Cloud adapters
- Knowledge Compiler (Case → Pattern → Procedure → Skill)
- Counterfactual replay
- Agent-security modules

---

## 3. Explicit non-goals for near term (from V2 §116)

- No 500 writeups as RAG
- No giant master skill
- No exposing 50 tools at once
- No K8s / Redis / Kafka / vector DB / graph DB until measured need
- No multi-model routing from day one
- No unrestricted shell/browser
- No finding without evidence
- No direct edit of production skills

---

## 4. Freeze decision

**Foundation APIs are frozen for V2 work:**
- `ScopeGuard.authorize()` signature and fail-closed semantics
- `ExecutionLedger` node lifecycle + budget spend
- `EvidenceStore` chain integrity
- `VerificationLoop.run(researcher_fn, skeptic_fn)` contract
- `content_isolation.wrap_target_content()`
- `SkillRegistry.route()` trust gate

New features must extend via new modules under `src/agent_core/` and must not weaken these boundaries. Any change to the above requires an explicit ADR and a regression test that proves no safety loss.

---

## 5. Next concrete commits

1. `docs/audit/PHASE0_AUDIT.md` (this file)
2. `src/agent_core/schemas/` — Pydantic models for Engagement, Target, Hypothesis, Experiment, Decision, Finding, Opportunity, Unknown, Belief
3. Unit tests for schema round-trip + validation
4. Keep all 35 existing tests green
5. Update ROADMAP to point at V2 sprint order

---

## 6. North Star (from V2)

```
Validated Findings × Evidence Quality × Novelty
──────────────────────────────────────────────
Requests + Tool Calls + Tokens + Time + Risk
```

Optimize for smarter research, not more requests.
