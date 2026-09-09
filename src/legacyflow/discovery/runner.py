import asyncio
from pathlib import Path

from legacyflow.config import Settings
from legacyflow.discovery.planner import Planner
from legacyflow.discovery.recorder import Recorder
from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import Action, FlowError, Result, Value
from legacyflow.runtime import business_outcome, classify, failed, final_screenshot, ready
from legacyflow.surfaces.base import ComputerSurface


class DiscoveryRunner:
    def __init__(
        self, surface: ComputerSurface, planner: Planner, evidence: Evidence, settings: Settings
    ) -> None:
        self.surface, self.planner, self.evidence, self.settings = (
            surface,
            planner,
            evidence,
            settings,
        )

    async def run(
        self, goal: str, target: str, inputs: dict[str, str], artifact_path: Path
    ) -> Result:
        recorder = Recorder()
        history: list[str] = []
        step_id = "entry"
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                await self.surface.execute(
                    Action(kind="navigate", value=Value(source="literal", value=target)), {}
                )
                for index in range(self.settings.max_steps):
                    step_id = f"decision-{index + 1:02d}"
                    observation = await ready(self.surface, self.evidence)
                    if classify(observation):
                        return await business_outcome(
                            self.surface, self.evidence, len(recorder.steps)
                        )
                    decision = await self.planner.decide(goal, observation, inputs, history)
                    self.evidence.event(
                        "planner_action_selected", step_id=step_id, decision=decision.model_dump()
                    )
                    if decision.action == "finish":
                        artifact = recorder.compile(observation, self.evidence.run_id)
                        await self.surface.verify(artifact.success_checkpoint, inputs)
                        outputs = {
                            name: await self.surface.read(spec.target)
                            for name, spec in artifact.outputs.items()
                        }
                        artifact.validate_inputs(inputs)
                        artifact_path.parent.mkdir(parents=True, exist_ok=True)
                        artifact_path.write_text(
                            artifact.model_dump_json(indent=2) + "\n", encoding="utf-8"
                        )
                        self.evidence.event("checkpoint_verified", verified=True)
                        await final_screenshot(self.surface, self.evidence.directory)
                        return self.evidence.finish(
                            Result(
                                status="success",
                                run_id=self.evidence.run_id,
                                steps_completed=len(recorder.steps),
                                outputs=outputs,
                            )
                        )
                    if decision.action == "escalate":
                        raise FlowError(
                            "INTERVENTION_REQUIRED",
                            "human assistance",
                            "planner requested assistance",
                        )
                    control = next(
                        (c for c in observation.controls if c.id == decision.control_id), None
                    )
                    value = None
                    if decision.input_name is not None:
                        if decision.input_name not in inputs:
                            raise FlowError(
                                "INVALID_PARAMETER", "known input", "unknown input reference"
                            )
                        value = Value(source="input", value=decision.input_name)
                    elif decision.literal is not None:
                        value = Value(source="literal", value=decision.literal)
                    if decision.action == "type" and (value is None or value.source != "input"):
                        raise FlowError(
                            "LITERAL_INPUT_BLOCKED", "input reference", "literal form value"
                        )
                    action = Action(
                        kind=decision.action,
                        target=control.target if control else None,
                        value=value,
                    )
                    fingerprint = ":".join(
                        [
                            action.kind,
                            control.name if control else "",
                            decision.input_name or decision.literal or "",
                        ]
                    )
                    if history[-2:] == [fingerprint, fingerprint]:
                        raise FlowError("DEAD_END", "progress", "repeated identical action")
                    await self.surface.execute(action, inputs)
                    after = await ready(self.surface, self.evidence)
                    if classify(after):
                        return await business_outcome(
                            self.surface, self.evidence, len(recorder.steps) + 1
                        )
                    condition = recorder.condition(action, after)
                    await self.surface.verify(condition, inputs)
                    recorder.record(action, condition)
                    history.append(fingerprint)
                raise FlowError(
                    "MAX_STEPS", "goal completed within step limit", "step limit reached"
                )
        except TimeoutError:
            return await failed(
                self.surface,
                self.evidence,
                FlowError("RUN_TIMEOUT", "bounded run", "run deadline reached"),
                step_id,
                len(recorder.steps),
            )
        except FlowError as error:
            return await failed(self.surface, self.evidence, error, step_id, len(recorder.steps))
        except Exception as error:
            return await failed(
                self.surface,
                self.evidence,
                FlowError("RUNTIME_ERROR", "valid UI action", type(error).__name__),
                step_id,
                len(recorder.steps),
            )
