from __future__ import annotations

import subprocess
from pathlib import Path


def run_selftest(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "selftest.sh"

    return subprocess.run(
        ["bash", str(script), *args],
        cwd=str(repo_root),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )


def test_selftest_unit_exit_code_zero() -> None:
    result = run_selftest("unit")

    assert result.returncode == 0
    assert "Unit tests (" in result.stdout


def test_selftest_module_option_runs_named_module() -> None:
    result = run_selftest("--module", "unit")

    assert result.returncode == 0
    assert "Unit tests (" in result.stdout


def test_selftest_rejects_unknown_module() -> None:
    result = run_selftest("--module", "definitely-not-a-module")

    assert result.returncode == 2
    assert "Unknown module" in result.stderr


def test_selftest_script_is_executable_for_documented_usage() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "selftest.sh"

    assert script.stat().st_mode & 0o111
