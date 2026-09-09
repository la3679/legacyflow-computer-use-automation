from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import Field

from legacyflow.models.contracts import Action, Contract, FlowError


class Policy(Contract):
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:8000", "http://localhost:8000"]
    )
    allowed_routes: list[str] = Field(
        default_factory=lambda: [
            "/members",
            "/members/search",
            "/members/notice",
            "/accounts/new",
            "/accounts/review",
        ]
    )
    allowed_actions: list[str] = Field(
        default_factory=lambda: ["observe", "click", "type", "select", "read", "wait", "navigate"]
    )
    risky_names: list[str] = Field(default_factory=lambda: ["Create Account", "Confirm Review"])

    @classmethod
    def load(cls, path: Path | None = None) -> "Policy":
        return cls.model_validate(yaml.safe_load(path.read_text())) if path else cls()

    def authorize_url(self, url: str, resource: bool = False) -> None:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.username or parsed.password or origin not in self.allowed_origins:
            raise FlowError("ORIGIN_BLOCKED", "allowed origin", "origin not allowed")
        if parsed.path not in self.allowed_routes and not (
            resource and parsed.path.startswith("/static/")
        ):
            raise FlowError("ROUTE_BLOCKED", "allowed route", "route not allowed")

    def authorize(self, action: Action, url: str, actual_name: str = "") -> None:
        self.authorize_url(url)
        if action.kind not in self.allowed_actions:
            raise FlowError("ACTION_BLOCKED", "allowed action", "unsupported action")
        names = [actual_name]
        if action.target:
            names.extend(s.value for s in action.target.strategies)
        if action.kind in {"click", "type", "select"} and any(
            risk.casefold() in name.casefold() for name in names for risk in self.risky_names
        ):
            raise FlowError("HUMAN_APPROVAL_REQUIRED", "human approval", "risky action blocked")
