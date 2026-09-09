from unittest.mock import AsyncMock

import pytest

from legacyflow.discovery.planner import OpenAIPlanner
from legacyflow.models.contracts import FlowError, Observation


async def test_api_error_body_never_reaches_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-credential")
    planner = OpenAIPlanner("test")
    planner.client.responses.parse = AsyncMock(side_effect=RuntimeError("sensitive-response"))
    observation = Observation(
        url="http://127.0.0.1:8000/members",
        heading="Member Search",
        application="test",
        app_version="1.0",
        controls=[],
        messages=[],
    )
    with pytest.raises(FlowError) as exc:
        await planner.decide("test", observation, {}, [])
    assert str(exc.value) == "PLANNER_ERROR"
    assert "sensitive-response" not in exc.value.observed
    await planner.close()
