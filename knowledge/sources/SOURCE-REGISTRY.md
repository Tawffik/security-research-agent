# Source Registry (Knowledge Engine — Tiered)

Per Notion V3 source hierarchy. Discovery sources ≠ trusted knowledge until extracted and validated.

| ID | Tier | Source | Role | Status |
|----|------|--------|------|--------|
| SRC-0001 | B — Methodology | PortSwigger Web Security Academy — IDOR | Concepts + example scenarios | ingested |
| SRC-0002 | B — Standards | OWASP API Security Top 10 2023 — API1 BOLA | Classification + scenarios | ingested |
| SRC-0003 | B — Standards | CWE-639 Authorization Bypass Through User-Controlled Key | Root-cause vocabulary | referenced |
| SRC-0004 | A — deferred | Live HackerOne/Intigriti disclosed reports | Primary cases | **not bulk-scraped** (quality filter first) |
| SRC-0005 | C — deferred | SecurityCipher / Bug Bytes indexes | Discovery leads only | not trusted knowledge yet |

**Rule:** We do not auto-promote writeups to Skills. Pipeline: Source → Case → Pattern → Procedure → (later) Skill candidate + benchmark.
