# Notion knowledge inventory (for agent ingestion)

Human-side sources already curated in the workspace. Agent should **extract structure**, not dump pages.

## High-value pages
| Notion page | Role for agent |
|-------------|----------------|
| 🛡️ Security Research Agent V3/V4 MASTER SPEC | Canonical architecture + realism ladder |
| 🧠 Security Research Agent V2 Knowledge Engine | Older knowledge graph notes |
| 🔥 Top Writeups | Curated Tier-A/B links (IDOR/BOLA first) |
| 📚 Bug Bounty Writeups Library | Database of real writeups (many cards) |
| IDOR Checklist — Object & Function Authorization | Methodology signals for PROC |
| Real Bounty — Profile IDOR to ATO | → CASE-0006 |
| Real Bounty — $949 Ticket IDOR PII | Candidate CASE (link on card) |
| Hacking Subaru — IDOR + Auth Bypass | Candidate CASE (vehicle control / object key) |
| BugBounty Lab — Practical Web Security Project | Lab design ideas (L1–L2) |

## Extraction priority (quality, not volume)
1. Access control / IDOR / BOLA writeups with clear object key + proof  
2. Auth/ATO chains that start from object authorization failure  
3. Business logic / state machine (later phase)  
4. Skip pure payload lists and duplicate ideas

## Rule
Notion = human interface. Git `knowledge/` = versioned machine knowledge after extraction.
