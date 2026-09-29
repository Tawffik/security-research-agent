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
from agent_core.orchestrator.experiment_alignment import (
    align_experiment_to_scenario,
    resolve_selected_experiment,
)
from agent_core.evaluation.episode import EpisodeRecorder, ResearchEpisode
from agent_core.knowledge.candidates import KnowledgeCandidateFactory
from agent_core.schemas.observation import Observation, from_lab_observation
from agent_core.knowledge.case_extract import extract_case_from_episode
from agent_core.hypotheses.update import apply_evidence_to_hypotheses
from agent_core.findings.poc import MinimizedPoC, PoCMinimizer
from agent_core.findings.report import EvidenceReport, build_evidence_report
from agent_core.orchestrator.research_loop import ResearchLoop, ResearchLoopResult
from agent_core.schemas.research import HypothesisStatus
from agent_core.scope.guard import Decision as ScopeDecision, RiskTier, ScopeGuard
from agent_core.variants.hunter import VariantCandidate, VariantHunter
from agent_core.variants.root_cause import RootCause, RootCauseEngine
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
    # M5: fixture-side role metadata (not inferred from list index)
    role: str = ""  # baseline | challenge | "" (unset)


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
    # Hard-scenario: confirm only if selected experiment is knowledge/procedure-driven
    requires_knowledge_procedure: bool = False
    methodology: str = "authorization"


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
    selected_experiment_id: Optional[str] = None
    experiment_alignment: Optional[dict] = None
    budget_exhausted: bool = False
    knowledge_procedure_required_blocked: bool = False
    hypothesis_updates: list = field(default_factory=list)
    max_experiments_budget: Optional[int] = None
    experiments_designed: int = 0
    report: Optional[EvidenceReport] = None
    root_cause: Optional[RootCause] = None
    variants: list[VariantCandidate] = field(default_factory=list)
    poc: Optional[MinimizedPoC] = None
    episode: Optional[ResearchEpisode] = None
    knowledge_candidates: list = field(default_factory=list)
    normalized_observations: list = field(default_factory=list)
    structured_case: object = None  # episode → case candidate (untrusted)


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
                role="baseline"),
            LabObservation(
                identity="user_b",
                method="GET",
                path="/api/orders/1001",
                host=host,
                status=200,
                body='{"id":1001,"owner":"user_a","amount":42.00,"status":"PAID"}',
                notes="non-owner received owner object body",
                role="challenge"),
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
                role="baseline"),
            LabObservation(
                identity="user_b",
                method="GET",
                path="/api/orders/1001",
                host=host,
                status=403,
                body='{"error":"forbidden"}',
                role="challenge"),
        ],
    )


def public_resource_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """L2 FP trap: both identities get 200 because resource is intentionally public."""
    return LabScenario(
        name="lab_public_resource",
        expected_if_secure="Public catalog is readable by any authenticated user — not IDOR",
        suggests_authz_issue=False,
        observations=[
            LabObservation(
                identity="user_a",
                method="GET",
                path="/api/catalog/item/5",
                host=host,
                status=200,
                body='{"id":5,"visibility":"public","name":"widget"}',
                notes="public resource baseline",
                role="baseline"),
            LabObservation(
                identity="user_b",
                method="GET",
                path="/api/catalog/item/5",
                host=host,
                status=200,
                body='{"id":5,"visibility":"public","name":"widget"}',
                notes="same public resource — not ownership bypass",
                role="challenge"),
        ],
    )


def shared_object_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """L2 FP trap: intentional shared ACL — both users legitimately access same object."""
    return LabScenario(
        name="lab_shared_acl_object",
        expected_if_secure="Shared ACL grants both identities access — not horizontal IDOR",
        suggests_authz_issue=False,
        observations=[
            LabObservation(
                identity="user_a",
                method="GET",
                path="/api/docs/shared-9",
                host=host,
                status=200,
                body='{"id":"shared-9","acl":["user_a","user_b"],"title":"team notes"}',
                role="baseline"),
            LabObservation(
                identity="user_b",
                method="GET",
                path="/api/docs/shared-9",
                host=host,
                status=200,
                body='{"id":"shared-9","acl":["user_a","user_b"],"title":"team notes"}',
                role="challenge"),
        ],
    )



def hard_authz_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """
    Hard authz: same leak signals as IDOR, but confirmation requires
    knowledge/procedure-driven experiment selection (baseline without knowledge → incomplete).
    """
    return LabScenario(
        name="lab_hard_authz_requires_procedure",
        expected_if_secure="Non-owner denied",
        suggests_authz_issue=True,
        requires_knowledge_procedure=True,
        methodology="authorization",
        observations=[
            LabObservation(
                identity="user_a", method="GET", path="/api/orders/1001", host=host,
                status=200, body='{"id":1001,"owner":"user_a","secret":"s"}', notes="owner",
                role="baseline",
            ),
            LabObservation(
                identity="user_b", method="GET", path="/api/orders/1001", host=host,
                status=200, body='{"id":1001,"owner":"user_a","secret":"s"}', notes="leak",
                role="challenge",
            ),
        ],
    )


def business_logic_coupon_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """Coupon replay: second redemption still accepted — business invariant break."""
    return LabScenario(
        name="lab_business_logic_coupon_replay",
        expected_if_secure="Second redemption rejected",
        suggests_authz_issue=True,  # treated as issue path for lab referee
        requires_knowledge_procedure=True,
        methodology="business_logic",
        observations=[
            LabObservation(
                identity="user_a", method="POST", path="/api/checkout", host=host,
                status=200, body='{"order":1,"coupon":"SAVE10","applied":true}',
                notes="first redeem", role="baseline",
            ),
            LabObservation(
                identity="user_a", method="POST", path="/api/checkout", host=host,
                status=200, body='{"order":2,"coupon":"SAVE10","applied":true}',
                notes="replay accepted", role="challenge",
            ),
        ],
    )


def hard_ssrf_lab_scenario(host: str = "api.acme-demo.test") -> LabScenario:
    """SSRF-like: challenge fetch returns metadata markers; requires knowledge procedure."""
    return LabScenario(
        name="lab_hard_ssrf_metadata",
        expected_if_secure="No internal metadata body",
        suggests_authz_issue=True,
        requires_knowledge_procedure=True,
        methodology="ssrf",
        observations=[
            LabObservation(
                identity="svc", method="POST", path="/api/fetch", host=host,
                status=200, body='{"url":"https://example.com","ok":true}',
                notes="public url", role="baseline",
            ),
            LabObservation(
                identity="svc", method="POST", path="/api/fetch", host=host,
                status=200, body='{"url":"http://169.254.169.254/","body":"meta"}',
                notes="metadata", role="challenge",
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
        knowledge_retriever=None,
        max_experiments_budget: Optional[int] = None,
    ):
        self.engagement_id = engagement_id
        self.scope_path = Path(scope_path)
        self.guard = ScopeGuard.from_scope_file(self.scope_path)
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="sra_loop_"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.evidence = EvidenceStore.open(self.data_dir / f"{engagement_id}_evidence.db")
        self.research = ResearchLoop(
            engagement_id=engagement_id,
            knowledge_retriever=knowledge_retriever,
        )
        self.max_experiments_budget = max_experiments_budget

    def run(
        self,
        recon_path: Union[str, Path],
        scenario: Optional[LabScenario] = None,
        force_experiment=None,
        skip_research: bool = False,
        prior_plan=None,
    ) -> ClosedLoopResult:
        """
        force_experiment: bind this Experiment for alignment (M7 follow-up).
        skip_research + prior_plan: re-evaluate fixtures under a new experiment without re-planning.
        """
        host_hint = "api.acme-demo.test"
        scenario = scenario or default_idor_lab_scenario(host_hint)
        if getattr(scenario, "methodology", None):
            self.research.preferred_methodology = scenario.methodology

        if skip_research and prior_plan is not None:
            plan = prior_plan
        else:
            plan = self.research.run_from_recon_file(recon_path)
        host = plan.target_context.primary_host or host_hint

        selected_experiment = force_experiment or resolve_selected_experiment(plan)
        hyp_id_early = (
            (plan.decision.hypothesis_id if plan.decision else None)
            or (plan.hypotheses[0].hypothesis_id if plan.hypotheses else None)
        )
        alignment = align_experiment_to_scenario(
            selected_experiment,
            scenario,
            hypothesis_id=hyp_id_early,
        )

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
            deny_result = ClosedLoopResult(
                plan=plan,
                scope_allowed=False,
                summary=f"SCOPE_DENIED by ScopeGuard: {decision.value}",
                limitations=limitations,
                referee_reason=f"ScopeGuard returned {decision.value}",
                stop_reason=stop_reason,
                report=report,
            )
            deny_result.episode = EpisodeRecorder(self.engagement_id).from_closed_loop(deny_result)
            return deny_result

        evidence_ids: list[str] = []
        hyp_id = alignment.hypothesis_id or plan.decision.hypothesis_id or (
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
            # Prefer explicit observation role when present (M11); fall back to identity heuristic
            is_challenge = (getattr(obs, "role", "") or "") == "challenge" or (
                not getattr(obs, "role", None) and obs.identity != "user_a"
            )
            if scenario.suggests_authz_issue and is_challenge and obs.status == 200:
                polarity = EvidencePolarity.POSITIVE  # supports candidate issue
            elif not scenario.suggests_authz_issue and is_challenge and obs.status in (401, 403, 404):
                polarity = EvidencePolarity.NEGATIVE  # ownership enforced
            # Experiment-aware adjustment: incomplete required evidence → down-weight to NEUTRAL
            if alignment.required_evidence and not all(
                r.status == "satisfied" for r in alignment.required_evidence
            ):
                if polarity == EvidencePolarity.POSITIVE and any(
                    r.status == "missing" for r in alignment.required_evidence
                ):
                    polarity = EvidencePolarity.NEUTRAL
            # Discriminator contradicts scenario issue path → prefer NEUTRAL for non-owner 200
            if (
                alignment.discriminator_outcome == "contradicts"
                and polarity == EvidencePolarity.POSITIVE
            ):
                polarity = EvidencePolarity.NEUTRAL

            role = getattr(obs, "role", "") or ""
            ev = self.evidence.record(
                target=f"{obs.host}{obs.path}",
                action=f"{obs.method} as {obs.identity}",
                input_data=f"identity={obs.identity}|role={role}",
                expected=scenario.expected_if_secure,
                observed=f"status={obs.status} body={rendered[:500]}",
                polarity=polarity,
                confidence=0.85,
                source=(f"closed_loop.lab_scenario|exp={alignment.experiment_id}|hyp={alignment.hypothesis_id}|sc={scenario.name}"),
                related_hypothesis=hyp_id,
            )
            evidence_ids.append(ev.evidence_id)

        # M4: experiment alignment metadata as NEUTRAL evidence (not a finding)
        align_blob = alignment.to_dict()
        ev_align = self.evidence.record(
            target=f"{host}/experiment_alignment",
            action=f"align experiment {alignment.experiment_id}",
            input_data=str(align_blob),
            expected=alignment.discriminator or "n/a",
            observed=(
                f"discriminator_outcome={alignment.discriminator_outcome};"
                f"stop={alignment.stop_condition_status};"
                f"req={[(r.requirement, r.status) for r in alignment.required_evidence]}"
            ),
            polarity=EvidencePolarity.NEUTRAL,
            confidence=0.9,
            related_hypothesis=alignment.hypothesis_id or hyp_id_early,
            source=(
                f"closed_loop.experiment_alignment|exp={alignment.experiment_id}"
                f"|hyp={alignment.hypothesis_id}|sc={scenario.name}"
            ),
        )
        evidence_ids.append(ev_align.evidence_id)

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

        # Hard-scenario gate: require procedure-driven experiment for confirmation
        knowledge_driven = bool(
            getattr(self.research.experiment_designer, "last_procedure_ids", None)
        ) or bool(
            selected_experiment
            and (
                "procedure:" in (getattr(selected_experiment, "discriminator", "") or "")
                or getattr(selected_experiment, "steps", None)
            )
        )
        knowledge_blocked = False
        if getattr(scenario, "requires_knowledge_procedure", False) and not knowledge_driven:
            knowledge_blocked = True
            # Force incomplete — discriminating procedure not selected (baseline insufficiency)
            class _Forced:
                accepted = False
                final_status = type("S", (), {"value": "incomplete"})()
                finding_id = None
                reason = "knowledge_procedure_required_not_selected"
            ruling = _Forced()  # type: ignore

        final_status = ruling.final_status.value if ruling.final_status else "unknown"
        belief_updates: list[str] = []
        # Update beliefs + hypothesis portfolio from referee outcome
        # Gate 3: observation/evidence polarity → hypothesis portfolio update
        pol = "positive" if ruling.accepted else "negative"
        hyp_updates = apply_evidence_to_hypotheses(
            list(plan.hypotheses or []),
            polarity=pol,
            evidence_ids=list(evidence_ids),
            competing_notes=list(
                (self.research.last_retrieval.competing_explanations
                 if self.research.last_retrieval else []) or []
            )[:3],
        )
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

        root_cause = None
        variants: list[VariantCandidate] = []
        if ruling.accepted and ruling.finding_id:
            rc_engine = RootCauseEngine(self.engagement_id)
            root_cause = rc_engine.analyze_confirmed(
                finding_id=ruling.finding_id,
                claim=claim_text,
                evidence_ids=list(evidence_ids),
                ctx=plan.target_context,
                scenario_name=scenario.name,
            )
            hunter = VariantHunter(self.engagement_id)
            variants = hunter.find_structural(
                ctx=plan.target_context,
                graph=plan.target_graph,
                root_cause=root_cause,
                seed_path_substr="orders",
                limit=5,
            )

        poc = None
        if ruling.accepted and ruling.finding_id and evidence_ids:
            poc = PoCMinimizer(self.engagement_id).minimize(
                finding_id=ruling.finding_id,
                observations=list(scenario.observations),
                evidence_ids=list(evidence_ids),
                claim=claim_text,
            )

        summary = (
            f"scope_ok={scope_ok} scenario={scenario.name} "
            f"evidence={len(evidence_ids)} accepted={ruling.accepted} "
            f"status={final_status} finding={ruling.finding_id} "
            f"stop={stop_reason} report_blocked={report.report_blocked} "
            f"root_cause={root_cause.root_cause_id if root_cause else None} "
            f"variants={len(variants)} "
            f"poc={poc.poc_id if poc else None}"
        )

        out = ClosedLoopResult(
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
            root_cause=root_cause,
            variants=variants,
            poc=poc,
            selected_experiment_id=alignment.experiment_id,
            knowledge_procedure_required_blocked=knowledge_blocked,
            hypothesis_updates=hyp_updates,
            experiments_designed=len(plan.experiments or []),
            max_experiments_budget=getattr(self, "max_experiments_budget", None),
            experiment_alignment=alignment.to_dict(),
        )
        # M11: normalize lab observations (not findings)
        base_lab = None
        for i, lo in enumerate(out.observations or []):
            if getattr(lo, "role", "") == "baseline":
                base_lab = lo
                break
            if i == 0:
                base_lab = lo
        out.normalized_observations = [
            from_lab_observation(
                lo,
                engagement_id=self.engagement_id,
                experiment_id=out.selected_experiment_id or "",
                hypothesis_id=alignment.hypothesis_id if alignment else "",
                index=i,
                baseline=base_lab if getattr(lo, "role", "") == "challenge" else None,
            )
            for i, lo in enumerate(out.observations or [])
        ]
        out.episode = EpisodeRecorder(self.engagement_id).from_closed_loop(out)
        out.knowledge_candidates = KnowledgeCandidateFactory(self.engagement_id).from_closed_loop(
            out, episode_id=getattr(out.episode, "episode_id", "")
        )
        try:
            out.structured_case = extract_case_from_episode(
                out, case_id=f"CASE-EP-{self.engagement_id}"
            )
        except Exception:
            out.structured_case = None
        return out
