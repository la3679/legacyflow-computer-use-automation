import pytest
from typer import BadParameter
from typer.testing import CliRunner

from legacyflow.cli import app, parse_inputs


def test_cli_commands_and_input_validation() -> None:
    runner = CliRunner()
    for args in [
        ["--help"],
        ["discover", "--help"],
        ["replay", "--help"],
        ["demo", "serve", "--help"],
    ]:
        assert runner.invoke(app, args).exit_code == 0
    assert parse_inputs(["member_id=23456"]) == {"member_id": "23456"}
    with pytest.raises(BadParameter):
        parse_inputs(["member_id=1", "member_id=2"])
