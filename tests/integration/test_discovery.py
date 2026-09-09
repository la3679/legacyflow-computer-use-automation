from pathlib import Path

from legacyflow.config import Settings
from legacyflow.discovery.runner import DiscoveryRunner
from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import Artifact
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor
from legacyflow.surfaces.browser import BrowserSurface
from tests.fakes import ScriptedPlanner


async def test_discovery_compiles_live_actions(base_url: str, tmp_path: Path) -> None:
    settings = Settings(base_url=base_url, headless=True)
    evidence = Evidence(tmp_path / "runs", "test-discovery", Redactor(["12345"]))
    artifact_path = tmp_path / "capability.json"
    async with BrowserSurface(settings, Policy(allowed_origins=[base_url]), evidence) as surface:
        result = await DiscoveryRunner(surface, ScriptedPlanner(), evidence, settings).run(
            "Prepare savings to review",
            "/members",
            {"member_id": "12345", "initial_deposit": "100"},
            artifact_path,
        )
    assert result.status == "success", result
    assert result.outputs["review_status"] == "ready"
    artifact = Artifact.model_validate_json(artifact_path.read_text())
    assert len(artifact.steps) == 6
    assert "12345" not in artifact_path.read_text()
    assert "12345" not in (evidence.directory / "run.jsonl").read_text()


async def test_discovery_limit_returns_failure(base_url: str, tmp_path: Path) -> None:
    settings = Settings(base_url=base_url, headless=True, max_steps=1)
    evidence = Evidence(tmp_path, "test-discovery", Redactor(["12345"]))
    async with BrowserSurface(settings, Policy(allowed_origins=[base_url]), evidence) as surface:
        result = await DiscoveryRunner(surface, ScriptedPlanner(), evidence, settings).run(
            "Prepare savings",
            "/members",
            {"member_id": "12345", "initial_deposit": "100"},
            tmp_path / "artifact.json",
        )
    assert result.error and result.error.code == "MAX_STEPS"
    assert (evidence.directory / "failure.png").exists()
