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
        # Contournements relevés en revue de code.
        "git -C . commit -n -m x",
        "SKIP=gitleaks git commit -m x",
        "git push origin +inc/1-x",
        "cd /tmp\ngit commit -n -m x",
        "cat > f <<EOF\nl'apostrophe ouvre une citation\nEOF\ngit commit --no-verify -m x",
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
        # Faux positifs relevés en revue de code : le texte d'un message n'est pas une option.
        "git commit -m 'fix: option -ignore-case'",
        'git commit -m "docs: interdire --no-verify et SKIP=x"',
        "git push origin main-hotfix",
        "git commit -am 'feat: x'",
    ],
)
def test_guard_allows(command):
    assert guard.decide(command, branch="inc/1-x") is None


@pytest.mark.parametrize(
    "command",
    ["git commit -m x", "git push", "git push origin HEAD", "git push -u origin HEAD"],
)
def test_guard_denies_commit_and_push_from_main(command):
    assert guard.decide(command, branch="main") is not None


@pytest.mark.parametrize("command", ["git pull", "git push origin inc-3", "git tag inc-3"])
def test_guard_allows_on_main(command):
    assert guard.decide(command, branch="main") is None


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


stop = load("stop_check")


def _repo(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=tmp_path,
            check=True,
        )
    return tmp_path


def test_stop_state_key_sees_untracked_content_changes(tmp_path):
    repo = _repo(tmp_path)
    new_file = repo / "test_new.py"
    new_file.write_text("ok = 1\n")
    before = stop.state_key(repo)
    new_file.write_text("ok = (\n")  # même nom, contenu cassé : l'empreinte doit changer
    assert stop.state_key(repo) != before


def test_stop_marker_lives_in_real_git_dir_for_worktrees(tmp_path):
    repo = _repo(tmp_path / "main")
    worktree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", str(worktree)], cwd=repo, check=True)
    marker = stop.marker_path(worktree)
    assert marker.parent.is_dir()
    assert (worktree / ".git").is_file()  # .git est un fichier dans un worktree
