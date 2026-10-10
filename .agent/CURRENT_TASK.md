# Current Task

**Campaign:** IN_PROGRESS  
**Focus:** Knowledge surface-aligned retrieval (GraphQL lab ranking)

## Completed this cycle
- Fixed `tags_prefer` merge that reversed procedure rank via repeated `insert(0)`
- Lab observation paths (e.g. `/graphql`) inject ranking-only `extra_tech_signals`
- Authz query builder path/tech surface signals for GraphQL/WebSocket
- Surface-tech tag boost when signals include graphql/websocket
- Regression: GraphQL-tagged procedures rank above generic function-level admin
- Baseline research-utility: none→FN / curated→TP on hard scenarios; irrelevant→no FP
- Full suite: **449 passed / 0 failed / 8 skipped**

## Still blocked (external/human)
- Gate 6B live authorized target
- Live browser network research
- Public mobile HTTPS deploy

## Next resume
- Live authorization when available
- Optional: measure whether progressive-disclosure skills (not just knowledge/) change ResearchLoop decisions
