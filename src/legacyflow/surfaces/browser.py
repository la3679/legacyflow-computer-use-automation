import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4

from playwright.async_api import (
    Browser,
    BrowserContext,
    Frame,
    Locator,
    Page,
    Playwright,
    Route,
    async_playwright,
    expect,
)

from legacyflow.config import Settings
from legacyflow.evidence.logger import Evidence
from legacyflow.models.contracts import (
    Action,
    Condition,
    Control,
    FlowError,
    Observation,
    Strategy,
    Target,
)
from legacyflow.policy.engine import Policy

# Fixed, reviewed DOM observation code. The model never supplies JavaScript or selectors.
OBSERVE = """() => {
 const visible = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
 const controls = [...document.querySelectorAll('input:not([type=hidden]),select,button,a,output')]
 .filter(visible).map(e => {
  const role = e.tagName==='BUTTON' ? 'button' : e.tagName==='SELECT' ? 'combobox' :
    e.tagName==='A' ? 'link' : e.tagName==='OUTPUT' ? 'status' : 'textbox';
  const label = e.labels?.[0]?.textContent?.trim() || '';
  const name = e.getAttribute('aria-label') || label || e.textContent.trim();
  return {name: name.slice(0,200), role, label, attribute:e.getAttribute('name'),
    state: ['INPUT','SELECT'].includes(e.tagName) ? (e.value ? 'filled':'empty'):'not_applicable'};
 });
 return {heading:document.querySelector('h1')?.textContent.trim() || '', controls,
  application:document.querySelector('meta[name=application-name]')?.content || '',
  app_version:document.querySelector('meta[name=application-version]')?.content || '',
  messages:[...document.querySelectorAll('dialog[open], [role=alert]')]
    .filter(visible).map(e=>(e.querySelector('h2')?.textContent || e.textContent)
      .trim().slice(0,200))};
}"""


class BrowserSurface:
    def __init__(self, settings: Settings, policy: Policy, evidence: Evidence) -> None:
        self.settings, self.policy, self.evidence = settings, policy, evidence
        self.owner = "automation"
        self.session_id = uuid4().hex
        self.runtime: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext
        self.page: Page
        self.blocked_request = False
        self.recent_read: str | None = None

    async def __aenter__(self) -> "BrowserSurface":
        self.runtime = await async_playwright().start()
        self.browser = await self.runtime.chromium.launch(headless=self.settings.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1200, "height": 850}, service_workers="block", accept_downloads=False
        )
        await self.context.route("**/*", self._route)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.settings.action_timeout_ms)
        self.evidence.event("session_started", session_id=self.session_id)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self.browser:
            await self.browser.close()
        if self.runtime:
            await self.runtime.stop()

    async def _route(self, route: Route) -> None:
        try:
            self.policy.authorize_url(route.request.url, resource=True)
        except FlowError:
            self.blocked_request = True
            self.evidence.event("policy_decision", decision="block", reason="network destination")
            await route.abort()
            return
        await route.continue_()

    def _owned(self) -> None:
        if self.owner != "automation":
            raise FlowError("CONTROL_NOT_OWNED", "automation ownership", "human owns session")

    async def observe(self) -> Observation:
        self._owned()
        self.policy.authorize_url(self.page.url)
        if self.blocked_request:
            raise FlowError("NETWORK_BLOCKED", "allowed requests", "disallowed request blocked")
        raw = await self.page.evaluate(OBSERVE)
        controls = []
        for index, item in enumerate(raw.pop("controls")):
            if not item["name"]:
                continue
            strategies = [Strategy(kind="role", role=item["role"], value=item["name"])]
            if item["label"]:
                strategies.append(Strategy(kind="label", value=item["label"]))
            elif item["role"] in {"button", "link"}:
                strategies.append(Strategy(kind="text", value=item["name"]))
            if item["attribute"]:
                strategies.append(Strategy(kind="attribute", value=item["attribute"]))
            controls.append(
                Control(
                    id=f"c{index}",
                    name=item["name"],
                    role=item["role"],
                    target=Target(strategies=strategies),
                    value_state=item["state"],
                )
            )
        observation = Observation(
            url=self.page.url, controls=controls, recent_read=self.recent_read, **raw
        )
        self.evidence.event("observation_captured", observation=observation.model_dump())
        return observation

    async def resolve(self, target: Target) -> Locator:
        self._owned()
        scope: Any = self.page
        if target.frame:
            frames: list[Frame] = [f for f in self.page.frames if f.name == target.frame]
            if len(frames) != 1:
                raise FlowError("FRAME_NOT_FOUND", "unique named frame", "no unique frame")
            scope = frames[0]
        if target.region:
            scope = scope.get_by_role("region", name=target.region, exact=True)
        for strategy in target.strategies:
            if strategy.kind == "role":
                locator = scope.get_by_role(strategy.role, name=strategy.value, exact=True)
            elif strategy.kind == "label":
                locator = scope.get_by_label(strategy.value, exact=True)
            elif strategy.kind == "text":
                locator = scope.get_by_text(strategy.value, exact=True)
            else:
                locator = scope.locator(f"[name={json.dumps(strategy.value)}]")
            count = await locator.count()
            if count > 1:
                raise FlowError("TARGET_AMBIGUOUS", "unique target", "multiple matching controls")
            if count == 1 and await locator.is_visible():
                self.evidence.event("target_resolved", strategy=strategy.model_dump())
                return locator  # type: ignore[no-any-return]
        raise FlowError("TARGET_NOT_FOUND", "visible unique target", "no permitted locator matched")

    async def execute(self, action: Action, inputs: dict[str, str]) -> None:
        self._owned()
        current = (
            self.page.url if self.page.url != "about:blank" else self.settings.base_url + "/members"
        )
        self.policy.authorize(action, current)
        self.evidence.event("policy_decision", decision="allow", action=action.kind)
        self.evidence.event("action_started", action=action.kind)
        if action.kind == "navigate":
            assert action.value is not None
            destination = urljoin(self.settings.base_url, action.value.resolve(inputs))
            self.policy.authorize_url(destination)
            await self.page.goto(destination, wait_until="domcontentloaded")
        elif action.kind == "wait":
            await self.page.wait_for_load_state("domcontentloaded")
        else:
            assert action.target is not None
            locator = await self.resolve(action.target)
            name = await locator.get_attribute("aria-label") or await locator.inner_text()
            self.policy.authorize(action, self.page.url, name)
            if action.kind == "click":
                destination = await locator.evaluate(
                    "e => e.href || (e.type === 'submit' ? e.form?.action : '') || ''"
                )
                if destination:
                    self.policy.authorize_url(destination)
                await locator.click()
                await self.page.wait_for_load_state("domcontentloaded")
            elif action.kind == "type":
                assert action.value is not None
                await locator.fill(action.value.resolve(inputs))
            elif action.kind == "select":
                assert action.value is not None
                await locator.select_option(label=action.value.resolve(inputs))
            elif action.kind == "read":
                self.recent_read = (await locator.inner_text()).strip()[:250]
        self.evidence.event("action_completed", action=action.kind)

    async def verify(self, condition: Condition, inputs: dict[str, str]) -> None:
        self._owned()
        value = condition.value.resolve(inputs)
        try:
            if condition.kind == "heading":
                await expect(
                    self.page.get_by_role("heading", name=value, exact=True)
                ).to_be_visible(timeout=self.settings.action_timeout_ms)
            else:
                assert condition.target is not None
                locator = await self.resolve(condition.target)
                if condition.kind == "field":
                    await expect(locator).to_have_value(
                        value, timeout=self.settings.action_timeout_ms
                    )
                else:
                    await expect(locator).to_be_visible(timeout=self.settings.action_timeout_ms)
        except AssertionError:
            raise FlowError(
                "CHECKPOINT_FAILED", condition.kind, "expected condition not satisfied"
            ) from None
        self.evidence.event("postcondition_checked", kind=condition.kind, verified=True)

    async def read(self, target: Target) -> str:
        self.policy.authorize(Action(kind="read", target=target), self.page.url)
        return (await (await self.resolve(target)).inner_text()).strip()

    async def screenshot(self, path: Path) -> None:
        # Mask inputs during human ownership too. Synthetic output fields may remain visible.
        await self.page.screenshot(
            path=str(path), full_page=True, mask=[self.page.locator("input, textarea")]
        )
