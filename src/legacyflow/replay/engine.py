import asyncio
from decimal import Decimal, InvalidOperation

from legacyflow.config import Settings
from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import Action, Artifact, FlowError, Result, Value
from legacyflow.runtime import business_outcome, classify, failed, final_screenshot, ready
from legacyflow.surfaces.base import ComputerSurface


class ReplayEngine:
    def __init__(self, surface: ComputerSurface, evidence: Evidence, settings: Settings) -> None:
        self.surface, self.evidence, self.settings = surface, evidence, settings

    async def run(
        self, artifact: Artifact, inputs: dict[str, str], scenario: str = "normal"
    ) -> Result:
        completed, step_id = 0, "entry"
        try:
            try:
                inputs = artifact.validate_inputs(inputs)
            except ValueError:
                raise FlowError(
                    "INVALID_INPUT", "typed capability inputs", "input validation failed"
                ) from None
            if artifact.target.variant != "base" or artifact.target.app_major != 1:
                raise FlowError(
                    "INCOMPATIBLE_VARIANT", "reviewed base variant 1.x", "unsupported variant"
                )
            async with asyncio.timeout(self.settings.timeout_seconds):
                if scenario not in {"normal", "notice", "slow", "permission", "handoff", "expired"}:
                    raise FlowError("INVALID_SCENARIO", "known demo scenario", "unknown scenario")
                entry = artifact.target.entry_point + f"?scenario={scenario}"
                await self.surface.execute(
                    Action(kind="navigate", value=Value(source="literal", value=entry)), {}
                )
                observation = await ready(self.surface, self.evidence)
                if observation.application != artifact.target.application:
                    raise FlowError(
                        "INCOMPATIBLE_APP", artifact.target.application, "identity mismatch"
                    )
                if classify(observation):
                    return await business_outcome(self.surface, self.evidence, completed)
                for step in artifact.steps:
                    step_id = step.id
                    if step.risk == "irreversible":
                        raise FlowError(
                            "HUMAN_APPROVAL_REQUIRED", "human approval", "irreversible step"
                        )
                    self.evidence.event("step_started", step_id=step_id, capability_id=artifact.id)
                    await self.surface.execute(step.action, inputs)
                    observation = await ready(self.surface, self.evidence)
                    if classify(observation):
                        return await business_outcome(self.surface, self.evidence, completed + 1)
                    await self.surface.verify(step.expect, inputs)
                    completed += 1
                    self.evidence.event("step_completed", step_id=step_id)
                step_id = "success-checkpoint"
                await self.surface.verify(artifact.success_checkpoint, inputs)
                self.evidence.event("checkpoint_verified", verified=True)
                outputs = {}
                for name, spec in artifact.outputs.items():
                    text = await self.surface.read(spec.target)
                    if spec.type == "decimal":
                        try:
                            number = Decimal(text)
                            if not number.is_finite():
                                raise InvalidOperation
                        except InvalidOperation:
                            raise FlowError(
                                "OUTPUT_INVALID", "decimal output", "invalid extracted output"
                            ) from None
                    outputs[name] = text
                self.evidence.event("outputs_extracted", outputs=outputs)
                await final_screenshot(self.surface, self.evidence.directory)
                return self.evidence.finish(
                    Result(
                        status="success",
                        run_id=self.evidence.run_id,
                        capability_id=artifact.id,
                        capability_version=artifact.version,
                        steps_completed=completed,
                        outputs=outputs,
                    )
                )
        except TimeoutError:
            return await failed(
                self.surface,
                self.evidence,
                FlowError("RUN_TIMEOUT", "bounded run", "run deadline reached"),
                step_id,
                completed,
            )
        except FlowError as error:
            return await failed(self.surface, self.evidence, error, step_id, completed)
        except Exception as error:
            return await failed(
                self.surface,
                self.evidence,
                FlowError("RUNTIME_ERROR", "valid UI action", type(error).__name__),
                step_id,
                completed,
            )
