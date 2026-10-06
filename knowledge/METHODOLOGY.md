# Knowledge methodology (canonical — matches Notion + code)

## Pipeline
```text
EXTERNAL / NOTION SOURCE
        ↓
Source quality scoring (source_quality.py)
  UNVERIFIED → REVIEWED → ACCEPTED | REJECTED | DUPLICATE
        ↓
Case extraction (case_extract / expansion)
        ↓
Novelty / dedup (dedup.py)
        ↓
Pattern cluster → Procedure → Strategy (compiler GENERATE)
        ↓
Knowledge Candidate (untrusted)
        ↓
Benchmark + human review
        ↓
CuratedKnowledgeImporter (only PROMOTED)
        ↓
knowledge/{cases,patterns,procedures,strategies,negative}/
        ↓
KnowledgeIndex → Retrieval → Research decisions
```

## Where data comes from
| Origin | How it enters | Trust |
|--------|----------------|-------|
| Notion writeup library / Top Writeups | Human extracts structure → CASE markdown | Trusted only after extraction into `knowledge/` |
| PortSwigger / OWASP / CWE | Methodology → PATTERN/PROC | Tier B — concepts |
| Public writeups (HackerOne, blogs) | Copy text offline → ExpansionPipeline | Candidate until promoted |
| BugBountyCI | Recon only — **not** knowledge | Never auto-knowledge |
| Agent research episode | StructuredCase untrusted | Candidate ledger |
| Tips | `knowledge/tips/` | Untrusted hints only |

**Never:** bulk scrape the open web into trusted knowledge.

## How sources are classified
`SourceType`: writeup | advisory | academy | standard | notion | research_paper | agent_episode

`SourceStatus`: UNVERIFIED → REVIEWED → ACCEPTED | REJECTED | DUPLICATE

Quality signals (0..1): technical depth, reproducibility, concrete evidence, preconditions, root cause, impact, novelty, reliability, relevance, duplication risk → `priority_score`.

## How filtering works
1. Empty / trivial text → reject  
2. Low priority_score → defer  
3. Duplicate vs existing patterns → DUPLICATE / merge  
4. Payload-only lists without object model → reject for curated  
5. Universal claims (“always vulnerable”) → cannot import  
6. Tips never become execution permission  
7. Generated artifacts stay in candidate store until PROMOTED + benchmark

## Promotion rules
- Candidate ≠ curated  
- Benchmark snapshot required for positive/negative kinds  
- False-positive benchmark → block import  
- Human/review gate for trusted subdirs (`cases/`, `patterns/`, …)  
- `knowledge/imported/` is quarantine for automated writes

## Extraction priority (quality > volume)
1. Object-level authorization / BOLA / IDOR with clear key + proof  
2. Auth/ATO chains from authorization failure  
3. Business logic / state / race on benefits  
4. SSRF with scope-safe discriminating checks  
5. XSS with context + encoding falsification  
6. Skip pure payload dumps and duplicate ideas
