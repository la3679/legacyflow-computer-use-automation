import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from legacyflow.models.contracts import Result
from legacyflow.policy.redaction import Redactor


class Evidence:
    def __init__(self, root: Path, mode: str, redactor: Redactor) -> None:
        self.run_id = uuid4().hex
        self.directory = root / self.run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.redactor = redactor
        self.mode = mode
        self.capability = ("open-savings-subaccount", "1.0.0")
        self.started = time.monotonic()
        self.write(
            "metadata.json",
            {"run_id": self.run_id, "mode": mode, "synthetic_data": True, "started_at": self.now()},
        )
        self.event("run_started")

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def write(self, name: str, value: Any) -> None:
        if Path(name).name != name:
            raise ValueError("Evidence name must be a basename")
        (self.directory / name).write_text(
            json.dumps(self.redactor.clean(value), indent=2) + "\n", encoding="utf-8"
        )

    def event(self, event: str, **data: Any) -> None:
        record = {
            "timestamp": self.now(),
            "run_id": self.run_id,
            "mode": self.mode,
            "event": event,
            "elapsed_ms": round((time.monotonic() - self.started) * 1000),
            **data,
        }
        with (self.directory / "run.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(self.redactor.clean(record)) + "\n")

    def finish(self, result: Result) -> Result:
        result.capability_id, result.capability_version = self.capability
        self.write("result.json", result.model_dump(mode="json"))
        self.event("run_completed", status=result.status)
        return result
