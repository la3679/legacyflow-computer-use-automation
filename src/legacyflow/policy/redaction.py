import re
from collections.abc import Mapping
from typing import Any

MASK = "[REDACTED]"
SENSITIVE = re.compile(r"key|authorization|cookie|token|password|credential|member_id", re.I)
SECRET = re.compile(r"sk-[A-Za-z0-9_-]+|Bearer\s+[^\s\"']+", re.I)


class Redactor:
    def __init__(self, secrets: list[str] | None = None) -> None:
        self.secrets = sorted((v for v in secrets or [] if v), key=len, reverse=True)

    def clean(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(k): MASK if SENSITIVE.search(str(k)) else self.clean(v)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, MASK)
            return SECRET.sub(MASK, value)
        return value
