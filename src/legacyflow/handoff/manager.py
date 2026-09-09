import asyncio
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from legacyflow.evidence.logger import Evidence
from legacyflow.handoff.state import TRANSITIONS, Intervention, RunState
from legacyflow.models.contracts import FlowError, Observation
from legacyflow.surfaces.browser import BrowserSurface

HUMAN_EVENTS = """() => {
 if (window.legacyflowRecorder) return;
 window.legacyflowRecorder = true;
 for (const kind of ['click','input','change']) document.addEventListener(kind, e => {
   const el=e.target;
   const label=el.getAttribute?.('aria-label') || el.labels?.[0]?.textContent?.trim() || '';
   const target = kind==='click' && ['BUTTON','A'].includes(el.tagName) ?
     el.textContent.trim().slice(0,80) : label.slice(0,80);
   window.legacyflowHumanEvent({kind, target, tag:el.tagName});
 }, true);
}"""

OPERATOR_HTML = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LegacyFlow Operator</title><style>
body{font:16px/1.5 Arial;background:#e8ecf1;color:#172b46;margin:32px;max-width:900px}
main{background:white;padding:24px;border:1px solid #8795a8}button{padding:12px 20px;
font:inherit;margin:8px;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}
img{max-width:100%;border:1px solid #8795a8}:focus-visible{outline:3px solid #a16207}
</style><main><h1>LegacyFlow Operator Console</h1><p>Operate the paused headed browser.
Resume verifies the same session and expected screen. All data is synthetic.</p>
<pre id="status" aria-live="polite">Waiting for a run...</pre>
<button onclick="act('take')">Take Control</button>
<button onclick="act('resume')">Resume Automation</button>
<button onclick="act('abort')">Abort Run</button><p id="message" role="alert"></p>
<img id="shot" alt="Paused application screenshot" hidden></main><script>
async function refresh(){const r=await fetch('/status');const s=await r.json();
document.querySelector('#status').textContent=JSON.stringify(s,null,2);
if(s.id){const i=document.querySelector('#shot');i.hidden=false;i.src='/screenshot?id='+s.id}}
async function act(a){const r=await fetch('/'+a,{method:'POST'});
document.querySelector('#message').textContent=r.ok?'Action accepted':(await r.json()).detail;
await refresh()} setInterval(refresh,1500);refresh();</script></html>"""


class HandoffManager:
    def __init__(
        self,
        surface: BrowserSurface,
        evidence: Evidence,
        operator_origin: str,
        timeout: float = 120,
        actor: str = "human",
    ) -> None:
        self.surface, self.evidence, self.operator_origin = surface, evidence, operator_origin
        self.timeout, self.actor = timeout, actor
        self.state = RunState.RUNNING
        self.intervention: Intervention | None = None
        self.signal = asyncio.Event()
        self.step_id = "unknown"
        self.app = self._app()

    async def install_recorder(self) -> None:
        async def record(_source: Any, data: dict[str, str]) -> None:
            if self.state == RunState.HUMAN_CONTROLLED:
                self.evidence.event(
                    "human_action",
                    actor=self.actor,
                    kind=data.get("kind"),
                    target=data.get("target"),
                    tag=data.get("tag"),
                    session_id=self.surface.session_id,
                )

        await self.surface.context.expose_binding("legacyflowHumanEvent", record)
        await self.surface.context.add_init_script(f"({HUMAN_EVENTS})();")
        await self.surface.page.evaluate(HUMAN_EVENTS)
        self.surface.page.on("framenavigated", self._navigation)

    def _navigation(self, _frame: Any) -> None:
        if self.state == RunState.HUMAN_CONTROLLED:
            self.evidence.event(
                "human_action",
                actor=self.actor,
                kind="navigation",
                session_id=self.surface.session_id,
            )

    def transition(self, state: RunState) -> None:
        if state not in TRANSITIONS[self.state]:
            raise ValueError("Invalid control transition")
        self.state = state
        if self.intervention:
            self.intervention.state = state
        self.evidence.event("control_transition", state=state, session_id=self.surface.session_id)

    async def request(self, observation: Observation) -> None:
        if self.surface.settings.headless:
            raise FlowError(
                "HEADED_BROWSER_REQUIRED", "headed browser", "headless handoff disabled"
            )
        original_session = self.surface.session_id
        await self.surface.screenshot(self.evidence.directory / "before-handoff.png")
        self.transition(RunState.WAITING_FOR_HUMAN)
        self.surface.owner = "human"
        self.intervention = Intervention(
            id=uuid4().hex,
            run_id=self.evidence.run_id,
            session_id=original_session,
            capability="open-savings-subaccount",
            step_id=self.step_id,
            reason=observation.messages[0]
            if observation.messages
            else "Automation requires assistance",
            expected_heading=observation.heading,
            screenshot="before-handoff.png",
            owner="human",
            state=self.state,
        )
        self.signal.clear()
        self.evidence.write("intervention.json", self.intervention.model_dump())
        self.evidence.event("intervention_requested", intervention=self.intervention.model_dump())
        self.evidence.event("control_transferred", owner="human", session_id=original_session)
        try:
            await asyncio.wait_for(self.signal.wait(), timeout=self.timeout)
        except TimeoutError:
            self.transition(RunState.ABORTED)
            raise FlowError(
                "HANDOFF_TIMEOUT", "operator decision", "intervention deadline reached"
            ) from None
        if self.state == RunState.ABORTED:
            raise FlowError("OPERATOR_ABORTED", "operator resume", "operator aborted run")
        self.surface.owner = "automation"
        current = await self.surface.observe()
        if (
            self.surface.session_id != original_session
            or current.heading != observation.heading
            or current.messages
        ):
            self.transition(RunState.ABORTED)
            raise FlowError(
                "RESUME_STATE_INVALID", observation.heading, "resume seam not satisfied"
            )
        self.transition(RunState.RUNNING)
        self.intervention.owner = "automation"
        self.evidence.event("automation_resumed", session_id=original_session, revalidated=True)
        await self.surface.screenshot(self.evidence.directory / "after-resume.png")

    def _app(self) -> FastAPI:
        app = FastAPI(title="LegacyFlow Operator")

        @app.middleware("http")
        async def local_only(request: Request, call_next: Any) -> Any:
            from starlette.responses import JSONResponse

            if request.headers.get("host") != self.operator_origin.split("://", 1)[1]:
                return JSONResponse({"detail": "Host not allowed"}, status_code=403)
            if request.method == "POST" and request.headers.get("origin") != self.operator_origin:
                return JSONResponse(
                    {"detail": "Same-origin operator request required"}, status_code=403
                )
            return await call_next(request)

        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            return OPERATOR_HTML

        @app.get("/status")
        async def status() -> dict[str, Any]:
            if self.intervention:
                return self.evidence.redactor.clean(self.intervention.model_dump())  # type: ignore[no-any-return]
            return {"state": self.state}

        @app.get("/screenshot")
        async def screenshot() -> FileResponse:
            path = self.evidence.directory / "before-handoff.png"
            if not path.exists():
                raise HTTPException(404, "No intervention screenshot")
            return FileResponse(path)

        @app.post("/{action}")
        async def control(action: str) -> dict[str, str]:
            states = {
                "take": RunState.HUMAN_CONTROLLED,
                "resume": RunState.RESUMING,
                "abort": RunState.ABORTED,
            }
            if action not in states:
                raise HTTPException(404, "Unknown operator action")
            try:
                self.transition(states[action])
            except ValueError:
                raise HTTPException(409, "Action unavailable in current control state") from None
            if action in {"resume", "abort"}:
                self.signal.set()
            return {"state": self.state}

        return app
