# Contributing

## Before you open a PR

1. Read `docs/ARCHITECTURE.md` — it explains *why* the code is shaped the
   way it is, not just what it does. Several design choices here look
   over-engineered until you know the failure mode they prevent.
2. Read `SECURITY.md` — this project has an explicit ethical-use posture
   baked into the code (`ScopeGuard` fails closed), and PRs that weaken it
   will be closed regardless of how convenient they are.
3. Check `docs/ROADMAP.md` before adding a new subsystem — there's a
   reasoned order to Phase 3-8, and jumping ahead (e.g. wiring in a vector
   DB before Phase 3's retrieval task actually needs one) adds maintenance
   surface without evidence it helps.

## Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python examples/run_demo.py
```

## Adding a new Skill

Every skill needs, at minimum:

```
skills/<your-skill-name>/
    metadata.yaml   # Level 1 — see any existing skill for the schema
    SKILL.md        # Level 2 — invariant-first, evidence-explicit
```

Requirements for `SKILL.md`:
- State the **invariant** being tested, not just a payload list.
- Every step that produces a claim must say what Evidence object backs it.
- The skill must NOT self-approve its own findings — that is the
  `VerificationLoop`'s job (`src/agent_core/verification/loop.py`). If your
  skill's SKILL.md includes language like "mark this CONFIRMED", that's a
  sign it's trying to skip the Skeptic step — remove it.
- No live exploit payloads for real-world unpatched vulnerabilities. This
  repo describes methodology (what to test and why), not a payload
  library.

Add a matching test in `tests/test_skill_registry.py` if your skill
introduces a new routing case (new technology tag, new vulnerability
class, new dependency edge).

## Code style

- Every module-level docstring should explain *why* the module exists and
  what real-world failure it addresses — see any existing file in
  `src/agent_core/` for the expected tone. Terse "does X" docstrings are
  not enough for a project whose whole point is decisions with
  consequences.
- No bare `except:` — evidence and scope-decision paths must fail loudly.
- New control-plane code (anything under `src/agent_core/`) needs tests.
  Skills (under `/skills/`) are documentation-first and don't need unit
  tests unless they include an executable `scripts/` entry.

## Reporting a security issue in this project itself

See `SECURITY.md` — use a private advisory, not a public issue.
