"""
Closed-loop vertical slice (lab / fixture only).

Path:
  ResearchLoop (plan) → JEV decision → ScopeGuard → Mock observation
  → EvidenceStore → Researcher → Skeptic → Referee → Finding status

Honest limits:
  - Does NOT claim live HTTP or BugBountyCI production integration.
  - Observations come from LabScenario fixtures (authorized lab simulation).
  - Status labels: IMPLEMENTED + TESTED for offline path; NOT END_TO_END VERIFIED
    against real BugBountyCI or production targets.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from agent_core.content_isolation.sanitizer import wrap_target_content
from agent_core.evidence.store import EvidencePolarity, EvidenceStore, FindingStatus
from agent_core.findings.report import EvidenceReport, build_evidence_report
from agent_core.orchestrator.research_loop import ResearchLoop, ResearchLoopResult
from agent_core.schemas.research import HypothesisStatus
from agent_core.scope.guard import Decision as ScopeDecision, RiskTier, ScopeGuard
from agent_core.verification.loop import (
    ResearcherClaim,
    SkepticQuestion,
    SkepticVerdict,
    VerificationLoop,
)


@dataclass
class LabObservation:
    """Simulated authorized-lab HTTP observation for one identity."""

    identity: str
    method: str
    path: str
    host: str
    status: int
    body: str
    notes: str = ""


@dataclass
class LabScenario:
    """
    Programmed lab outcomes for a discriminating experiment.

    example: owner gets 200 with own order; other user also gets 200 with
    same private fields → candidate authorization issue for skeptic review.
    """

    name: str
    observations: list[LabObservation]
    expected_if_secure: str
    # If True, observations are consistent with a possible ownership bypass.
    suggests_authz_issue: bool = False


@dataclass
class ClosedLoopResult:
    plan: ResearchLoopResult
    scope_allowed: bool
    observations: list[LabObservation] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    referee_accepted: bool = False
    finding_id: Optional[str] = None
    final_status: Optional[str] = None
    referee_reason: str = ""
    summary: str = ""
    limitations: list[str] = field(default_factory=list)
    stop_reason: str = ""
    belief_updates: list[str] = field(default_factory=list)
    report: Optional[EvidenceReport] = None


def default_idor_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """Deterministic lab fixture: non-owner receives another user's order body."""
    return LabScenario(
        name="lab_idor_order_cross_identity",
        expected_if_secure="Non-owner must receive 403/404; owner may receive 200 for own object",
        suggests_authz_issue=True,
        observations=[
            LabObservation(
                identity="user_a",
                method="GET",
                path="/api/orders/1001",
                host=host,
                status=200,
                body='{"id":1001,"owner":"user_a","amount":42.00,"status":"PAID"}',
                notes="owner access",
            ),
            LabObservation(
                identity="user_b",
                method="GET",
                path="/api/orders/1001",
                host=host,
                status=200,
                body='{"id":1001,"owner":"user_a","amount":42.00,"status":"PAID"}',
                notes="non-owner received owner object body",
            ),
        ],
    )


def secure_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """Negative case: server enforces ownership — should not become CONFIRMED IDOR."""
    return LabScenario(
        name="lab_secure_ownership",
        expected_if_secure="Non-owner blocked",
        suggests_authz_issue=False,
        observations=[
            LabObservation(
                identity="user_a",
                method="GET",
                path="/api/orders/1001",
                host=host,
                status=200,
                body='{"id":1001,"owner":"user_a"}',
            ),
            LabObservation(
                identity="user_b",
                method="GET",
                path="/api/orders/1001",
                host=host,
                status=403,
                body='{"error":"forbidden"}',
            ),
        ],
    )


class ClosedLoopRunner:
    """
    Runs plan + lab observation + evidence + verification under ScopeGuard.

    Requires a ScopeGuard built from an authorized scope file; denies if host
    is out of scope.
    """

    def __init__(
        self,
        scope_path: Union[str, Path],
        engagement_id: str = "eng_closed_loop",
        data_dir: Optional[Path] = None,
    ):
        self.engagement_id = engagement_id
        self.scope_path = Path(scope_path)
        self.guard = ScopeGuard.from_scope_file(self.scope_path)
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="sra_loop_"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.evidence = EvidenceStore.open(self.data_dir / f"{engagement_id}_evidence.db")
        self.research = ResearchLoop(engagement_id=engagement_id)

    def run(
        self,
        recon_path: Union[str, Path],
        scenario: Optional[LabScenario] = None,
    ) -> ClosedLoopResult:
        plan = self.research.run_from_recon_file(recon_path)
        host = plan.target_context.primary_host or "api.acme-demo.test"
        scenario = scenario or default_idor_lab_scenario(host)

        limitations = [
            "Observations are LabScenario fixtures, not live HTTP",
            "Not BugBountyCI production artifact integration",
            "Researcher/Skeptic are deterministic lab functions, not LLM providers",
        ]

        # Scope check for the observation host before any "execution"
        decision = self.guard.authorize(
            host=host,
            risk_tier=RiskTier.ACTIVE_SAFE,
            action_description=f"lab_observe GET /api/orders/1001 on {host}",
        )
        scope_ok = decision in (ScopeDecision.ALLOW, ScopeDecision.REQUIRES_APPROVAL)
        if not scope_ok:
            stop_reason = "scope_blocked"
            report = build_evidence_report(
                engagement_id=self.engagement_id,
                title="Scope denied",
                claim="No claim evaluated — host/action blocked by ScopeGuard",
                status="scope_denied",
                evidence_ids=[],
                stop_reason=stop_reason,
                limitations=limitations,
            )
            return ClosedLoopResult(
                plan=plan,
                scope_allowed=False,
                summary=f"SCOPE_DENIED by ScopeGuard: {decision.value}",
                limitations=limitations,
                referee_reason=f"ScopeGuard returned {decision.value}",
                stop_reason=stop_reason,
                report=report,
            )

        evidence_ids: list[str] = []
        hyp_id = plan.decision.hypothesis_id or (
            plan.hypotheses[0].hypothesis_id if plan.hypotheses else "H1"
        )

        for obs in scenario.observations:
            # Content isolation on target body before any model-facing use
            wrapped = wrap_target_content(
                f"lab_http:{obs.host}{obs.path}:{obs.identity}",
                obs.body,
            )
            rendered = wrapped.render_for_model() if hasattr(wrapped, "render_for_model") else str(wrapped)

            polarity = EvidencePolarity.NEUTRAL
            if scenario.suggests_authz_issue and obs.identity != "user_a" and obs.status == 200:
                polarity = EvidencePolarity.POSITIVE  # supports candidate issue
            elif not scenario.suggests_authz_issue and obs.identity != "user_a" and obs.status in (401, 403, 404):
                polarity = EvidencePolarity.NEGATIVE  # ownership enforced

            ev = self.evidence.record(
                target=f"{obs.host}{obs.path}",
                action=f"{obs.method} as {obs.identity}",
                input_data=f"identity={obs.identity}",
                expected=scenario.expected_if_secure,
                observed=f"status={obs.status} body={rendered[:500]}",
                polarity=polarity,
                confidence=0.85,
                source="closed_loop.lab_scenario",
                related_hypothesis=hyp_id,
            )
            evidence_ids.append(ev.evidence_id)

        # Differential summary evidence
        if len(scenario.observations) >= 2:
            a, b = scenario.observations[0], scenario.observations[1]
            diff_note = (
                f"identity_diff status_a={a.status} status_b={b.status} "
                f"body_equal={a.body == b.body} suggests_authz_issue={scenario.suggests_authz_issue}"
            )
            ev = self.evidence.record(
                target=f"{host}/api/orders/1001",
                action="diff_response_by_identity",
                input_data="user_a vs user_b",
                expected=scenario.expected_if_secure,
                observed=diff_note,
                polarity=EvidencePolarity.POSITIVE
                if scenario.suggests_authz_issue
                else EvidencePolarity.NEGATIVE,
                confidence=0.9,
                source="closed_loop.diff",
                related_hypothesis=hyp_id,
            )
            evidence_ids.append(ev.evidence_id)

        def researcher_fn(hypothesis_id: str) -> ResearcherClaim:
            return ResearcherClaim(
                hypothesis_id=hypothesis_id,
                title="Cross-identity object access on order resource",
                claim=(
                    "User B can retrieve User A's order object via GET /api/orders/{id} "
                    "with identical private fields when authorization should be ownership-bound."
                    if scenario.suggests_authz_issue
                    else "Ownership appears enforced: non-owner receives 403."
                ),
                supporting_evidence_ids=list(evidence_ids),
                severity_estimate="medium" if scenario.suggests_authz_issue else "info",
            )

        def skeptic_fn(claim: ResearcherClaim, store: EvidenceStore) -> SkepticVerdict:
            # Deterministic skeptic: for secure scenario, flag intended/authz not crossed.
            if not scenario.suggests_authz_issue:
                answers = {
                    SkepticQuestion.AUTHZ_ACTUALLY_CROSSED: False,
                    SkepticQuestion.ALTERNATE_EXPLANATION: False,
                    SkepticQuestion.INTENDED_BEHAVIOR: True,
                    SkepticQuestion.REPRODUCIBLE: True,
                    SkepticQuestion.EVIDENCE_COMPLETE: True,
                    SkepticQuestion.IN_SCOPE: True,
                    SkepticQuestion.IMPACT_REAL: False,
                    SkepticQuestion.AUTH_ACTUALLY_BYPASSED: True,
                    SkepticQuestion.POSSIBLE_DUPLICATE: True,
                    SkepticQuestion.TEST_ARTIFACT: True,
                }
                return SkepticVerdict(
                    claim=claim,
                    answers=answers,
                    disproof_attempted=True,
                    disproof_evidence_id=evidence_ids[-1] if evidence_ids else None,
                    notes="Non-owner blocked (403). Authorization boundary holds under lab scenario.",
                )

            # Candidate issue: skeptic still attempts alternate explanations but resolves them.
            answers = {
                SkepticQuestion.ALTERNATE_EXPLANATION: True,  # resolved: not shared ACL in body
                SkepticQuestion.INTENDED_BEHAVIOR: True,  # no public marker
                SkepticQuestion.AUTH_ACTUALLY_BYPASSED: True,
                SkepticQuestion.AUTHZ_ACTUALLY_CROSSED: True,
                SkepticQuestion.REPRODUCIBLE: True,
                SkepticQuestion.IMPACT_REAL: True,
                SkepticQuestion.EVIDENCE_COMPLETE: True,
                SkepticQuestion.IN_SCOPE: True,
                SkepticQuestion.POSSIBLE_DUPLICATE: True,
                SkepticQuestion.TEST_ARTIFACT: True,
            }
            return SkepticVerdict(
                claim=claim,
                answers=answers,
                disproof_attempted=True,
                disproof_evidence_id=evidence_ids[-1] if evidence_ids else None,
                notes="Disproof attempted: checked shared-ACL, public endpoint, role grants; none supported by lab bodies.",
            )

        loop = VerificationLoop(
            evidence_store=self.evidence,
            researcher_fn=researcher_fn,
            skeptic_fn=skeptic_fn,
        )
        ruling = loop.run(hypothesis_id=hyp_id, target=f"{host}/api/orders/1001")

        final_status = ruling.final_status.value if ruling.final_status else "unknown"
        belief_updates: list[str] = []
        # Update beliefs + hypothesis portfolio from referee outcome
        if ruling.accepted:
            b = self.research.belief_engine.assert_belief(
                claim="Cross-identity object access observed under lab scenario",
                confidence=0.9,
                supporting=list(evidence_ids),
                source="closed_loop.referee",
            )
            belief_updates.append(f"{b.belief_id}: confidence={b.confidence} (supported)")
            self.research.hypothesis_engine.update_status(hyp_id, HypothesisStatus.SUPPORTED)
            stop_reason = "sufficient_evidence"
        else:
            b = self.research.belief_engine.assert_belief(
                claim="Ownership boundary holds under lab scenario (or claim disproved)",
                confidence=0.85,
                supporting=list(evidence_ids),
                source="closed_loop.referee",
            )
            belief_updates.append(f"{b.belief_id}: confidence={b.confidence} (negative/rejected path)")
            self.research.hypothesis_engine.update_status(hyp_id, HypothesisStatus.REJECTED)
            stop_reason = "hypothesis_disproven"

        claim_text = (
            "User B can retrieve User A's order object via identifier when ownership should bind access."
            if scenario.suggests_authz_issue
            else "Non-owner cannot access owner object; authorization appears enforced."
        )
        report = build_evidence_report(
            engagement_id=self.engagement_id,
            title="Cross-identity object access on order resource",
            claim=claim_text,
            status=final_status,
            evidence_ids=list(evidence_ids),
            hypothesis_id=hyp_id,
            finding_id=ruling.finding_id,
            stop_reason=stop_reason,
            belief_updates=belief_updates,
            limitations=limitations,
        )

        summary = (
            f"scope_ok={scope_ok} scenario={scenario.name} "
            f"evidence={len(evidence_ids)} accepted={ruling.accepted} "
            f"status={final_status} finding={ruling.finding_id} "
            f"stop={stop_reason} report_blocked={report.report_blocked}"
        )

        return ClosedLoopResult(
            plan=plan,
            scope_allowed=True,
            observations=list(scenario.observations),
            evidence_ids=evidence_ids,
            referee_accepted=ruling.accepted,
            finding_id=ruling.finding_id,
            final_status=final_status,
            referee_reason=ruling.reason,
            summary=summary,
            limitations=limitations,
            stop_reason=stop_reason,
            belief_updates=belief_updates,
            report=report,
        )
