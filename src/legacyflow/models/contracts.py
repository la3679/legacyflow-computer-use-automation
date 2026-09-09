from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Strategy(Contract):
    kind: Literal["role", "label", "text", "attribute"]
    value: str = Field(min_length=1, max_length=200)
    role: Literal["button", "textbox", "combobox", "link", "heading", "status"] | None = None


class Target(Contract):
    strategies: list[Strategy] = Field(min_length=1, max_length=6)
    frame: str | None = None
    region: str | None = None


class Value(Contract):
    source: Literal["input", "literal"]
    value: str

    def resolve(self, inputs: dict[str, str]) -> str:
        return inputs[self.value] if self.source == "input" else self.value


class Condition(Contract):
    kind: Literal["heading", "field", "visible"]
    value: Value
    target: Target | None = None


class Action(Contract):
    kind: Literal["click", "type", "select", "read", "wait", "navigate"]
    target: Target | None = None
    value: Value | None = None

    @model_validator(mode="after")
    def action_shape(self) -> Self:
        if self.kind in {"click", "type", "select", "read"} and self.target is None:
            raise ValueError("Action requires target")
        if self.kind in {"type", "select", "navigate"} and self.value is None:
            raise ValueError("Action requires value")
        return self


class Step(Contract):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    action: Action
    expect: Condition
    risk: Literal["read", "reversible", "irreversible"] = "reversible"


class InputSpec(Contract):
    type: Literal["string", "decimal"]
    sensitive: bool = False
    required: bool = True


class OutputSpec(Contract):
    type: Literal["string", "decimal"]
    target: Target


class Compatibility(Contract):
    application: str = "legacyflow-demo"
    vendor_family: str = "legacyflow-demo-core"
    surface: Literal["web"] = "web"
    app_major: int = 1
    variant: str = "base"
    entry_point: str = "/members"


class Artifact(Contract):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(default="open-savings-subaccount", pattern=r"^[a-z0-9-]+$")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    name: str = "Open savings sub-account to review"
    description: str = "Prepare a savings sub-account without creating the account."
    target: Compatibility = Field(default_factory=Compatibility)
    inputs: dict[str, InputSpec]
    outputs: dict[str, OutputSpec]
    steps: list[Step] = Field(min_length=1, max_length=100)
    success_checkpoint: Condition
    discovery_run_id: str

    @model_validator(mode="after")
    def references(self) -> Self:
        if len({s.id for s in self.steps}) != len(self.steps):
            raise ValueError("Duplicate step IDs")
        values = [s.action.value for s in self.steps]
        values += [s.expect.value for s in self.steps] + [self.success_checkpoint.value]
        for value in values:
            if value and value.source == "input" and value.value not in self.inputs:
                raise ValueError("Undefined input reference")
        for step in self.steps:
            if step.action.kind == "type" and (
                step.action.value is None or step.action.value.source != "input"
            ):
                raise ValueError("Typed form values must be parameter references")
        return self

    def validate_inputs(self, values: dict[str, str]) -> dict[str, str]:
        if set(values) - set(self.inputs):
            raise ValueError("Unknown input parameter")
        result: dict[str, str] = {}
        for name, spec in self.inputs.items():
            raw = values.get(name, "")
            if spec.required and not raw:
                raise ValueError("Missing required input")
            if spec.type == "decimal":
                try:
                    amount = Decimal(raw)
                    if not amount.is_finite() or not 0 < amount <= 100000:
                        raise ValueError("Deposit out of range")
                    if amount != amount.quantize(Decimal("0.01")):
                        raise ValueError("Deposit must have at most two decimal places")
                    raw = format(amount, "f")
                except InvalidOperation:
                    raise ValueError("Invalid decimal input") from None
            elif len(raw) > 100 or not raw.isalnum():
                raise ValueError("Invalid identifier input")
            result[name] = raw
        return result


class Control(Contract):
    id: str
    name: str
    role: str
    target: Target
    value_state: Literal["empty", "filled", "not_applicable"]


class Observation(Contract):
    url: str
    heading: str
    application: str
    app_version: str
    controls: list[Control]
    messages: list[str]


class Decision(Contract):
    """Strict planner output; no code, selectors, or hidden reasoning."""

    action: Literal["click", "type", "select", "read", "wait", "navigate", "finish", "escalate"]
    control_id: str | None
    input_name: str | None
    literal: str | None
    rationale_summary: str = Field(max_length=250)


class Failure(Contract):
    code: str
    step_id: str
    expected: str
    observed: str
    evidence: str | None = None


class Result(Contract):
    status: Literal["success", "business_outcome", "failure", "aborted"]
    run_id: str
    capability_id: str = "open-savings-subaccount"
    capability_version: str = "1.0.0"
    steps_completed: int = 0
    outputs: dict[str, str] = Field(default_factory=dict)
    outcome: Literal["member_not_found"] | None = None
    error: Failure | None = None

    @model_validator(mode="after")
    def result_shape(self) -> Self:
        if (self.status == "failure") != (self.error is not None):
            raise ValueError("Failure requires error details exclusively")
        if (self.status == "business_outcome") != (self.outcome is not None):
            raise ValueError("Business outcome requires outcome exclusively")
        return self


class FlowError(Exception):
    def __init__(self, code: str, expected: str, observed: str) -> None:
        super().__init__(code)
        self.code, self.expected, self.observed = code, expected, observed
