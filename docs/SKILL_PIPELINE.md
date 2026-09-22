# How Skills Enter This Project

Skills are **procedures**, not the brain.

The brain is: research state + beliefs + unknowns + hypotheses + experiments + evidence + decision policy.

## What we do NOT do

- Do not create hundreds of skills from writeups.
- Do not paste Notion/RAG text and call it a skill.
- Do not auto-promote because an LLM suggested it.
- Do not execute a skill only because retrieval ranked it.

## Lifecycle (required)

```
DRAFT → CANDIDATE → BENCHMARKED → REVIEW → APPROVED
                ↘ FAILED / REJECTED
APPROVED → REGRESSION → DEPRECATED
```

Promotion requires:

1. Provenance (where it came from)
2. Capability declaration (network/shell/secrets bounds)
3. Benchmark episode
4. Baseline (no-skill) comparison
5. Differential evaluation (findings, FP, cost, requests)
6. No unacceptable regression
7. Human review

## Knowledge path (before a skill exists)

```
Source (writeup / lab episode / note)
  → CASE (what happened)
  → PATTERN (generalization across cases)
  → PROCEDURE (repeatable test steps)
  → STRATEGY (when/why to use procedures)
  → SKILL CANDIDATE (executable interface + constraints)
  → Benchmark
  → Promote or reject
```

Directories (machine knowledge, versioned in git):

```
knowledge/
  cases/         # specific incidents
  patterns/      # generalized security patterns
  procedures/    # how to test
skills/
  candidates/    # not yet approved
  <approved>/    # existing: authz-idor-analysis, recon-js-surface, report-generator
```

## First domain

Authorization / IDOR / business logic only.

Start with a **small** number of strong sources (about 10–20), not 500 writeups.

## Current approved skills (keep small)

| Skill | Role |
|-------|------|
| recon-js-surface | Passive surface fragment (not findings) |
| authz-idor-analysis | Authorization hypotheses from graph/identities |
| report-generator | Report packaging |

New skills land in `skills/candidates/` until the lifecycle above is satisfied.
