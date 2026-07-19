# map-ai-py

MAP (Markdown for AI Processing) documentation scaffold — install and drift-check CLI for Django, Flask, FastAPI, and plain Python projects.

This package doesn't reimplement MAP's install/patch logic — it vendors and shells out to [`larablocks/map-ai`](https://github.com/larablocks/map-ai)'s `install.sh`/`doctor.sh`, the same zero-runtime-dependency scripts that back non-PHP, non-JS installs of MAP. The only Python-native part is auto-detecting your project's name, stack, and commands from `pyproject.toml`/`requirements.txt` to fill in `AGENTS.md`, the same role [`map-ai-laravel`](https://github.com/larablocks/map-ai-laravel)'s `ProcessesStubContent` and [`map-ai-js`](https://github.com/larablocks/map-ai-js)'s `detect.js` play for their ecosystems.

Requires `bash` to be on `PATH` — true for Mac/Linux and WSL, but worth knowing if you're on native Windows without WSL.

## Install

```bash
pipx run map-ai-py install
# or
uvx map-ai-py install
```

Copies the MAP scaffold (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `docs/`, etc.) into the current directory, merges the required `.gitignore`/`.gitattributes` entries, bootstraps your gitignored personal files (`docs/MEMORY.md`, `docs/memory/gotchas.md`, etc.), and fills in what it can detect:

- **Project name** — from `pyproject.toml`'s `[project].name` (or Poetry's `[tool.poetry].name`), title-cased; falls back to the directory name
- **Stack** — the first framework it recognizes (Django, FastAPI, Flask, Litestar, Starlette, Tornado, Sanic, Pyramid) plus any data-layer dependency (SQLAlchemy, PostgreSQL, MySQL, Redis, MongoDB drivers)
- **Test command** — `pytest` if it's a dependency, prefixed with `uv run`/`poetry run`/`pipenv run` depending on which lockfile is present
- **Static analysis command** — `ruff`/`mypy`/`flake8`, whichever are dependencies
- **Start command** — `python manage.py runserver` for Django, `docker compose up -d` if a compose file exists, `uvicorn`/`flask run` otherwise if detectable
- **Build command** — only for a `src/`-layout package meant to ship to PyPI itself (`python -m build`); omitted for applications, where "build" has no meaning

**Start/build command detection is weaker here than `map-ai-js`'s** — Python has no `package.json`-scripts-equivalent single convention, so this falls back to a `[MANUAL]` placeholder more often. That's an accepted, documented gap, not a bug.

Files that already exist are left alone unless you pass `--force`, which overwrites `SCAFFOLD_FILES` after backing each one up to `<file>.bak`:

```bash
pipx run map-ai-py install --force
```

Pass a path to install somewhere other than the current directory:

```bash
pipx run map-ai-py install ./backend
```

## Checking for drift

```bash
pipx run map-ai-py doctor               # report only — exits 1 if anything needs attention
pipx run map-ai-py doctor --fix         # applies fixable findings unattended, then reports what's left
pipx run map-ai-py doctor --interactive # same fixable set as --fix, confirmed one file at a time
```

`doctor` never touches real project content — it only ever adds missing files/lines, or replaces a stub's own instructional text (a stale italic note, HTML comment, or fenced-code trailing comment) with its current wording. Anything else is reported for you to merge by hand, never auto-applied. See [`larablocks/map-ai`'s README](https://github.com/larablocks/map-ai#doctor--checking-and-repairing-drift-automatically) for the exact safety rules; this package's `doctor`/`install` commands are the same `doctor.sh`/`install.sh` scripts, unmodified.

## Keeping this package in sync with map-ai

This package vendors a copy of `install.sh`/`doctor.sh`/`lib.sh`/`stubs/` rather than depending on `larablocks/map-ai` at install time (there's no PyPI-native way to depend on a Composer package). `scripts/sync-from-map-ai.sh` re-vendors those files from a local `larablocks/map-ai` checkout — run it, review the diff, bump this package's version, and publish whenever map-ai core releases something this package should pick up.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## License

MIT
