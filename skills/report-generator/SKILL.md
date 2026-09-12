# Skill: report-generator

## Purpose
Turn a CONFIRMED finding into a submission-ready report. This is the last
step of the pipeline (MASTER SPEC §6, "Bounty Operations") and the one a
human triager actually reads — so it is held to the strictest
evidence-traceability standard in the whole system.

## Procedure
1. Load the Finding and its full evidence_ids list from the EvidenceStore.
   Refuse to proceed if the finding's status is not CONFIRMED.
2. Build the report in this structure:
   - **Summary** (1-2 sentences, no hedging, no invented severity language
     beyond what the evidence supports)
   - **Reproduction steps** — each numbered step must cite the evidence_id
     it came from. If a step cannot be traced to evidence, delete the step
     rather than paraphrase around the gap.
   - **Impact** — derived from the invariant that was violated (see
     authz-idor-analysis SKILL.md), not from generic severity language.
   - **Evidence appendix** — raw request/response pairs, screenshots,
     timestamps, exactly as recorded (no "cleaning up" the evidence to make
     it read better — programs need the actual proof).
3. Run a duplicate check: search prior findings in this engagement's
   EvidenceStore for overlapping target + endpoint + invariant before
   marking the report ready. (Cross-program duplicate checking against a
   platform's public disclosure history is a Phase 3+ retrieval feature —
   see docs/ROADMAP.md.)
4. Attach the evidence chain's hash-chain verification result
   (`EvidenceStore.verify_chain()`) as an appendix line — this lets a
   program verify the evidence wasn't edited after discovery.

## Non-negotiable rule
This skill never adds a claim, a payload, or a reproduction detail that is
not directly supported by a cited Evidence object. If the write-up would
read better with an assumption filled in, that is a signal to go back and
gather the missing evidence — not to write the assumption down.
