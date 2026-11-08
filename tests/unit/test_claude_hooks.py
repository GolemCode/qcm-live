"""Les garde-fous de l'environnement Claude Code (.claude/hooks) sont testés comme du code."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / ".claude" / "hooks"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load("guard_bash")


def _run_hook(
    name: str, payload: object = None, project: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)} if project else None
    return subprocess.run(
        [sys.executable, HOOKS / f"{name}.py"],
        input=None if payload is None else json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


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
    out = _run_hook("guard_bash", {"tool_input": {"command": "git commit --no-verify -m x"}})
    decision = json.loads(out.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "--no-verify" in decision["permissionDecisionReason"]


def test_format_hook_ignores_non_python(tmp_path):
    target = tmp_path / "notes.md"
    target.write_text("x")
    assert _run_hook("format_python", {"tool_input": {"file_path": str(target)}}).returncode == 0


stop = load("stop_check")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True
    )


def _repo(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "init")
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


# --- Audit externe (R), constat 1 : le garde sur .env évite les accidents, sans plus.


@pytest.mark.parametrize(
    "command",
    [
        "base64 .env",
        "tac .env",
        "cut -c1- .env",
        "sort .env",
        "cp .env /tmp/x",
        "mv ./.env /tmp/x",
        "dd if=.env",
        "vim .env",
        "diff .env .env.example",
        "commande-inconnue .env",  # la règle ne dépend plus d'une liste de lecteurs
        # Les préfixes ne cachent pas la commande réelle.
        "uv run cat .env",
        "FOO=1 cat .env",
        "timeout 5 cat .env",
        "env cat .env",
        # git affiche ou indexe le fichier : seules quelques sous-commandes sont sûres.
        "git diff --no-index /dev/null .env",
        "git add -f .env",
        "git show HEAD:.env",
        "cat<.env",
    ],
)
def test_guard_denies_more_ways_to_read_env(command):
    assert guard.decide(command, branch="inc/1-x") is not None


@pytest.mark.parametrize(
    "command",
    [
        "ls -la .env",
        "test -f .env",
        "git check-ignore .env",
        "make classe ENV_FILE=.env.test",
        "cat .env.test",
        'git commit -m "docs: ENV_FILE=.env"',
        # Écrire un script n'est pas l'exécuter : un heredoc reste du texte.
        "cat > run.sh <<EOF\ngit push --force\nEOF",
        # Le corps d'un heredoc est du texte : un message de commit peut citer la commande.
        "git commit -F - <<'EOF'\ncat .env\nEOF",
    ],
)
def test_guard_allows_commands_that_do_not_read_env(command):
    assert guard.decide(command, branch="inc/1-x") is None


@pytest.mark.parametrize(
    "command",
    [
        "timeout 5 git push --force",
        "timeout 5 git commit --no-verify -m x",
        "FOO=1 git commit -n -m x",
        "env git push -f",
        # Un heredoc donné à un shell, lui, contient des commandes.
        "bash <<EOF\ngit commit --no-verify -m x\nEOF",
        # Trouvés par /code-review.
        "timeout -k 5 60 git push --force",
        "env -i git push --force",
        "env -u FOO git commit --no-verify -m x",
        # La suite de ligne ne sépare pas une option de sa commande.
        "git push \\\n --force origin inc/1-x",
        "git commit \\\n --no-verify -m x",
    ],
)
def test_guard_sees_through_prefixes_and_shell_heredocs(command):
    assert guard.decide(command, branch="inc/1-x") is not None


@pytest.mark.parametrize(
    "command",
    [
        # Trouvés par /security-review : « << » n'annonce pas toujours un heredoc,
        # et bash exécute bien les lignes suivantes.
        'grep x <<< "abc"\ngit push --force origin x',
        'echo "voir a <<X"\ngit push --force origin x',
        'echo "<<X"\ngit push origin HEAD:main',
        'git add -A && git commit -m "doc de <<EOF"\ngit commit --no-verify -m b',
        "echo $((1<<2))\ngit commit --no-verify -m b",
        'echo "<<X"\nSKIP=gitleaks git commit -m a',
        'echo "<<X"\ncat .env',
        # Le corps est donné à un shell, avant ou après le « << ».
        "cat <<EOF | bash\ngit push --force origin x\nEOF",
        "source /dev/stdin <<EOF\ngit push --force origin x\nEOF",
        # La fin d'un heredoc au délimiteur composé doit être trouvée.
        "cat <<'E-F' > f\ntexte\nE-F\ngit push --force origin x",
    ],
)
def test_guard_does_not_mistake_a_double_chevron_for_a_heredoc(command):
    assert guard.decide(command, branch="inc/1-x") is not None


@pytest.mark.parametrize(
    "command",
    [
        "python3 -c \"print(open('.env').read())\"",
        "uv run --env-file .env python -c 'import os; print(os.environ)'",
        # Une commande cachée dans une chaîne n'est pas analysée non plus.
        'echo "$(cat .env)"',
        "bash -c 'cat .env'",
    ],
)
def test_guard_is_not_a_security_boundary(command):
    """Limite assumée, écrite dans REX.md (section R) : un filtre de texte ne peut pas voir
    ce que fait un programme. Si ce test tombe, relire ce que le REX promet."""
    assert guard.decide(command, branch="inc/1-x") is None


def test_claude_shell_loads_the_test_env_not_the_real_one():
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["env"]["UV_ENV_FILE"] == ".env.test"
    assert "Read(./.env)" in settings["permissions"]["deny"]


def test_test_env_is_tracked_and_holds_no_secret():
    content = (REPO / ".env.test").read_text(encoding="utf-8")
    key = next(line for line in content.splitlines() if line.startswith("DJANGO_SECRET_KEY="))
    assert "pas-un-secret" in key
    tracked = subprocess.run(
        ["git", "check-ignore", "-q", ".env.test"], cwd=REPO, check=False
    ).returncode
    assert tracked == 1  # 1 : le fichier n'est pas ignoré


def _make_dry_run(*args: str) -> str:
    return subprocess.run(
        ["make", "-n", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


@pytest.mark.parametrize("target", sorted(guard.VERIFY_TARGETS))
def test_quality_targets_never_load_the_real_env(target):
    output = _make_dry_run(target)
    assert "--env-file .env.test" in output
    assert "--env-file .env " not in output
    assert "gen_env" not in output  # pas besoin du vrai .env pour vérifier


def test_class_mode_uses_the_real_env_unless_told_otherwise():
    assert "--env-file .env " in _make_dry_run("classe")
    assert "--env-file .env.test " in _make_dry_run("classe", "ENV_FILE=.env.test")


# --- Audit externe (R), constat 3 : le hook Stop vérifie que la procédure est allée au bout.

I6_REX = "## I5 — x\ntexte\n\n---\n\n## I6 — y\nAudit spec-auditor : abc1234, 3 survivantes.\n"


def test_gaps_reproduce_the_i6_stop_right_after_security_review():
    """L'arrêt réel de I6 : branche de travail, ni REX, ni audit, ni PR."""
    joined = " ".join(stop.increment_gaps("6", "## I5 — x\n", None))
    assert "REX.md" in joined
    assert "spec-auditor" in joined
    assert "PR" in joined


def test_gaps_audit_of_another_increment_does_not_count():
    rex = "## I5 — x\nAudit spec-auditor : abc1234\n\n## I6 — y\nRien sur l'audit.\n"
    assert "spec-auditor" in " ".join(stop.increment_gaps("6", rex, "OPEN"))


def test_gaps_mere_mention_of_the_auditor_does_not_count():
    """La section R citait l'agent dans un constat, sans qu'aucun audit ait eu lieu."""
    rex = "## R — x\n**6. Agent `spec-auditor` « en lecture seule » : exact.**\n"
    assert "spec-auditor" in " ".join(stop.increment_gaps("r", rex, "OPEN"))


def test_rex_section_does_not_confuse_i1_with_i10():
    rex = "## I10 — dix\nAudit spec-auditor : abc1234\n"
    assert stop.rex_section(rex, "1") == ""
    assert stop.rex_section(rex, "10") != ""


def test_gaps_open_pull_request_must_still_be_merged():
    gaps = stop.increment_gaps("6", I6_REX, "OPEN")
    assert len(gaps) == 1
    assert "fusionn" in gaps[0]


def test_gaps_closed_pull_request_delivers_nothing():
    gaps = stop.increment_gaps("6", I6_REX, "CLOSED")
    assert len(gaps) == 1
    assert "fermée" in gaps[0]


def test_gaps_merged_pull_request_leaves_the_tag():
    gaps = stop.increment_gaps("6", I6_REX, "MERGED")
    assert len(gaps) == 1
    assert "inc-6" in gaps[0]


def test_gaps_correction_increment_uses_section_r():
    rex = "## I7 — x\nAudit spec-auditor : abc1234\n\n## R — Audit\nAudit spec-auditor : def5678\n"
    assert len(stop.increment_gaps("r", rex, "OPEN")) == 1  # seule la fusion manque
    assert "REX.md" in " ".join(stop.increment_gaps("r", "## I7\n", "OPEN"))


@pytest.mark.parametrize(
    ("last_merge", "tags", "expected"),
    [
        ("Incrément 6 : résultats (#7)", set(), 1),
        ("Incrément 6 : résultats (#7)", {"inc-6"}, 0),
        ("Incrément R : audit externe (#9)", set(), 1),
        ("Incrément R : audit externe (#9)", {"inc-r"}, 0),
        ("docs: autre chose", set(), 0),
    ],
)
def test_gaps_on_main_only_the_tag_can_be_missing(last_merge, tags, expected):
    assert len(stop.missing_tag(last_merge, tags)) == expected


def _project(path: Path, branch: str) -> Path:
    repo = _repo(path)
    (repo / "Makefile").write_text("check:\n\t@true\n")
    (repo / "REX.md").write_text("## I5 — x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Incrément 5 : x (#6)")
    _git(repo, "tag", "inc-5")
    _git(repo, "branch", "-m", branch)
    return repo


def _run_stop(repo: Path, active: bool = False) -> subprocess.CompletedProcess[str]:
    return _run_hook("stop_check", {"stop_hook_active": active}, repo)


def test_stop_hook_ignores_other_branches(tmp_path):
    assert _run_stop(_project(tmp_path, "essai")).returncode == 0


def test_stop_hook_sends_back_to_work_when_the_procedure_is_unfinished(tmp_path):
    repo = _project(tmp_path, "inc/6-resultats")
    first = _run_stop(repo)
    assert first.returncode == 2
    assert "REX.md" in first.stderr
    # `make check` est déjà mémorisé comme vert : la procédure reste vérifiée.
    assert _run_stop(repo).returncode == 2
    # Une seule relance par arrêt : s'arrêter reste possible, pour poser une question.
    assert _run_stop(repo, active=True).returncode == 0


def test_stop_hook_passes_on_main_once_tagged(tmp_path):
    assert _run_stop(_project(tmp_path, "main")).returncode == 0


def test_stop_hook_reports_a_failing_check_before_the_procedure(tmp_path):
    repo = _project(tmp_path, "inc/6-resultats")
    (repo / "Makefile").write_text("check:\n\t@false\n")
    result = _run_stop(repo)
    assert result.returncode == 2
    assert "make check" in result.stderr


# --- Audit externe (R), constat 4 : un code de retour de vérification ne se masque pas.


@pytest.mark.parametrize(
    "command",
    [
        # Les deux incidents réels.
        "timeout 600 uv run pytest tests/e2e -q 2>&1 | tail -2 && git add -A && git commit -q -m x",
        'make verify > v.log 2>&1; echo "exit $?" >> v.log',
        # Variantes du pipe.
        "make verify 2>&1 | tail -40",
        "make check | tail -3",
        "uv run --env-file .env.test pytest tests/unit -q | tail -3",
        "uv run --no-env-file pyright | tail -1",
        "uv run ruff check . |& head",
        "python -m pytest | grep passed",
        "DJANGO_DEBUG=1 make test | tee t.log",
        "cd x && make accept INC=7 2>&1 | tail -5",
        # Variantes de la suite de commandes.
        "uv run pytest; git commit -m x",
        "make check\ngit commit -m x",
        "(make verify > v.log 2>&1; tail -30 v.log)",
        "make check || true",
        "make check || echo raté",
        "make check &> v.log; tail v.log",
        # Trouvés par /code-review : le masquage plus loin dans la chaîne.
        "make check && echo ok; echo fin",
        "make check && echo ok || true",
        "make check && echo a\necho b",
        "set -o pipefail; make check | tail -3; echo fin",
        "set -o pipefail; make check | tail -3 || true",
        "make check &",
        # Un `exit` final ne vaut que s'il rend un vrai code.
        "make verify; exit 0",
        "make verify; echo x; exit 0",
        "make check || exit 0",
        "make check; exit",
        # `+o` désactive pipefail.
        "set +o pipefail; make check | tail",
        # Les préfixes ne cachent pas la vérification.
        "timeout --signal=KILL 60 make check | tail",
        "time make check | tail",
        "! make check; echo x",
        "uv run --package foo pytest | tail",
        "uv run --with-editable . pytest | tail",
    ],
)
def test_guard_denies_masked_exit_codes(command):
    reason = guard.decide(command, branch="inc/1-x")
    assert reason is not None
    assert "code de retour" in reason


@pytest.mark.parametrize(
    "command",
    [
        "make verify",
        "make check && git commit -m x",
        "set -o pipefail; make verify 2>&1 | tail -40",
        "set -euo pipefail\nuv run pytest | tail -3",
        "make verify > v.log 2>&1; code=$?; tail -25 v.log; exit $code",
        "make check || exit 1",
        # Un pipe plus loin ne touche pas au code de la vérification.
        "make verify > v.log 2>&1; code=$?; grep x v.log | cut -c1-9; exit $code",
        "make check && echo ok | tail -1",
        "if make check; then git commit -m x; fi",
        # Trouvés par /code-review : honnêtes, mais refusés à tort.
        "make check &&\n git commit -m x",
        "(make check) && git commit -m x",
        "set -o pipefail; make check |\n tail -3",
        "uv run pytest tests/unit \\\n -q && git commit -m x",
        # Ce ne sont pas des vérifications.
        "make help | grep check",
        "make -n check | grep env-file",
        "uv run pyright --version | head -1",
        "git log --oneline | head -3",
        "uv tree | tail -3",
        "grep -n pytest Makefile | head",
        # Le texte d'un message, d'une chaîne ou d'un heredoc n'est pas une commande.
        'git commit -m "docs: make check | tail masque le code"',
        "git commit -F - <<'EOF'\nmake check | tail\nuv run pytest; echo fini\nEOF",
        "cat > note.md <<EOF\nmake verify | tail -3\nEOF\ngit status",
    ],
)
def test_guard_allows_honest_exit_codes(command):
    assert guard.decide(command, branch="inc/1-x") is None


def test_guard_allows_pushing_the_correction_tag_from_main():
    assert guard.decide("git push origin inc-r", branch="main") is None
    assert guard.decide("git push origin inc-x", branch="main") is not None


# --- Audit externe (R), constat 6 : ce que l'agent spec-auditor peut réellement faire.


def test_spec_auditor_description_matches_what_it_can_do():
    text = (REPO / ".claude" / "agents" / "spec-auditor.md").read_text(encoding="utf-8")
    front = text.split("---")[1]
    assert "isolation: worktree" in front
    assert "Bash" in front
    assert "lecture seule" not in front  # la description ne promet plus ce que Bash permet


# --- Audit externe (R), constat 7 : la langue de la conversation.


def test_session_start_recalls_the_conversation_language():
    assert "en français" in _run_hook("session_start", project=REPO).stdout
