#!/usr/bin/env python3
"""Run the offline research loop against the sample recon fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_core.orchestrator.research_loop import ResearchLoop

FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"


def main() -> int:
    loop = ResearchLoop(engagement_id="eng_demo_offline")
    result = loop.run_from_recon_file(FIXTURE)
    print(result.summary)
    print("---")
    print("Top opportunities:")
    for o in result.opportunities[:5]:
        print(f"  {o.opportunity_id} [{o.priority.value}] {o.type}: {o.target}")
    print("Hypotheses:")
    for h in result.hypotheses:
        print(f"  {h.hypothesis_id} ({h.confidence:.2f}) {h.statement[:70]}")
    print("Decision:")
    print(
        f"  {result.decision.decision.value} candidate={result.decision.candidate} "
        f"reasons={result.decision.reason_codes}"
    )
    out = ROOT / "examples" / "fixtures" / "last_research_result.json"
    payload = {
        "summary": result.summary,
        "decision": result.decision.model_dump(),
        "hypothesis_ids": [h.hypothesis_id for h in result.hypotheses],
        "experiment_ids": [e.experiment_id for e in result.experiments],
        "opportunity_count": len(result.opportunities),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
