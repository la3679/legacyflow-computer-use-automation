import asyncio
import json
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

import typer
import uvicorn

from legacyflow.config import Settings
from legacyflow.evidence.logger import Evidence
from legacyflow.handoff.manager import HandoffManager
from legacyflow.models.contracts import Artifact, FlowError, Result
from legacyflow.policy.engine import Policy
from legacyflow.policy.redaction import Redactor
from legacyflow.replay.engine import ReplayEngine
from legacyflow.surfaces.browser import BrowserSurface

app = typer.Typer(help="Discover, save, and deterministically replay UI capabilities.")
demo = typer.Typer(help="Run the synthetic legacy application.")
app.add_typer(demo, name="demo")


@demo.command()
def serve(port: int = 8000) -> None:
    """Serve fictional member records on loopback only."""
    uvicorn.run("legacyflow.demo.app:app", host="127.0.0.1", port=port, access_log=False)


def parse_inputs(items: list[str]) -> dict[str, str]:
    values = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter("Inputs must use name=value")
        name, value = item.split("=", 1)
        if name in values:
            raise typer.BadParameter("Duplicate input parameter")
        values[name] = value
    return values


async def run_ui(
    mode: str,
    values: dict[str, str],
    artifact_path: Path,
    goal: str,
    target: str,
    scenario: str,
    root: Path,
    policy_path: Path | None,
    headless: bool | None,
    operator: bool,
) -> Result:
    settings = Settings.load()
    if headless is not None:
        settings.headless = headless
    policy = Policy.load(policy_path)
    artifact = (
        Artifact.model_validate_json(artifact_path.read_text(encoding="utf-8"))
        if mode == "replay"
        else None
    )
    sensitive_names = {"member_id"}
    if artifact:
        sensitive_names.update(name for name, spec in artifact.inputs.items() if spec.sensitive)
    redactor = Redactor([values.get(name, "") for name in sensitive_names])
    evidence = Evidence(root, mode, redactor)
    async with BrowserSurface(settings, policy, evidence) as surface:
        manager = HandoffManager(surface, evidence, settings.operator_url) if operator else None
        server: uvicorn.Server | None = None
        server_task: asyncio.Task[None] | None = None
        try:
            if manager:
                parsed = urlsplit(settings.operator_url)
                if parsed.hostname not in {"127.0.0.1", "localhost"}:
                    raise ValueError("Operator URL must be loopback")
                await manager.install_recorder()
                server = uvicorn.Server(
                    uvicorn.Config(
                        manager.app,
                        host="127.0.0.1",
                        port=parsed.port or 8010,
                        access_log=False,
                        log_level="warning",
                    )
                )
                server_task = asyncio.create_task(server.serve())
                async with asyncio.timeout(10):
                    while not server.started:
                        await asyncio.sleep(0.05)
                typer.echo(f"Operator console: {settings.operator_url}")
            if mode == "discovery":
                # Lazy imports keep replay usable without the discovery extra or credentials.
                from legacyflow.discovery.planner import OpenAIPlanner
                from legacyflow.discovery.runner import DiscoveryRunner

                planner = OpenAIPlanner(settings.model)
                evidence.event(
                    "planner_configured", provider="OpenAI", model=settings.model, live_api=True
                )
                try:
                    result = await DiscoveryRunner(
                        surface, planner, evidence, settings, manager
                    ).run(goal, target, values, artifact_path)
                finally:
                    await planner.close()
            else:
                assert artifact is not None
                result = await ReplayEngine(surface, evidence, settings, manager).run(
                    artifact, values, scenario
                )
        finally:
            if server:
                server.should_exit = True
            if server_task:
                await server_task
    typer.echo(json.dumps(redactor.clean(result.model_dump(mode="json")), indent=2))
    typer.echo(f"Evidence: {evidence.directory}")
    return result


def launch(
    mode: str,
    values: list[str],
    artifact: Path,
    goal: str = "",
    target: str = "/members",
    scenario: str = "normal",
    root: Path = Path("runs"),
    policy: Path | None = None,
    headless: bool | None = None,
    operator: bool = False,
) -> None:
    try:
        result = asyncio.run(
            run_ui(
                mode,
                parse_inputs(values),
                artifact,
                goal,
                target,
                scenario,
                root,
                policy,
                headless,
                operator,
            )
        )
    except (FlowError, ValueError, OSError) as error:
        typer.echo(f"Run could not start: {type(error).__name__}", err=True)
        raise typer.Exit(1) from None
    if result.status in {"failure", "aborted"}:
        raise typer.Exit(1)


@app.command()
def discover(
    goal: Annotated[str, typer.Option(help="Natural-language goal")],
    inputs: Annotated[list[str], typer.Option("--input")],
    target: str = "/members",
    artifact: Path = Path("artifacts/open-savings-subaccount.v1.json"),
    root: Path = Path("runs"),
    policy: Path | None = None,
    headless: Annotated[bool | None, typer.Option("--headless/--headed")] = None,
    operator: bool = False,
) -> None:
    """Use the real OpenAI planner against the live UI, then save a capability."""
    launch(
        "discovery",
        inputs,
        artifact,
        goal,
        target,
        root=root,
        policy=policy,
        headless=headless,
        operator=operator,
    )


@app.command()
def replay(
    artifact: Path,
    inputs: Annotated[list[str], typer.Option("--input")],
    scenario: str = "normal",
    root: Path = Path("runs"),
    policy: Path | None = None,
    headless: Annotated[bool | None, typer.Option("--headless/--headed")] = None,
    operator: bool = False,
) -> None:
    """Replay a saved capability without any model or API key."""
    launch(
        "replay",
        inputs,
        artifact,
        scenario=scenario,
        root=root,
        policy=policy,
        headless=headless,
        operator=operator,
    )


@app.command()
def version() -> None:
    """Print the application version."""
    typer.echo("LegacyFlow 0.1.0")


if __name__ == "__main__":
    app()
