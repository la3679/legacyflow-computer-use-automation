"""Validate durable evidence and its provenance without calling the live API."""

import json
from pathlib import Path

from legacyflow.models.contracts import Artifact, Result

ROOT = Path(__file__).resolve().parents[2] / "evidence"


def events(name):
    return [json.loads(line) for line in (ROOT / name / "run.jsonl").read_text().splitlines()]


def test_discovery_provenance_and_parameterized_artifact():
    artifact = Artifact.model_validate_json(
        (ROOT / "capabilities/open-savings-subaccount.v1.json").read_text()
    )
    records = events("discovery-success")
    assert {r["run_id"] for r in records} == {artifact.discovery_run_id}
    assert any(r["event"] == "planner_configured" and r["live_api"] for r in records)
    assert any(r["event"] == "planner_action_selected" for r in records)
    assert records[-1]["status"] == "success"
    assert "12345" not in artifact.model_dump_json()


def test_committed_evidence_is_coherent_and_redacted():
    for result_file in ROOT.glob("*/result.json"):
        result = Result.model_validate_json(result_file.read_text())
        records = events(result_file.parent.name)
        assert {r["run_id"] for r in records} == {result.run_id}
        assert records[-1]["event"] == "run_completed"
        assert records[-1]["status"] == result.status
        if result.error:
            assert (result_file.parent / result.error.evidence).is_file()
        for file in result_file.parent.iterdir():
            if file.suffix in {".json", ".jsonl"}:
                text = file.read_text()
                assert all(value not in text for value in ["12345", "23456", "99999"])


def test_handoff_evidence_identifies_actor_and_same_session():
    records = events("handoff-demo")
    handoff = [
        r
        for r in records
        if r["event"]
        in {
            "session_started",
            "control_transferred",
            "human_action",
            "automation_resumed",
            "same_session_verified",
        }
    ]
    assert len({r["session_id"] for r in handoff}) == 1
    actions = [r for r in handoff if r["event"] == "human_action"]
    assert actions and all(r["actor"] == "automated_demonstrator" for r in actions)
    verification = next(r for r in handoff if r["event"] == "same_session_verified")
    assert verification["page_identity"] and verification["context_identity"]
    assert any(r["event"] == "automation_resumed" and r["revalidated"] for r in handoff)


def test_exceptional_evidence_proves_bounded_recovery_and_policy():
    recoveries = [r for r in events("replay-notice") if r["event"] == "recovery_attempted"]
    assert len(recoveries) == 1 and recoveries[0]["attempt"] == recoveries[0]["maximum"] == 1
    blocked = Result.model_validate_json((ROOT / "policy-blocked/result.json").read_text())
    assert blocked.error.code == "HUMAN_APPROVAL_REQUIRED"
    assert blocked.error.step_id == "attempt-create-account"
