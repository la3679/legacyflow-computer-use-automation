from pathlib import Path

from legacyflow.evidence.logger import Evidence
from legacyflow.policy.redaction import Redactor


def test_event_and_file_share_redaction_boundary(tmp_path: Path) -> None:
    evidence = Evidence(tmp_path, "test", Redactor(["private-value"]))
    evidence.event("test", detail="private-value", password="hidden")
    evidence.write("result.json", {"nested": {"token": "hidden"}})
    for file in evidence.directory.iterdir():
        assert "private-value" not in file.read_text()
        assert "hidden" not in file.read_text()
