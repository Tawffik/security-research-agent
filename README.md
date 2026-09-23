# security-research-agent

[![CI](https://github.com/Tawffik/security-research-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Tawffik/security-research-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-93%20passing-brightgreen.svg)](tests/)

> Replace `OWNER` in the badge URL above with your GitHub username/org once
> this is pushed — see the "Publish this to GitHub" section below.

An evidence-driven, skill-driven control plane for an AI-assisted security
research agent — built for **authorized bug-bounty programs, owned
systems, CTFs, and controlled labs only.**

This is not a scanner and not a prompt collection. It is the boring,
load-bearing infrastructure that a real research agent needs *before* it
is allowed to touch a target: authorization enforcement, durable resumable
state, hash-chained evidence, adversarial self-verification, and a
skill system with progressive disclosure. The offensive reasoning itself
lives in Skills (`/skills`), which this library loads, sequences, and
holds accountable for evidence — it never trusts a skill's output blindly.

## Why this shape

This repo implements Phase 1–2 of a larger architecture (see
`docs/ARCHITECTURE.md` and `docs/ROADMAP.md`) informed by:

- the real-world "Bug Bounty Singularity" hackbot (Rez0 + xssdoctor,
  126 confirmed findings / 5 months) — its single biggest quality lever
  was a **dedicated adversarial validator rewarded for killing findings,
  not confirming them**, which cut false positives from ~80% to ~60%.
  See `agent_core/verification/loop.py`.
- Trail of Bits' `skills` repo pattern of progressive-disclosure security
  skills (metadata → SKILL.md → references → scripts). See
  `agent_core/skills/registry.py`.
- LongHorizon-Harness's "audited state transitions" idea (arXiv:2608.01964) —
  a resumed agent should see compact, *verified* state, not a raw replay
  of everything it ever tried. See `agent_core/ledger/state_tree.py`.
- Documented incidents where agents followed instructions hidden in
  target-controlled content (CVE-2025-59536, CVE-2025-6514, the Truffle
  Security "be thorough" SQLi study) — which is why Content Isolation is a
  first-class module here, not an afterthought. See
  `agent_core/content_isolation/sanitizer.py`.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# See every Phase 1-2 component wired together end-to-end:
python examples/run_demo.py

# Run the test suite:
pytest
```

## Layout

```
src/agent_core/
    scope/               ScopeGuard — hard authorization boundary (§1)
    content_isolation/    Treats ALL target-origin data as untrusted
    ledger/               Execution Ledger — resumable state tree + budget breaker (§3)
    evidence/             Hash-chained Evidence Store + Findings (§9)
    skills/               Skill Registry — progressive disclosure + routing (§4-5)
    verification/         Researcher -> Skeptic -> Referee loop (§10)

skills/                    Example skills (metadata.yaml + SKILL.md), no live payloads:
    recon-js-surface/      passive client-side attack-surface mapping
    authz-idor-analysis/   authorization-boundary hypothesis generation
    report-generator/      evidence-traceable bounty report generation

examples/
    demo_program_scope.yaml   example authorized-scope declaration
    run_demo.py               end-to-end demo of every Phase 1-2 component

tests/                     pytest suite (run `pytest tests/` for current count)
docs/
    ARCHITECTURE.md        full architecture map + design rationale
    ROADMAP.md             Phase 3-8 plan (retrieval, graphs, hypothesis engine, evaluation)
```

## Non-negotiables (read before extending this)

1. **Every outbound action goes through `ScopeGuard.authorize()`.** No
   exceptions, no "just this once for testing." If a code path can reach
   the network without going through the guard, that's a bug, not a
   feature.
2. **Every claim traces to an Evidence object.** `EvidenceStore` refuses
   nothing — it will happily store a bad claim — but `VerificationLoop`
   refuses to promote a finding to `CONFIRMED` unless a Skeptic actually
   attempted disproof and failed. Don't collapse Researcher and Skeptic
   into one pass to save a model call; that's the exact mistake this
   architecture exists to prevent.
3. **Target-origin content is never instructions.** Anything that comes
   back from the target — HTTP bodies, JS source, error messages, even a
   bounty program's own scope page — goes through
   `content_isolation.wrap_target_content()` before a model sees it.
4. **A skill with `trust_score < 0.6` and `provenance != "internal"`
   cannot be routed above `RiskTier.PASSIVE`** until a human reviews it.
   See `SkillRegistry.route()`.
5. **Rejected hypotheses and negative evidence are kept, never deleted.**
   That's what makes resumption after a crash cheap instead of a replay.

## What this repo deliberately does NOT include yet

No retrieval layer, no knowledge graph, no browser automation, no live
HTTP tooling, and no vulnerability-class-specific exploitation logic. See
`docs/ROADMAP.md` for the phased plan — building those on top of a shaky
foundation (no scope enforcement, no evidence discipline) is how you get
an expensive, unreliable scanner instead of a research agent.

## Publish this to GitHub

```bash
# 1. Create an empty repo on GitHub first (no README/license — this repo
#    already has them), then:
git remote add origin git@github.com:<your-username>/security-research-agent.git
git branch -M main
git push -u origin main

# 2. Update the CI badge URL at the top of this README with your username.
# 3. In the repo's Settings -> General, consider enabling "Require status
#    checks to pass before merging" for the `test` and `lint` jobs once
#    CI has run at least once.
```

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues in this project
itself go through [SECURITY.md](SECURITY.md), not a public issue.
