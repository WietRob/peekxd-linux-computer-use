"""CLI tests for peekxd doctor commands."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from peekxd.cli import cli
from peekxd.core.doctor import CapabilityStatus, DoctorCheck, DoctorResult


def _result(*checks):
    return DoctorResult(checks=list(checks))


def _check(capability="screenshot", status=CapabilityStatus.OK, provider="test", smoke=False):
    return DoctorCheck(
        capability=capability,
        status=status,
        provider=provider,
        message="ok",
        evidence={"dimensions": "8x6", "mode": "RGBA"} if smoke else {},
        fix_hint="",
        smoke_tested=smoke,
    )


def test_doctor_json_is_valid_json():
    runner = CliRunner()
    with patch("peekxd.cli.run_doctor", return_value=_result(_check())):
        result = runner.invoke(cli, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["checks"][0]["capability"] == "screenshot"
    assert payload["checks"][0]["status"] == "OK"


def test_doctor_capability_filter_passed_through():
    runner = CliRunner()
    with patch("peekxd.cli.run_doctor", return_value=_result(_check(capability="screenshot", smoke=True))) as mock_run:
        result = runner.invoke(cli, ["doctor", "--capability", "screenshot", "--smoke"])

    assert result.exit_code == 0
    mock_run.assert_called_once_with(capability="screenshot", smoke=True)
    assert "screenshot: OK via test" in result.output
    assert "smoke=8x6 RGBA" in result.output


def test_compatibility_json_uses_doctor_result():
    runner = CliRunner()
    with patch("peekxd.cli.run_doctor", return_value=_result(_check(capability="input", provider="xdotool"))):
        result = runner.invoke(cli, ["compatibility", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["checks"][0]["capability"] == "input"


def test_doctor_text_outputs_fix_hint_for_blocked():
    runner = CliRunner()
    blocked = _check(status=CapabilityStatus.BLOCKED, provider="none")
    blocked.fix_hint = "Install a provider"
    with patch("peekxd.cli.run_doctor", return_value=_result(blocked)):
        result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "screenshot: BLOCKED via none" in result.output
    assert "fix=Install a provider" in result.output
