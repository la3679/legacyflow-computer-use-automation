import pytest
from pydantic import ValidationError

from legacyflow.discovery.recorder import Recorder
from legacyflow.models.contracts import Action, Control, Observation, Strategy, Target, Value


def test_compiler_persists_references_and_validates_replay_inputs() -> None:
    recorder = Recorder()
    target = Target(strategies=[Strategy(kind="label", value="Member ID")])
    action = Action(kind="type", target=target, value=Value(source="input", value="member_id"))
    observation = Observation(
        url="http://127.0.0.1:8000/accounts/review",
        heading="Review New Account",
        application="legacyflow-demo",
        app_version="1.0.0",
        messages=[],
        controls=[
            Control(
                id=name,
                name=name,
                role="status",
                value_state="not_applicable",
                target=Target(strategies=[Strategy(kind="role", role="status", value=name)]),
            )
            for name in ["Member name", "Review status", "Initial deposit"]
        ],
    )
    recorder.record(action, recorder.condition(action, observation))
    artifact = recorder.compile(observation, "test-run")
    assert "12345" not in artifact.model_dump_json()
    assert artifact.steps[0].action.value == Value(source="input", value="member_id")
    assert artifact.validate_inputs({"member_id": "23456", "initial_deposit": "250"})
    for invalid in [
        {},
        {"member_id": "23456", "initial_deposit": "NaN"},
        {"member_id": "23456", "initial_deposit": "-1"},
    ]:
        with pytest.raises(ValueError):
            artifact.validate_inputs(invalid)
    raw = artifact.model_dump()
    raw["steps"][0]["action"]["value"] = {"source": "literal", "value": "12345"}
    with pytest.raises(ValidationError):
        type(artifact).model_validate(raw)
