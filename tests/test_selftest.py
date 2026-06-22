from __future__ import annotations

import subprocess
from pathlib import Path


def test_selftest_unit_exit_code_zero() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "selftest.sh"

    result = subprocess.run(
        ["bash", str(script), "unit"],
        cwd=str(repo_root),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )

    assert result.returncode == 0
    assert "PASS: Unit tests" in result.stdout