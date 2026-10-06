# Knowledge (not skills yet)

Structured research knowledge for Security Research Agent.

## Pipeline (Notion V3 / V2 master)
```text
SOURCE (tiered) → CASE → PATTERN → PROCEDURE → STRATEGY
                 → (later) SKILL CANDIDATE → BENCHMARK → REVIEW → APPROVE
```

## Current inventory
| ID | Kind | Origin |
|----|------|--------|
| SRC-REGISTRY | sources | PortSwigger, OWASP API1, … |
| CASE-0001 | case | Lab IDOR episode |
| CASE-0002..0005 | case | PortSwigger + OWASP scenarios (Tier B) |
| CASE-0006 | case | Profile IDOR→ATO (Tier A writeup + Notion) |
| NOTION-INVENTORY | sources | Map of workspace writeup library |
| PAT-0001, PAT-0002 | pattern | Cross-identity + BOLA object key |
| PROC-0001, PROC-0002 | procedure | Discriminating experiments |
| STRAT-0001 | strategy | Prioritize object-keyed APIs |
| PAT-0003, PROC-0003, STRAT-0002 | pattern/proc/strat | BOLA mutation matrix (APIsec field data) |
| CASE-0007, PAT-0004 | case/pattern | GraphQL operation authorization |

## Quality rules
- No bulk scrape of the internet  
- Writeup ≠ Skill  
- Recon hosts alone ≠ authorization evidence  
- Tier C discovery feeds leads only  

## Methodology
See `METHODOLOGY.md` for source → filter → classify → promote (code-backed).

## Recent curated additions
| ID | Kind | Domain |
|----|------|--------|
| CASE-0014 / PAT-0014 / PROC-0014 | mass assignment privilege fields | authorization |
| CASE-0015 / PAT-0015 | benefit race check-then-act | business_logic |
| NEG-0003 / NEG-0004 | status-only / introspection false leads | negative |
| STRAT-0014 | allowlist writable fields | authorization |

## Not done yet
- Bulk primary bounty report ingest (quality filter first)
- Full Notion writeup library extraction (human-paced)
- Auto skill promotion without benchmark + review

## Quality expansion (2026-10)
Deepened SSRF/XSS; added authentication (JWT, CSRF, redirect), injection (SQLi differential), traversal — each with CASE+PAT+PROC and negatives where FP is common. **No payload catalogs.**

## Multi-class coverage (research-aligned)
Authorization (object/action/vertical/GraphQL/function), authentication (JWT/CSRF/OAuth/CORS/reset),
ssrf, xss, injection (SQL/XXE/SSTI/second-order), business_logic, cache, traversal, upload,
deserialization, smuggling, ui_security, websocket authz.

Same QUALITY_BAR for every class — see STRAT-0100.
