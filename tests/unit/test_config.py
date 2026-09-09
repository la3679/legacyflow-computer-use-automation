from pathlib import Path

from legacyflow.config import Settings


def test_configuration_has_no_credential_field(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing")
    assert settings.base_url.startswith("http://127.0.0.1")
    assert "key" not in settings.model_dump_json()
