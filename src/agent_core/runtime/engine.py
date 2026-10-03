"""
ResearchRuntime — HTTP-independent session orchestration.

Wires existing ClosedLoopRunner (offline lab) into session lifecycle.
Never enables live HTTP from this control path.
"""

from __future__ import annotations

import threading
import traceback
from pathlib import Path
from typing import Any, Optional

from agent_core.orchestrator.closed_loop import ClosedLoopRunner, secure_lab_scenario
from agent_core.runtime.events import EventType, RuntimeEvent
from agent_core.runtime.session import ResearchSession, SessionStatus
from agent_core.runtime.store import SessionStore
from agent_core.tools.browser_health import check_browser_health


ROOT = Path(__file__).resolve().parents[3]


class ResearchRuntime:
    def __init__(self, store: SessionStore, *, default_recon: Path | None = None, default_scope: Path | None = None):
        self.store = store
        self.default_recon = default_recon or (ROOT / "examples" / "fixtures" / "sample_recon.json")
        self.default_scope = default_scope or (ROOT / "examples" / "demo_program_scope.yaml")
        self._threads: dict[str, threading.Thread] = {}
        self._stop_flags: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def emit(self, session: ResearchSession, et: EventType, message: str = "", data: dict | None = None) -> RuntimeEvent:
        seq = self.store.next_sequence(session.session_id)
        ev = RuntimeEvent.create(session.session_id, et, sequence=seq, message=message, data=data)
        self.store.append_event(ev)
        return ev

    def create_session(self, *, label: str = "", recon_path: str = "", scope_path: str = "") -> ResearchSession:
        recon = recon_path or str(self.default_recon)
        scope = scope_path or str(self.default_scope)
        # Fail closed: never accept live_http via create
        sess = ResearchSession.new(label=label, recon_path=recon, scope_path=scope)
        sess.status = SessionStatus.READY.value
        sess.live_http = False
        self.store.save_session(sess)
        self.emit(sess, EventType.SESSION_CREATED, "session created", {"live_http": False})
        return sess

    def get(self, session_id: str) -> Optional[ResearchSession]:
        return self.store.get_session(session_id)

    def list_sessions(self) -> list[ResearchSession]:
        return self.store.list_sessions()

    def start(self, session_id: str) -> ResearchSession:
        with self._lock:
            sess = self.store.get_session(session_id)
            if not sess:
                raise KeyError("session_not_found")
            if sess.status == SessionStatus.RUNNING.value:
                return sess  # idempotent
            if sess.is_terminal():
                raise ValueError(f"cannot_start_terminal_{sess.status}")
            if sess.status not in (
                SessionStatus.READY.value,
                SessionStatus.PAUSED.value,
                SessionStatus.CREATED.value,
            ):
                raise ValueError(f"invalid_start_from_{sess.status}")
            sess.status = SessionStatus.RUNNING.value
            sess.current_phase = "starting"
            sess.error = ""
            self.store.save_session(sess)
            self.emit(sess, EventType.SESSION_STARTED, "research started (offline lab)")
            flag = threading.Event()
            self._stop_flags[session_id] = flag
            t = threading.Thread(target=self._run, args=(session_id, flag), daemon=True)
            self._threads[session_id] = t
            t.start()
            return sess

    def stop(self, session_id: str) -> ResearchSession:
        with self._lock:
            sess = self.store.get_session(session_id)
            if not sess:
                raise KeyError("session_not_found")
            if sess.is_terminal() and sess.status != SessionStatus.RUNNING.value:
                return sess  # idempotent
            flag = self._stop_flags.get(session_id)
            if flag:
                flag.set()
            sess.status = SessionStatus.CANCELLED.value
            sess.current_phase = "stopped"
            sess.stop_reason = "user_stop"
            self.store.save_session(sess)
            self.emit(sess, EventType.STOPPED, "stop requested")
            return sess

    def pause(self, session_id: str) -> ResearchSession:
        """Cooperative pause marker — current offline run is short; records PAUSED if running."""
        sess = self.store.get_session(session_id)
        if not sess:
            raise KeyError("session_not_found")
        if sess.status != SessionStatus.RUNNING.value:
            return sess
        sess.status = SessionStatus.PAUSED.value
        sess.current_phase = "paused"
        self.store.save_session(sess)
        self.emit(sess, EventType.PAUSED, "paused")
        return sess

    def resume(self, session_id: str) -> ResearchSession:
        sess = self.store.get_session(session_id)
        if not sess:
            raise KeyError("session_not_found")
        if sess.status != SessionStatus.PAUSED.value:
            return sess
        return self.start(session_id)

    def _run(self, session_id: str, stop_flag: threading.Event) -> None:
        sess = self.store.get_session(session_id)
        if not sess:
            return
        try:
            if stop_flag.is_set():
                return
            sess.current_phase = "closed_loop"
            self.store.save_session(sess)
            self.emit(sess, EventType.PHASE_CHANGED, "closed_loop", {"phase": "closed_loop"})

            recon = Path(sess.recon_path)
            scope = Path(sess.scope_path)
            if not recon.exists() or not scope.exists():
                raise FileNotFoundError("recon_or_scope_missing")

            # Explicit: offline only
            runner = ClosedLoopRunner(scope_path=scope, engagement_id=session_id)
            result = runner.run(recon, scenario=secure_lab_scenario())

            if stop_flag.is_set():
                sess = self.store.get_session(session_id) or sess
                sess.status = SessionStatus.CANCELLED.value
                self.store.save_session(sess)
                return

            hyp_ids = [getattr(h, "hypothesis_id", str(h)) for h in (getattr(result.plan, "hypotheses", None) or [])][:5]
            if hyp_ids:
                sess.current_hypothesis = hyp_ids[0]
                self.emit(sess, EventType.HYPOTHESIS_SELECTED, hyp_ids[0], {"hypothesis_ids": hyp_ids})

            exp_ids = [getattr(e, "experiment_id", str(e)) for e in (getattr(result.plan, "experiments", None) or [])][:5]
            if exp_ids:
                sess.current_experiment = exp_ids[0]
                self.emit(sess, EventType.EXPERIMENT_SELECTED, exp_ids[0], {"experiment_ids": exp_ids})
                self.emit(sess, EventType.EXPERIMENT_STARTED, exp_ids[0])

            evidence_ids = list(getattr(result, "evidence_ids", None) or [])
            sess.evidence_count = len(evidence_ids)
            if evidence_ids:
                sess.latest_evidence = evidence_ids[-1]
                self.emit(
                    sess,
                    EventType.EVIDENCE_RECORDED,
                    f"{len(evidence_ids)} evidence ids",
                    {"evidence_ids": evidence_ids[:20]},
                )

            outcome = str(getattr(result, "outcome", "") or getattr(getattr(result, "episode", None), "outcome", "") or "")
            stop_reason = str(getattr(result, "stop_reason", "") or "")
            finding_id = getattr(result, "finding_id", None)
            sess.outcome = outcome
            sess.stop_reason = stop_reason
            sess.latest_finding = str(finding_id or "")
            sess.trajectory_summary = f"outcome={outcome} stop={stop_reason} evidence={len(evidence_ids)}"
            sess.report = {
                "outcome": outcome,
                "stop_reason": stop_reason,
                "finding_id": finding_id,
                "evidence_ids": evidence_ids[:50],
                "hypothesis_ids": hyp_ids,
                "experiment_ids": exp_ids,
                "live_http": False,
                "execution_mode": "offline_lab",
            }

            if finding_id:
                self.emit(sess, EventType.FINDING_VERIFIED, str(finding_id), {"finding_id": finding_id})
                sess.status = SessionStatus.COMPLETED.value
                self.emit(sess, EventType.SESSION_COMPLETED, "completed with finding path")
            elif outcome.lower() in ("rejected", "no_finding", "secure"):
                self.emit(sess, EventType.NEGATIVE_EVIDENCE_RECORDED, outcome or "negative")
                sess.status = SessionStatus.COMPLETED.value
                self.emit(sess, EventType.SESSION_COMPLETED, "completed without vulnerability finding")
            elif "block" in stop_reason.lower():
                sess.status = SessionStatus.BLOCKED.value
                self.emit(sess, EventType.BLOCKED, stop_reason)
            else:
                sess.status = SessionStatus.INCONCLUSIVE.value
                self.emit(sess, EventType.SESSION_INCONCLUSIVE, stop_reason or outcome or "inconclusive")

            sess.current_phase = "done"
            self.store.save_session(sess)
        except Exception as e:
            sess = self.store.get_session(session_id) or sess
            sess.status = SessionStatus.FAILED.value
            sess.error = str(e)[:500]
            sess.current_phase = "failed"
            self.store.save_session(sess)
            self.emit(
                sess,
                EventType.SESSION_FAILED,
                str(e)[:200],
                {"traceback": traceback.format_exc()[-800:]},
            )
        finally:
            self._stop_flags.pop(session_id, None)
            self._threads.pop(session_id, None)

    def health(self) -> dict[str, Any]:
        bh = check_browser_health(try_launch=False)
        return {
            "agent": "ok",
            "runtime": "ok",
            "browser": bh.to_dict(),
            "live_http_default": False,
            "persistence": str(self.store.db_path),
        }
