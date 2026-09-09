import pytest
from pydantic import ValidationError

from legacyflow.models.contracts import Action, Decision, Result, Value


def test_action_validation_and_parameter_resolution() -> None:
    with pytest.raises(ValidationError):
        Action(kind="type")
    assert Value(source="input", value="member_id").resolve({"member_id": "23456"}) == "23456"
    with pytest.raises(KeyError):
        Value(source="input", value="missing").resolve({})


def test_model_cannot_produce_code_or_untyped_outcomes() -> None:
    with pytest.raises(ValidationError):
        Decision.model_validate({"action": "eval", "code": "alert(1)"})
    with pytest.raises(ValidationError):
        Result(status="failure", run_id="test")
    assert Result(status="business_outcome", run_id="test", outcome="member_not_found")
