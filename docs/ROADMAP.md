# Roadmap

## Status: Phase A started (Orchestrator)

**HttpTransport (opt-in):** `src/agent_core/orchestrator/transport.py`
- MockTransport = default (tests/demo, no network)
- HttpTransport = stdlib urllib, timeout + body cap, no auto-redirect, TLS on
- Live traffic only via `EngagementConfig.use_live_http` / `--live-http`
- Every fetch still goes through `ScopeGuard.authorize()` + budget in the orchestrator


Implemented in-tree:
- `src/agent_core/orchestrator/engagement.py` — EngagementOrchestrator
- `examples/run_engagement.py` — CLI (mock transport, no network)
- `tests/test_orchestrator.py`

Phase 1-2 remain the foundation. Phase A is a thin loop on top of them,
not a rewrite. Real HTTP/browser tooling stays out until a real authorized
scope file has been exercised for a full engagement.

---

Phase 1-2 (this repo, as of now) are functional and tested. Everything
below is intentionally NOT built yet — build on the tested foundation
before adding surface area.

## Phase 3 — Retrieval
- Replace `SkillRegistry.route()`'s naive metadata matching with the
  adaptive hybrid retrieval described in MASTER SPEC §7: classify the
  query, route to lexical/dense/graph/episodic sources, fuse + rerank.
- Start with just two sources (BM25 over SKILL.md bodies + a simple
  embedding index) before adding graph retrieval — measure Recall@K
  before adding a third source, per §21's experimental discipline.
- Contradiction detection: if two retrieved sources disagree about the
  same target fact, surface the conflict rather than silently picking one.

## Phase 4 — Three Graph Model
- Target Graph: promote the informal `technologies: list[str]` used in
  today's `route()` call into real graph nodes/edges (Asset -> Endpoint ->
  Parameter -> Identity -> Role), stored the same way the Ledger stores
  its state tree (SQLite adjacency table is enough to start; don't reach
  for a graph database until the query patterns actually need one).
- Knowledge Graph: CVE/CWE/technology relationships. Start by ingesting
  Trail of Bits' `skills` repo structure and a CWE taxonomy dump — don't
  build a general-purpose knowledge graph before you have two concrete
  reasoning tasks that need graph traversal.
- Execution Graph: this already partially exists as the Ledger's
  hypothesis nodes; formalize the Task -> Hypothesis -> Attempt ->
  Observation -> Evidence -> Decision -> Finding chain explicitly.

## Phase 5 — Hypothesis Engine
- Multi-hypothesis branches (§11): extend `LedgerNode` with a
  `hypothesis_id` namespace so independent branches can run without
  interfering, then merge only after evidence.
- Wire `VerificationLoop` to run per-branch instead of once per call site.

## Phase 6 — Security Skill Families + Tool RAG + Patch-Diff/Variant Analysis
- Flesh out the skill library beyond the three examples here: recon,
  JS analysis, web, API, identity, authorization, business logic,
  injection, source-code security, vulnerability research, validation,
  bounty operations (§6). Model each new skill's SKILL.md on
  `authz-idor-analysis` — invariant-first, evidence-explicit, no
  self-approval.
- Tool RAG (§13): a `ToolRegistry` parallel to `SkillRegistry`, so tool
  selection is retrieval, not "expose 40 tools and hope."
- Patch-Diff + Variant Analysis (§16): once a finding is CONFIRMED, spin
  up a follow-on hypothesis generation pass that searches for sibling
  components / related versions. Trail of Bits' `variant-analysis` plugin
  (characterize root cause -> detection patterns -> CodeQL/ripgrep sweep
  -> validate -> document) is a good reference implementation to study —
  evaluate it, don't copy it blindly (§17's stated principle).

## Phase 7 — Advanced Memory
- Episodic memory (what happened in past engagements) separate from
  semantic memory (durable lessons) separate from the Ledger (what's
  happening now). Selective retrieval only — the question to ask before
  injecting any memory is "will this change the current decision?"
- Stale-memory and contradiction detection.

## Phase 8 — Continuous Evaluation + Skill Evolution
- Stand up a permanent benchmark. Don't build a bespoke one from scratch
  first — evaluate against published, real-world benchmarks so your
  numbers are comparable to the field:
    - CyberGym / CyberGym-E2E (UC Berkeley) — PoC + patch generation,
      1,500+ real vulnerabilities. Even top systems land around ~20%
      success — a useful, humbling baseline.
    - ExploitGym — exploitation specifically, across userspace/browser/kernel.
    - BountyBench, Cybench, NYU CTF Bench — smaller, faster iteration loops.
- Skill evolution (§19): never mutate a production skill in place.
  `v1 -> candidate v2 -> regression suite -> promote/rollback`. Store this
  as its own ledger-like table (skill_versions) so a bad skill update is
  as recoverable as a bad ledger state.

## Things to deliberately NOT do early
- Don't add a vector database before Phase 3 has a concrete retrieval task
  that the naive metadata router in `SkillRegistry.route()` demonstrably
  fails at. Measure the failure first.
- Don't wire in real HTTP/browser tooling before Phase 1's ScopeGuard has
  been exercised against a real authorized program's scope file for at
  least one full engagement — the schema in `demo_program_scope.yaml`
  WILL need fields you haven't thought of yet (out-of-hours windows,
  per-endpoint rate limits, credential rotation windows), and it's much
  cheaper to discover that before real traffic depends on it.
- Don't build the multi-model routing from `docs` references (e.g. the
  Huntress-style Coordinator-Solver pattern) until cost data from a real
  engagement tells you which skill classes actually benefit from a
  cheaper model — routing complexity has its own maintenance cost.
