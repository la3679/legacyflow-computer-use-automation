from legacyflow.models.contracts import (
    Action,
    Artifact,
    Condition,
    FlowError,
    InputSpec,
    Observation,
    OutputSpec,
    Step,
    Value,
)


class Recorder:
    """Compile executed, verified actions; never serialize a model transcript."""

    def __init__(self) -> None:
        self.steps: list[Step] = []

    def condition(self, action: Action, observation: Observation) -> Condition:
        if action.kind in {"type", "select"}:
            assert action.value is not None
            return Condition(kind="field", target=action.target, value=action.value)
        return Condition(kind="heading", value=Value(source="literal", value=observation.heading))

    def record(self, action: Action, condition: Condition) -> None:
        self.steps.append(
            Step(
                id=f"step-{len(self.steps) + 1:02d}-{action.kind}",
                action=action,
                expect=condition,
                risk="read" if action.kind == "read" else "reversible",
            )
        )

    def compile(
        self, observation: Observation, run_id: str, sensitive_values: list[str] | None = None
    ) -> Artifact:
        if observation.heading != "Review New Account":
            raise FlowError("GOAL_NOT_REACHED", "Review New Account", observation.heading)
        outputs = {}
        for name, label, kind in [
            ("member_name", "Member name", "string"),
            ("review_status", "Review status", "string"),
            ("initial_deposit", "Initial deposit", "decimal"),
        ]:
            matches = [c for c in observation.controls if c.name == label]
            if len(matches) != 1:
                raise FlowError("OUTPUT_NOT_FOUND", label, "no unique output")
            outputs[name] = OutputSpec.model_validate({"type": kind, "target": matches[0].target})
        artifact = Artifact(
            inputs={
                "member_id": InputSpec(type="string", sensitive=True),
                "initial_deposit": InputSpec(type="decimal"),
            },
            outputs=outputs,
            steps=self.steps,
            success_checkpoint=Condition(
                kind="heading", value=Value(source="literal", value="Review New Account")
            ),
            discovery_run_id=run_id,
        )
        serialized = artifact.model_dump_json()
        if any(value and value in serialized for value in sensitive_values or []):
            raise FlowError(
                "ARTIFACT_SENSITIVE_VALUE",
                "parameterized artifact",
                "sensitive invocation value found in compiled artifact",
            )
        return artifact
