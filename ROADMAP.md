
## Research Episodes
- IMPLEMENTED (lab): quality metrics + lessons; efficiency_proxy favors evidence-linked outcomes over request volume

## Adaptive loop (§92)
- IMPLEMENTED (lab): after closed-loop, re-rank opportunities; STOP on reject; optional single variant experiment on confirm — no URL spray

## Checkpoints (§66)
- IMPLEMENTED (lab): snapshot before/after adaptive decision; write JSON; not full replay yet

## Action Regret (§60)
- IMPLEMENTED (lab): expected vs actual information gain; negative evidence scored as useful

## Surprise Engine (§43)
- IMPLEMENTED (lab): unexpected status → candidate hypotheses/unknowns; no auto-exploit

## Memory (§62–63)
- IMPLEMENTED (lab): EpisodicMemory + WriteGuard; raw target bodies blocked

## Claim-Evidence + Invariants + Artifacts
- IMPLEMENTED (lab): claim matrix blocks empty evidence; I-001 ownership check; engagement artifact writer

## Stop policy + Replay + Severity
- IMPLEMENTED (lab): unified StopPolicy; artifact/in-memory replay summary; structured severity dimensions

## Lifecycle + Dedup + Differential
- IMPLEMENTED (lab): finding lifecycle transitions; experiment fingerprint dedup; identity differential compare

## Day batch: L2 FP labs + BBCI contract + scorecard
- L2: public resource + shared ACL must not confirm as IDOR
- BBCI recon contract normalizer (no live CI)
- QualityScorecard lab aggregation

## BBCI live.txt ingest (oneplus sample)
- parse_bbci_live_txt + fixture examples/fixtures/bbci/oneplus.ch.live.txt
- No live HTTP to targets; read-only sample from public results path
