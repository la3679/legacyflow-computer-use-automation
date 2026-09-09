import asyncio
from pathlib import Path

import httpx
import pytest

from legacyflow.config import Settings
from legacyflow.evidence.logger import Evidence
from legacyflow.handoff.manager import HandoffManager
from legacyflow.handoff.state import RunState
from legacyflow.models.contracts import Action, FlowError, Value
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor
from legacyflow.surfaces.browser import BrowserSurface


@pytest.mark.parametrize("choice", ["resume", "abort", "invalid"])
async def test_same_session_handoff(base_url: str, tmp_path: Path, choice: str) -> None:
    evidence = Evidence(tmp_path, "test-handoff", Redactor(["12345"]))
    # Headed on the local desktop; CI runs under Xvfb.
    async with BrowserSurface(
        Settings(base_url=base_url, headless=False), Policy(allowed_origins=[base_url]), evidence
    ) as surface:
        manager = HandoffManager(surface, evidence, "http://127.0.0.1:8010", actor="test_operator")
        await manager.install_recorder()
        await surface.execute(
            Action(
                kind="navigate", value=Value(source="literal", value="/members?scenario=handoff")
            ),
            {},
        )
        await surface.page.get_by_label("Member ID").fill("12345")
        await surface.page.get_by_role("button", name="Search", exact=True).click()
        observation = await surface.observe()
        context, page, session = surface.context, surface.page, surface.session_id
        task = asyncio.create_task(manager.request(observation))
        async with asyncio.timeout(5):
            while manager.state != RunState.WAITING_FOR_HUMAN:
                await asyncio.sleep(0.01)
        assert surface.owner == "human"
        with pytest.raises(FlowError, match="CONTROL_NOT_OWNED"):
            await surface.observe()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app), base_url=manager.operator_origin
        ) as client:
            assert (await client.post("/resume")).status_code == 403
            client.headers["Origin"] = manager.operator_origin
            assert (await client.post("/resume")).status_code == 409
            assert (await client.post("/take")).status_code == 200
            if choice != "abort":
                await surface.page.get_by_role("button", name="Confirm Review").click()
            if choice == "invalid":
                await surface.page.goto(base_url + "/members")
            assert (
                await client.post("/abort" if choice == "abort" else "/resume")
            ).status_code == 200
        if choice == "resume":
            await task
            assert surface.owner == "automation"
            assert manager.state == RunState.RUNNING
            assert (
                surface.context is context
                and surface.page is page
                and surface.session_id == session
            )
            assert (await surface.observe()).messages == []
            assert "test_operator" in (evidence.directory / "run.jsonl").read_text()
        else:
            with pytest.raises(
                FlowError, match="OPERATOR_ABORTED" if choice == "abort" else "RESUME_STATE_INVALID"
            ):
                await task
