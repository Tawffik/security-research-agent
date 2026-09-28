"""M11: Normalized Observation from lab fixtures — not findings."""

from pathlib import Path

from agent_core.orchestrator.closed_loop import ClosedLoopRunner, default_idor_lab_scenario
from agent_core.schemas.observation import Observation, from_lab_observation
from agent_core.orchestrator.closed_loop import LabObservation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_from_lab_observation_fields():
    lab = LabObservation(
        identity="user_b",
        method="GET",
        path="/api/x",
        host="h",
        status=200,
        body='{"a":1}',
        role="challenge",
    )
    base = LabObservation(
        identity="user_a", method="GET", path="/api/x", host="h", status=200, body='{"a":2}', role="baseline"
    )
    obs = from_lab_observation(lab, engagement_id="e", experiment_id="exp1", index=1, baseline=base)
    assert isinstance(obs, Observation)
    assert obs.status_delta == 0
    assert obs.body_changed is True
    assert obs.experiment_id == "exp1"
    assert obs.source == "lab"


def test_closed_loop_attaches_normalized_observations():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_obs").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    assert result.normalized_observations
    assert all(isinstance(o, Observation) for o in result.normalized_observations)
    # Observation is not a finding
    assert result.finding_id is None or result.referee_accepted is not None
