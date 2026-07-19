"""detect.py — reads pyproject.toml/requirements.txt (and a few marker files)
to auto-fill AGENTS.md's placeholders. The Python equivalent of
map-ai-laravel's ProcessesStubContent trait and map-ai-js's detect.js,
applying the same "detect what you can, leave the rest as a placeholder for
the developer" fallback rather than guessing.

Placeholder detection is weaker here than the JS/PHP versions, by necessity:
Python has no package.json/composer.json-equivalent single manifest with a
universal "scripts" section, so start/build commands in particular detect
less reliably and fall back to [MANUAL] more often. This is a known,
accepted gap — see docs/memory/project_map_ai_py_wrapper.md's design notes.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

# Meta/full frameworks first so a more specific match wins when both a
# framework and one of its own dependencies would otherwise match (e.g. a
# FastAPI project also has starlette installed as a transitive dependency).
FRAMEWORK_DEPS: list[tuple[str, str]] = [
    ("django", "Django"),
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("litestar", "Litestar"),
    ("starlette", "Starlette"),
    ("tornado", "Tornado"),
    ("sanic", "Sanic"),
    ("pyramid", "Pyramid"),
]

DATA_DEPS: list[tuple[str, str]] = [
    ("sqlalchemy", "SQLAlchemy"),
    ("psycopg2", "PostgreSQL"),
    ("psycopg2-binary", "PostgreSQL"),
    ("psycopg", "PostgreSQL"),
    ("pymysql", "MySQL"),
    ("mysqlclient", "MySQL"),
    ("redis", "Redis"),
    ("pymongo", "MongoDB"),
]


def _normalize(name: str) -> str:
    """PEP 503 normalization — dependency names are case/separator-insensitive."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_dependencies(target_path: str | Path) -> dict[str, str]:
    """@returns {normalized dependency name: version specifier or ''}"""
    target = Path(target_path)
    deps: dict[str, str] = {}

    pyproject_path = target / "pyproject.toml"
    if pyproject_path.exists():
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        for entry in data.get("project", {}).get("dependencies", []):
            _add_requirement(deps, entry)

        # Poetry (pre-PEP 621 style) keeps its own dependency table.
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for pkg_name in poetry_deps:
            if pkg_name.lower() != "python":
                deps[_normalize(pkg_name)] = ""

    requirements_path = target / "requirements.txt"
    if requirements_path.exists():
        for line in requirements_path.read_text(encoding="utf-8").splitlines():
            stripped = line.split("#", 1)[0].strip()
            if stripped and not stripped.startswith("-"):
                _add_requirement(deps, stripped)

    return deps


def _add_requirement(deps: dict[str, str], requirement: str) -> None:
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", requirement.strip())
    if match:
        deps.setdefault(_normalize(match.group(1)), requirement)


def project_name(target_path: str | Path) -> str:
    target = Path(target_path)
    pyproject_path = target / "pyproject.toml"

    name: str | None = None
    if pyproject_path.exists():
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            name = data.get("project", {}).get("name") or data.get("tool", {}).get("poetry", {}).get("name")
        except Exception:
            name = None

    if not name:
        name = target.resolve().name

    return re.sub(r"[-_]+", " ", name).title()


def detect_package_manager(target_path: str | Path) -> str:
    target = Path(target_path)
    if (target / "uv.lock").exists():
        return "uv run"
    if (target / "poetry.lock").exists():
        return "poetry run"
    if (target / "Pipfile.lock").exists():
        return "pipenv run"
    return ""


def detect_project_info(target_path: str | Path) -> dict[str, str]:
    """@returns {placeholder: detected value}"""
    deps = read_dependencies(target_path)
    detected = {"[PROJECT NAME]": project_name(target_path)}

    stack: list[str] = []
    for dep, label in FRAMEWORK_DEPS:
        if dep in deps:
            stack.append(label)
            break

    stack.append("Python")

    for dep, label in DATA_DEPS:
        if dep in deps and label not in stack:
            stack.append(label)

    detected["[e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]"] = ", ".join(stack)

    return detected


def detect_commands(target_path: str | Path) -> dict[str, str]:
    """@returns {placeholder: detected value}"""
    target = Path(target_path)
    deps = read_dependencies(target_path)
    runner = detect_package_manager(target_path)
    prefix = f"{runner} " if runner else ""
    detected: dict[str, str] = {}

    if "pytest" in deps:
        detected["[TEST COMMAND]"] = f"{prefix}pytest"
    elif (target / "tests").is_dir() or (target / "test").is_dir():
        detected["[TEST COMMAND]"] = f"{prefix}python -m unittest"

    checks = []
    if "ruff" in deps:
        checks.append(f"{prefix}ruff check")
    if "mypy" in deps:
        checks.append(f"{prefix}mypy .")
    if "flake8" in deps:
        checks.append(f"{prefix}flake8")
    if checks:
        detected["[STATIC ANALYSIS COMMAND]"] = " && ".join(checks)

    # Start/build commands have no universal convention in Python (unlike
    # package.json's scripts or Composer's) — special-case what's reliably
    # inferable per framework rather than guessing generically.
    if (target / "manage.py").exists():
        detected["[START COMMAND]"] = "python manage.py runserver"
    elif (
        Path.exists(target / "docker-compose.yml")
        or Path.exists(target / "docker-compose.yaml")
        or Path.exists(target / "compose.yaml")
        or Path.exists(target / "compose.yml")
    ):
        detected["[START COMMAND]"] = "docker compose up -d"
    elif "uvicorn" in deps:
        detected["[START COMMAND]"] = f"{prefix}uvicorn main:app --reload"
    elif "flask" in deps:
        detected["[START COMMAND]"] = f"{prefix}flask run"

    if (target / "pyproject.toml").exists() and _looks_like_distributable_package(target):
        detected["[BUILD COMMAND]"] = f"{prefix}python -m build"

    return detected


def _looks_like_distributable_package(target: Path) -> bool:
    """True if this looks like a package meant to ship to PyPI itself (a
    src/ layout containing at least one sub-package), not an application —
    "build" has no meaning for the latter."""
    src_dir = target / "src"
    if not src_dir.is_dir():
        return False
    return any(child.is_dir() for child in src_dir.iterdir())


def process_agents_md_content(content: str, target_path: str | Path) -> str:
    """Applies [DATE] plus detect_project_info()/detect_commands() substitutions to AGENTS.md content."""
    result = content.replace("[DATE]", date.today().isoformat())

    detected = {**detect_project_info(target_path), **detect_commands(target_path)}
    for placeholder, value in detected.items():
        result = result.replace(placeholder, value)

    return result
