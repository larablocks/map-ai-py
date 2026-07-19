from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest

from map_ai_py.detect import (
    detect_commands,
    detect_package_manager,
    detect_project_info,
    process_agents_md_content,
    project_name,
)


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    return tmp_path


def write_pyproject(target: Path, project: dict | None = None, tool: dict | None = None) -> None:
    lines = ["[project]"]
    for key, value in (project or {"name": "my-app"}).items():
        if isinstance(value, list):
            items = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{items}]")
        else:
            lines.append(f'{key} = "{value}"')

    content = "\n".join(lines) + "\n"

    if tool:
        content += "\n" + tool

    (target / "pyproject.toml").write_text(content)


class TestProjectName:
    def test_title_cases_the_project_name(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "my-cool-app"})
        assert project_name(tmp_project) == "My Cool App"

    def test_falls_back_to_the_title_cased_directory_name(self, tmp_project: Path) -> None:
        import re

        expected = re.sub(r"[-_]+", " ", tmp_project.resolve().name).title()
        assert project_name(tmp_project) == expected

    def test_reads_poetry_style_name(self, tmp_project: Path) -> None:
        (tmp_project / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "poetry-app"\n'
        )
        assert project_name(tmp_project) == "Poetry App"


class TestDetectProjectInfo:
    def test_detects_django(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["django>=5.0", "psycopg2-binary"]})
        info = detect_project_info(tmp_project)
        assert info["[e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]"] == "Django, Python, PostgreSQL"

    def test_detects_fastapi_over_starlette(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["fastapi", "starlette", "uvicorn"]})
        info = detect_project_info(tmp_project)
        assert info["[e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]"] == "FastAPI, Python"

    def test_reads_requirements_txt_when_no_pyproject(self, tmp_project: Path) -> None:
        (tmp_project / "requirements.txt").write_text("flask==3.0.0\nredis>=5.0\n")
        info = detect_project_info(tmp_project)
        assert info["[e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]"] == "Flask, Python, Redis"

    def test_reports_plain_python_when_no_framework_detected(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app"})
        info = detect_project_info(tmp_project)
        assert info["[e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]"] == "Python"


class TestDetectPackageManager:
    def test_detects_uv(self, tmp_project: Path) -> None:
        (tmp_project / "uv.lock").write_text("")
        assert detect_package_manager(tmp_project) == "uv run"

    def test_detects_poetry(self, tmp_project: Path) -> None:
        (tmp_project / "poetry.lock").write_text("")
        assert detect_package_manager(tmp_project) == "poetry run"

    def test_defaults_to_no_prefix(self, tmp_project: Path) -> None:
        assert detect_package_manager(tmp_project) == ""


class TestDetectCommands:
    def test_detects_pytest_with_the_right_runner_prefix(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["pytest"]})
        (tmp_project / "uv.lock").write_text("")
        assert detect_commands(tmp_project)["[TEST COMMAND]"] == "uv run pytest"

    def test_detects_django_start_command(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["django"]})
        (tmp_project / "manage.py").write_text("")
        assert detect_commands(tmp_project)["[START COMMAND]"] == "python manage.py runserver"

    def test_prefers_docker_compose_for_start_command(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["fastapi", "uvicorn"]})
        (tmp_project / "compose.yaml").write_text("services: {}")
        assert detect_commands(tmp_project)["[START COMMAND]"] == "docker compose up -d"

    def test_falls_back_to_uvicorn_for_fastapi_without_compose(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["fastapi", "uvicorn"]})
        assert detect_commands(tmp_project)["[START COMMAND]"] == "uvicorn main:app --reload"

    def test_combines_ruff_and_mypy_into_static_analysis(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app", "dependencies": ["ruff", "mypy"]})
        assert detect_commands(tmp_project)["[STATIC ANALYSIS COMMAND]"] == "ruff check && mypy ."

    def test_detects_build_command_for_a_src_layout_package(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "mylib"})
        (tmp_project / "src" / "mylib").mkdir(parents=True)
        assert detect_commands(tmp_project)["[BUILD COMMAND]"] == "python -m build"

    def test_omits_build_command_for_an_application(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app"})
        assert "[BUILD COMMAND]" not in detect_commands(tmp_project)

    def test_leaves_undetected_commands_absent(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "app"})
        assert detect_commands(tmp_project) == {}


class TestProcessAgentsMdContent:
    def test_fills_in_every_placeholder_it_can_detect(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "my-app", "dependencies": ["django"]})
        (tmp_project / "manage.py").write_text("")

        content = (
            "_Project: [PROJECT NAME] | Stack: [e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]_\n"
            "_MAP v1.0 | Last updated: [DATE]_\n"
            "- Start services: `[START COMMAND]`\n"
            "- Static analysis: `[STATIC ANALYSIS COMMAND]`\n"
        )

        result = process_agents_md_content(content, tmp_project)

        assert "_Project: My App | Stack: Django, Python_" in result
        assert f"_MAP v1.0 | Last updated: {date.today().isoformat()}_" in result
        assert "- Start services: `python manage.py runserver`" in result
        assert "[STATIC ANALYSIS COMMAND]" in result  # nothing to detect — left as-is

    def test_is_a_no_op_on_content_with_no_placeholders_left(self, tmp_project: Path) -> None:
        write_pyproject(tmp_project, {"name": "my-app"})
        content = "_Project: My App | Stack: Python_"
        assert process_agents_md_content(content, tmp_project) == content
