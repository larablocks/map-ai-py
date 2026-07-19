from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def run_cli(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "map_ai_py.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        **kwargs,
    )


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    return tmp_path


class TestInstall:
    def test_copies_the_scaffold_into_the_target_directory(self, target: Path) -> None:
        result = run_cli(["install", str(target)])

        assert result.returncode == 0
        assert (target / "AGENTS.md").exists()
        assert (target / "docs" / "BUGS.md").exists()
        assert (target / ".claude" / "rules" / "security.md").exists()

    def test_auto_detects_project_name_and_stack_from_pyproject_toml(self, target: Path) -> None:
        (target / "pyproject.toml").write_text(
            '[project]\nname = "my-cool-api"\ndependencies = ["fastapi", "uvicorn"]\n'
        )

        run_cli(["install", str(target)])

        agents = (target / "AGENTS.md").read_text()
        assert "My Cool Api" in agents
        assert "FastAPI" in agents
        assert "[PROJECT NAME]" not in agents

    def test_bootstraps_gitignored_personal_files(self, target: Path) -> None:
        run_cli(["install", str(target)])

        assert (target / "docs" / "MEMORY.md").exists()
        assert (target / "docs" / "memory" / "gotchas.md").exists()

    def test_does_not_overwrite_an_existing_agents_md_without_force(self, target: Path) -> None:
        (target / "AGENTS.md").write_text("my custom content")

        run_cli(["install", str(target)])

        assert (target / "AGENTS.md").read_text() == "my custom content"


class TestDoctor:
    def test_exits_1_and_reports_missing_files_on_an_empty_project(self, target: Path) -> None:
        result = run_cli(["doctor", str(target)])

        assert result.returncode == 1
        assert "[FIXABLE]  missing-file" in result.stdout

    def test_exits_0_clean_right_after_doctor_fix(self, target: Path) -> None:
        run_cli(["doctor", str(target), "--fix"])
        result = run_cli(["doctor", str(target)])

        assert result.returncode == 0
        assert "Clean" in result.stdout
