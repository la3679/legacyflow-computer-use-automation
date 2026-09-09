from fastapi.testclient import TestClient

from legacyflow.demo.app import app

client = TestClient(app)


def test_review_and_business_outcome() -> None:
    assert "Member Details" in client.post("/members/search", data={"member_id": "12345"}).text
    assert "Member Not Found" in client.post("/members/search", data={"member_id": "99999"}).text
    assert "Permission Denied" in client.post("/members/search", data={"member_id": "40300"}).text
    response = client.post(
        "/accounts/review",
        data={"member_id": "23456", "account_type": "Savings", "initial_deposit": "250"},
    )
    assert "Casey Example" in response.text
    assert "250.00" in response.text
    assert "no account has been created" in response.text


def test_invalid_amount_and_deterministic_scenarios() -> None:
    for amount in ["NaN", "Infinity", "-1", "1.001", "bad"]:
        response = client.post(
            "/accounts/review",
            data={"member_id": "12345", "account_type": "Savings", "initial_deposit": amount},
        )
        assert "Enter a positive deposit" in response.text
    for scenario, message in [
        ("notice", "Known System Notice"),
        ("handoff", "Supervisor Confirmation"),
        ("expired", "Session Expired"),
    ]:
        assert (
            message
            in client.post(
                "/members/search", data={"member_id": "12345", "scenario": scenario}
            ).text
        )
