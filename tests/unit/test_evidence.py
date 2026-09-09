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


def test_free_text_credentials_are_redacted_before_persistence(tmp_path):
    evidence = Evidence(tmp_path, "test", Redactor())
    samples = [
        "Authorization: Basic c3ludGhldGljOm9ubHk=",
        "Cookie: session=synthetic-session; other=synthetic-other",
        "password=synthetic-password&member_id=56789",
        'api_key="synthetic-key"',
        "session_token=synthetic-session",
        "Bearer synthetic-bearer",
        "sk-synthetic-test-only",
    ]
    evidence.event("test", messages=samples)
    evidence.write("sample.json", {"messages": samples})
    for name in ["run.jsonl", "sample.json"]:
        text = (evidence.directory / name).read_text()
        assert "synthetic-" not in text
        assert "56789" not in text
        assert "c3ludGhldGljOm9ubHk=" not in text
