"""Nonsecret configuration. API credentials are loaded only by discovery."""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field


class Settings(BaseModel):
    base_url: str = "http://127.0.0.1:8000"
    operator_url: str = "http://127.0.0.1:8010"
    headless: bool = False
    model: str = "gpt-5.6-terra"
    max_steps: int = Field(default=24, ge=1, le=100)
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    action_timeout_ms: int = Field(default=5000, ge=100, le=30000)

    @classmethod
    def load(cls, path: Path = Path(".env")) -> "Settings":
        values = {**dotenv_values(path, encoding="utf-8-sig"), **os.environ}
        return cls(
            base_url=values.get("LEGACYFLOW_BASE_URL") or "http://127.0.0.1:8000",
            operator_url=values.get("LEGACYFLOW_OPERATOR_URL") or "http://127.0.0.1:8010",
            headless=str(values.get("LEGACYFLOW_HEADLESS", "false")).lower() == "true",
            model=values.get("OPENAI_MODEL") or "gpt-5.6-terra",
        )
