"""cli.py — thin wrapper around the vendored install.sh/doctor.sh. All
diff/patch/copy logic lives in those scripts (kept in sync with
larablocks/map-ai via scripts/sync-from-map-ai.sh) — this module only adds
what genuinely needs to be Python-native: reading pyproject.toml/
requirements.txt to auto-fill AGENTS.md's placeholders, mirroring
map-ai-laravel's ProcessesStubContent and map-ai-js's detect.js.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .detect import detect_commands, detect_project_info, process_agents_md_content

VENDOR_DIR = Path(__file__).parent / "vendor"

INFO_LABELS = {
    "[PROJECT NAME]": "Project name",
    "[e.g. Laravel 13, PHP 8.5, PostgreSQL 16, Redis]": "Stack",
}

COMMAND_LABELS = {
    "[TEST COMMAND]": "Tests",
    "[STATIC ANALYSIS COMMAND]": "Static analysis",
    "[START COMMAND]": "Start services",
    "[BUILD COMMAND]": "Build",
}

USAGE = """Usage: map-ai-py <command> [path] [options]

Commands:
  install [path] [--force]              Install the MAP scaffold into [path] (default: cwd)
                                         --force overwrites existing SCAFFOLD_FILES (backed up to <file>.bak first)
  doctor [path] [--fix|--interactive]   Report on drift from the current template
                                         --fix applies safe repairs unattended
                                         --interactive confirms each file's changes before applying

[path] defaults to the current directory for both commands."""


def _run_vendored_script(script_name: str, args: list[str]) -> int:
    """Runs a vendored bash script with stdio inherited from this process —
    required for doctor.sh --interactive's confirm prompts to reach the
    developer's terminal transparently through this wrapper."""
    script_path = VENDOR_DIR / script_name
    result = subprocess.run(["bash", str(script_path), *args])
    return result.returncode


def _print_detection(target: str) -> None:
    print()
    print("Auto-detecting project info and commands for AGENTS.md...")
    print()

    detected = {**detect_project_info(target), **detect_commands(target)}

    for placeholder, label in INFO_LABELS.items():
        if placeholder in detected:
            print(f"  [DETECTED]  {label}: {detected[placeholder]}")
        else:
            print(f"  [MANUAL]    {label}: fill in manually")

    print()

    for placeholder, label in COMMAND_LABELS.items():
        if placeholder in detected:
            print(f"  [DETECTED]  {label}: {detected[placeholder]}")
        else:
            print(f"  [MANUAL]    {label}: fill in manually")


def run_install(args: list[str]) -> int:
    """Runs vendor/install.sh, then — if it left [PROJECT NAME]/[DATE]/command
    placeholders in AGENTS.md — fills in what pyproject.toml/requirements.txt
    let us detect. Safe to run every time: substitution is a no-op once a
    placeholder's already been replaced, so re-running install never
    overwrites real content."""
    target = next((a for a in args if not a.startswith("-")), ".")
    install_args = [target, *[a for a in args if a == "--force"]]

    exit_code = _run_vendored_script("install.sh", install_args)
    if exit_code != 0:
        return exit_code

    agents_path = Path(target) / "AGENTS.md"
    if not agents_path.exists():
        return 0

    original = agents_path.read_text(encoding="utf-8")
    processed = process_agents_md_content(original, target)
    if processed != original:
        agents_path.write_text(processed, encoding="utf-8")
        _print_detection(target)

    return 0


def run_doctor(args: list[str]) -> int:
    """Runs vendor/doctor.sh, passing args straight through (path, --fix, --interactive)."""
    return _run_vendored_script("doctor.sh", args)


def main() -> None:
    argv = sys.argv[1:]
    command = argv[0] if argv else None
    rest = argv[1:]

    if command == "install":
        sys.exit(run_install(rest))
    elif command == "doctor":
        sys.exit(run_doctor(rest))
    elif command in (None, "--help", "-h"):
        print(USAGE)
    else:
        print(f"Unknown command: {command}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
