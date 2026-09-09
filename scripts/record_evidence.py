"""Record offline replay demonstrations against a running loopback demo.

The handoff actor is explicitly automated; this does not claim a human operated it.
Run from the repository root after starting `legacyflow demo serve`.
"""

import asyncio
from pathlib import Path

import uvicorn

from legacyflow.config import Settings
from legacyflow.evidence.logger import Evidence
from legacyflow.handoff.manager import HandoffManager
from legacyflow.handoff.state import RunState
from legacyflow.models.contracts import Action, Artifact, Step, Strategy, Target
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor
from legacyflow.replay.engine import ReplayEngine
from legacyflow.surfaces.browser import BrowserSurface


async def demonstrate(scenario: str, expected: str) -> Path:
    artifact = Artifact.model_validate_json(
        Path("evidence/capabilities/open-savings-subaccount.v1.json").read_text()
    )
    settings = Settings(headless=scenario != "handoff")
    evidence = Evidence(Path("runs"), "replay", Redactor(["23456"]))
    evidence.event("demonstration_provenance", actor="automated_demonstrator", live_api=False)
    if scenario == "policy":
        artifact.steps.append(
            Step(
                id="attempt-create-account",
                action=Action(
                    kind="click",
                    target=Target(strategies=[Strategy(kind="text", value="Create Account")]),
                ),
                expect=artifact.success_checkpoint,
            )
        )
    async with BrowserSurface(settings, Policy(), evidence) as surface:
        manager = None
        server = None
        server_task = None
        operator_task = None
        if scenario == "handoff":
            manager = HandoffManager(
                surface, evidence, "http://127.0.0.1:8011", actor="automated_demonstrator"
            )
            await manager.install_recorder()
            server = uvicorn.Server(
                uvicorn.Config(
                    manager.app, host="127.0.0.1", port=8011, access_log=False, log_level="warning"
                )
            )
            server_task = asyncio.create_task(server.serve())
            async with asyncio.timeout(10):
                while not server.started:
                    await asyncio.sleep(0.05)

            async def operate() -> None:
                assert manager is not None and surface.browser is not None
                original_context, original_page = surface.context, surface.page
                async with asyncio.timeout(30):
                    while manager.state != RunState.WAITING_FOR_HUMAN:
                        await asyncio.sleep(0.02)
                    console = await surface.browser.new_page()
                    try:
                        await console.goto(manager.operator_origin)
                        await console.get_by_role("button", name="Take Control", exact=True).click()
                        while manager.state != RunState.HUMAN_CONTROLLED:
                            await asyncio.sleep(0.02)
                        await console.screenshot(
                            path=str(evidence.directory / "operator-console.png")
                        )
                        await original_page.get_by_role("button", name="Confirm Review").click()
                        await console.get_by_role("button", name="Resume Automation").click()
                        while manager.state != RunState.RUNNING:
                            await asyncio.sleep(0.02)
                        assert surface.context is original_context and surface.page is original_page
                        evidence.event(
                            "same_session_verified",
                            page_identity=True,
                            context_identity=True,
                            session_id=surface.session_id,
                            actor="automated_demonstrator",
                        )
                    finally:
                        await console.close()

            operator_task = asyncio.create_task(operate())
        try:
            result = await ReplayEngine(surface, evidence, settings, manager).run(
                artifact,
                {"member_id": "23456", "initial_deposit": "250"},
                "normal" if scenario == "policy" else scenario,
            )
            if operator_task:
                await operator_task
            actual = result.error.code if result.error else result.status
            assert actual == expected, (scenario, actual)
        finally:
            if operator_task and not operator_task.done():
                operator_task.cancel()
                await asyncio.gather(operator_task, return_exceptions=True)
            if server:
                server.should_exit = True
            if server_task:
                await server_task
    print(f"{scenario}: {actual}; evidence: {evidence.directory}")
    return evidence.directory


async def main() -> None:
    for scenario, expected in [
        ("handoff", "success"),
        ("notice", "success"),
        ("permission", "PERMISSION_DENIED"),
        ("policy", "HUMAN_APPROVAL_REQUIRED"),
    ]:
        await demonstrate(scenario, expected)


if __name__ == "__main__":
    asyncio.run(main())
