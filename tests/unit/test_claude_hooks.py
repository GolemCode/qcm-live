"""Les garde-fous de l'environnement Claude Code (.claude/hooks) sont testés comme du code."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load("guard_bash")


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m x",
        "git commit -n -m x",
        "git commit -anm x",
        "git push --force origin inc/1-x",
        "git push -f",
        "git push origin main",
        "git push origin HEAD:main",
        "cat .env",
        "grep SECRET .env",
        "head -1 ./.env",
        "source .env && echo ok",
    ],
)
def test_guard_denies(command):
    assert guard.decide(command, branch="inc/1-x") is not None


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'feat: x'",
        "git push -u origin inc/1-banque",
        "git push --force-with-lease origin inc/1-banque",
        "uv run --env-file .env pytest",
        "cat .env.example",
        "make verify",
        "git push origin inc-1",
        "gh pr merge 3 --merge",
        # Un « . » en fin de ligne puis .env dans un heredoc écrit ailleurs : pas une lecture.
        "./gitleaks git --exit-code 1 .\n"
        "cat > ci.yml <<'EOF'\nrun: uv run --env-file .env pytest\nEOF",
    ],
)
def test_guard_allows(command):
    assert guard.decide(command, branch="inc/1-x") is None


def test_guard_denies_commit_and_bare_push_on_main():
    assert guard.decide("git commit -m x", branch="main") is not None
    assert guard.decide("git push", branch="main") is not None
    assert guard.decide("git pull", branch="main") is None


def test_guard_hook_protocol():
    payload = json.dumps({"tool_input": {"command": "git commit --no-verify -m x"}})
    out = subprocess.run(
        [sys.executable, HOOKS / "guard_bash.py"],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    decision = json.loads(out.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "--no-verify" in decision["permissionDecisionReason"]


def test_stop_hook_skips_when_already_active():
    out = subprocess.run(
        [sys.executable, HOOKS / "stop_check.py"],
        input=json.dumps({"stop_hook_active": True}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0


def test_format_hook_ignores_non_python(tmp_path):
    target = tmp_path / "notes.md"
    target.write_text("x")
    out = subprocess.run(
        [sys.executable, HOOKS / "format_python.py"],
        input=json.dumps({"tool_input": {"file_path": str(target)}}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0
