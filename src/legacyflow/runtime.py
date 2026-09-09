"""Deterministic runtime classification shared by discovery and replay; no planner dependency."""

from pathlib import Path

from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import Failure, FlowError, Observation, Result
from legacyflow.surfaces.base import ComputerSurface


def classify(observation: Observation) -> str | None:
    if observation.application != "legacyflow-demo" or not observation.app_version.startswith("1."):
        raise FlowError(
            "INCOMPATIBLE_APP", "legacyflow-demo 1.x", "application identity/version drift"
        )
    if observation.heading == "Member Not Found":
        return "member_not_found"
    if observation.heading in {"Permission Denied", "Session Expired"}:
        raise FlowError(
            observation.heading.upper().replace(" ", "_"), "accessible session", observation.heading
        )
    if observation.messages:
        raise FlowError("INTERVENTION_REQUIRED", "unblocked application", observation.messages[0])
    return None


async def failed(
    surface: ComputerSurface, evidence: Evidence, error: FlowError, step_id: str, completed: int
) -> Result:
    image: str | None = "failure.png"
    try:
        await surface.screenshot(evidence.directory / "failure.png")
    except Exception:
        image = None
    failure = Failure(
        code=error.code,
        step_id=step_id,
        expected=error.expected,
        observed=error.observed,
        evidence=image,
    )
    evidence.event("hard_failure", **failure.model_dump())
    return evidence.finish(
        Result(status="failure", run_id=evidence.run_id, steps_completed=completed, error=failure)
    )


async def business_outcome(surface: ComputerSurface, evidence: Evidence, completed: int) -> Result:
    await surface.screenshot(evidence.directory / "business-outcome.png")
    evidence.event("business_outcome_detected", outcome="member_not_found")
    return evidence.finish(
        Result(
            status="business_outcome",
            run_id=evidence.run_id,
            steps_completed=completed,
            outcome="member_not_found",
        )
    )


async def final_screenshot(surface: ComputerSurface, directory: Path) -> None:
    await surface.screenshot(directory / "final-screenshot.png")
