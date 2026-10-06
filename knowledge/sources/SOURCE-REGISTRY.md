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

| SRC-0006 | A — Primary | Profile IDOR→ATO writeup (Notion Top Writeups) | Case extraction | CASE-0006 |
| SRC-0007 | Human index | Notion Top Writeups + Writeups Library | Discovery map | NOTION-INVENTORY |

| SRC-0008 | A/B Research | APIsec 100+ BOLA in the wild analysis | Pattern/strategy | PAT-0003, PROC-0003, STRAT-0002 |
| SRC-0009 | A Platform | HackerOne GraphQL auth bypass post | Case | CASE-0007, PAT-0004 |

| SRC-FX-0001 | A — Fixture writeup | Offline BOLA writeup sample | Case extraction | ACCEPTED offline |
| SRC-FX-0002 | A — Fixture writeup | Offline SSRF writeup sample | Case extraction | ACCEPTED offline |

| SRC-0010 | B — Standards | OWASP Mass Assignment / excessive binding concepts | Pattern | PAT-0014, CASE-0014, PROC-0014 |
| SRC-0011 | B — Methodology | Business-logic race / check-then-act on benefits | Pattern | CASE-0015, PAT-0015 |
| SRC-NEG-0003 | Negative knowledge | Status-only ≠ BOLA | Filter | NEG-0003 |
| SRC-NEG-0004 | Negative knowledge | Introspection ≠ authz bypass | Filter | NEG-0004 |

| SRC-0012 | B — Academy | PortSwigger SSRF | CASE-0010 deepened |
| SRC-0013 | B — Class | Cloud metadata SSRF class | CASE-0010 |
| SRC-0014 | B — Academy | PortSwigger XSS context | CASE-0013 deepened |
| SRC-0015 | B — Academy | JWT verification attacks class | CASE-0016 |
| SRC-0016 | B — Academy | CSRF | CASE-0017 |
| SRC-0017 | B — Academy | SQLi (differential, no payload catalog) | CASE-0018 |
| SRC-0018 | B — Academy | Directory traversal | CASE-0019 |
| SRC-0019 | B — Academy | Open redirect / OAuth return URL | CASE-0020 |

| SRC-0020 | B — Research class | Web cache deception | CASE-0021 |
| SRC-0021 | B — Methodology | Insecure deserialization | CASE-0022 |
| SRC-0022 | B — GraphQL | Batch/alias authz | CASE-0023 |
| SRC-0023 | B — OAuth | redirect_uri validation | CASE-0024 |
| SRC-0024 | B — Host header | Password reset poisoning | CASE-0025 |
| SRC-0025 | B — XXE | External entities | CASE-0026 |
| SRC-0026 | B — SSTI | Template evaluation | CASE-0027 |
| SRC-0027 | B — Upload | Type/path controls | CASE-0028 |
