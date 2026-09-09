import builtins
from pathlib import Path

import pytest

from legacyflow.config import Settings
from legacyflow.discovery.runner import DiscoveryRunner
from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import Artifact, Value
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor
from legacyflow.replay.engine import ReplayEngine
from legacyflow.surfaces.browser import BrowserSurface
from tests.fakes import ScriptedPlanner


@pytest.fixture
async def artifact(base_url: str, tmp_path: Path) -> Artifact:
    settings = Settings(base_url=base_url, headless=True)
    evidence = Evidence(tmp_path, "offline-discovery", Redactor(["12345"]))
    path = tmp_path / "capability.json"
    async with BrowserSurface(settings, Policy(allowed_origins=[base_url]), evidence) as surface:
        result = await DiscoveryRunner(surface, ScriptedPlanner(), evidence, settings).run(
            "Prepare savings to review",
            "/members",
            {"member_id": "12345", "initial_deposit": "100"},
            path,
        )
    assert result.status == "success"
    return Artifact.model_validate_json(path.read_text())


@pytest.mark.parametrize(
    "member,scenario,status,code",
    [
        ("23456", "normal", "success", None),
        ("23456", "notice", "success", None),
        ("23456", "slow", "success", None),
        ("23456", "handoff", "failure", "INTERVENTION_REQUIRED"),
        ("99999", "normal", "business_outcome", None),
        ("40300", "normal", "failure", "PERMISSION_DENIED"),
        ("23456", "expired", "failure", "SESSION_EXPIRED"),
    ],
)
async def test_replay_outcomes_without_planner(
    artifact: Artifact,
    base_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    member: str,
    scenario: str,
    status: str,
    code: str | None,
) -> None:
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(("openai", "legacyflow.discovery")):
            raise AssertionError("Replay attempted planner import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(base_url=base_url, headless=True)
    evidence = Evidence(tmp_path, "replay", Redactor([member]))
    async with BrowserSurface(settings, Policy(allowed_origins=[base_url]), evidence) as surface:
        result = await ReplayEngine(surface, evidence, settings).run(
            artifact, {"member_id": member, "initial_deposit": "250"}, scenario
        )
    assert result.status == status, result
    if code:
        assert result.error and result.error.code == code
        assert result.error.evidence
    if status == "success":
        assert result.outputs["member_name"] == "Casey Example"
        assert result.outputs["initial_deposit"] == "250.00"
    assert member not in (evidence.directory / "run.jsonl").read_text()


async def test_final_checkpoint_is_verified(
    artifact: Artifact, base_url: str, tmp_path: Path
) -> None:
    artifact.success_checkpoint.value = Value(source="literal", value="Wrong heading")
    settings = Settings(base_url=base_url, headless=True, action_timeout_ms=200)
    evidence = Evidence(tmp_path, "replay", Redactor())
    async with BrowserSurface(settings, Policy(allowed_origins=[base_url]), evidence) as surface:
        result = await ReplayEngine(surface, evidence, settings).run(
            artifact, {"member_id": "23456", "initial_deposit": "250"}
        )
    assert result.error and result.error.code == "CHECKPOINT_FAILED"
