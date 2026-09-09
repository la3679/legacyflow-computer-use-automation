import pytest

from legacyflow.models.contracts import Action, FlowError, Strategy, Target
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/members",
        "http://127.0.0.1:8000/accounts/create",
        "http://127.0.0.1:8000/members/../accounts/create",
    ],
)
def test_allowlist_rejects_unapproved_destinations(url: str) -> None:
    with pytest.raises(FlowError):
        Policy().authorize_url(url)


def test_risk_checked_against_actual_control() -> None:
    action = Action(kind="click", target=Target(strategies=[Strategy(kind="text", value="Submit")]))
    with pytest.raises(FlowError, match="HUMAN_APPROVAL_REQUIRED"):
        Policy().authorize(action, "http://127.0.0.1:8000/accounts/review", "Create Account")
    with pytest.raises(FlowError, match="ACTION_BLOCKED"):
        Policy(allowed_actions=[]).authorize(action, "http://127.0.0.1:8000/members")


def test_redaction_before_serialization() -> None:
    cleaned = Redactor(["12345"]).clean(
        {"member_id": "12345", "message": "Lookup 12345", "nested": [{"Authorization": "secret"}]}
    )
    assert "12345" not in str(cleaned)
    assert "secret" not in str(cleaned)
