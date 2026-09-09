from pathlib import Path

import pytest

from legacyflow.config import Settings
from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import Action, FlowError, Strategy, Target, Value
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor
from legacyflow.surfaces.browser import BrowserSurface


async def test_real_browser_observation_fallback_and_ownership(
    base_url: str, tmp_path: Path
) -> None:
    evidence = Evidence(tmp_path, "test", Redactor())
    async with BrowserSurface(
        Settings(base_url=base_url, headless=True), Policy(allowed_origins=[base_url]), evidence
    ) as surface:
        await surface.execute(
            Action(kind="navigate", value=Value(source="literal", value="/members")), {}
        )
        observation = await surface.observe()
        assert observation.heading == "Member Search"
        target = Target(
            strategies=[
                Strategy(kind="text", value="Missing"),
                Strategy(kind="label", value="Member ID"),
            ]
        )
        assert await (await surface.resolve(target)).get_attribute("name") == "member_id"
        surface.owner = "human"
        with pytest.raises(FlowError, match="CONTROL_NOT_OWNED"):
            await surface.observe()


async def test_ambiguous_locator_fails_closed(base_url: str, tmp_path: Path) -> None:
    async with BrowserSurface(
        Settings(base_url=base_url, headless=True),
        Policy(allowed_origins=[base_url]),
        Evidence(tmp_path, "test", Redactor()),
    ) as surface:
        await surface.execute(
            Action(kind="navigate", value=Value(source="literal", value="/members")), {}
        )
        await surface.page.evaluate(
            "document.body.insertAdjacentHTML('beforeend','<button>Search</button>')"
        )
        with pytest.raises(FlowError, match="TARGET_AMBIGUOUS"):
            await surface.resolve(
                Target(strategies=[Strategy(kind="role", role="button", value="Search")])
            )
