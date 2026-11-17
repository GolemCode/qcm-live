"""Les garde-fous de l'environnement Claude Code (.claude/hooks) sont testés comme du code."""

import importlib.util
import json
import os
import re
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
    name: str,
    payload: object = None,
    project: Path | None = None,
    first_on_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if project:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    if first_on_path:
        env["PATH"] = f"{first_on_path}{os.pathsep}{env['PATH']}"
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
        "uv run --env-file .env.test pytest",
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
        # Charger la vraie clé dans un processus : plus aucune vérification n'en a besoin.
        "uv run --env-file .env pytest",
        "uv run --env-file=.env printenv DJANGO_SECRET_KEY",
        "UV_ENV_FILE=.env uv run printenv DJANGO_SECRET_KEY",
        "uv run --env-file .env make check",
        "uv run --env-file .env ls",
        "uv run --env-file .env",
        "uv -q run --env-file .env printenv DJANGO_SECRET_KEY",
        "uv --directory . run --env-file .env printenv DJANGO_SECRET_KEY",
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
        # Une ligne illisible n'empêche pas d'analyser les suivantes.
        "bash <<EOF\nl'apostrophe\ngit push --force origin x\nEOF",
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
        "git commit -F .env",
        "cat .en?",
        # Une commande cachée dans une chaîne n'est pas analysée non plus.
        'echo "$(cat .env)"',
        "bash -c 'cat .env'",
    ],
)
def test_guard_is_not_a_security_boundary(command):
    """Limite assumée, écrite dans le REX (rex/R.md) : un filtre de texte ne peut pas voir
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
        ["git", "check-ignore", "--no-index", "-q", ".env.test"], cwd=REPO, check=False
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
    # -B : même si .env existe sur ce poste, le mode classe de test n'en dépend pas.
    assert "gen_env" not in _make_dry_run("-B", "classe", "ENV_FILE=.env.test")


# --- Audit externe (R), constat 3 : le hook Stop vérifie que la procédure est allée au bout.

I6_REX = "# I6 — y\nAudit spec-auditor : abc1234, 3 survivantes.\n"


def test_gaps_reproduce_the_i6_stop_right_after_security_review():
    """L'arrêt réel de I6 : branche de travail, ni REX, ni audit, ni PR."""
    joined = " ".join(stop.increment_gaps("6", "", None))
    assert "rex/I6.md" in joined
    assert "spec-auditor" in joined
    assert "PR" in joined


def test_gaps_mere_mention_of_the_auditor_does_not_count():
    """La section R citait l'agent dans un constat, sans qu'aucun audit ait eu lieu."""
    rex = "# R — x\n**6. Agent `spec-auditor` « en lecture seule » : exact.**\n"
    assert "spec-auditor" in " ".join(stop.increment_gaps("r", rex, "OPEN"))


@pytest.mark.parametrize(
    "line",
    [
        "Le hook cherche la ligne « Audit spec-auditor : abc1234 » dans le REX.",
        "Audit spec-auditor : <commit>",
        "Audit spec-auditor : ",
    ],
)
def test_gaps_audit_line_must_start_the_line_and_name_a_commit(line):
    rex = f"# R — x\n{line}\n"
    assert "spec-auditor" in " ".join(stop.increment_gaps("r", rex, "OPEN"))


@pytest.mark.parametrize(
    ("increment", "name"),
    [
        ("6", "rex/I6.md"),
        ("1", "rex/I1.md"),
        ("10", "rex/I10.md"),
        ("r", "rex/R.md"),
        ("m", "rex/M.md"),
    ],
)
def test_rex_file_of_an_increment(increment, name):
    """Un fichier par incrément (I15) : I1 n'est pas I10, R et M gardent leur lettre."""
    assert stop.rex_name(increment) == name


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


def _project(
    path: Path,
    branch: str,
    rex: str = "",
    merge: str = "Incrément 5 : x (#6)",
    tag: str = "inc-5",
) -> Path:
    repo = _repo(path / "repo")
    (repo / "Makefile").write_text("check:\n\t@true\n")
    (repo / "rex").mkdir()
    (repo / "rex" / "I5.md").write_text("# I5 — x\n")
    match = re.match(r"inc/(\w+?)-", branch)
    if rex and match:
        (repo / stop.rex_name(match.group(1))).write_text(rex)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", merge)
    _git(repo, "tag", tag)
    _git(repo, "branch", "-m", branch)
    return repo


def _fake_gh(path: Path, state: str) -> Path:
    """Un faux `gh` qui annonce l'état de la PR, à placer en tête du PATH."""
    folder = path / "bin"
    folder.mkdir()
    gh = folder / "gh"
    gh.write_text(f"#!/bin/sh\necho {state}\n")
    gh.chmod(0o755)
    return folder


def _run_stop(
    repo: Path, active: bool = False, gh_folder: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return _run_hook("stop_check", {"stop_hook_active": active}, repo, gh_folder)


def test_stop_hook_ignores_other_branches(tmp_path):
    assert _run_stop(_project(tmp_path, "essai")).returncode == 0


def test_stop_hook_sends_back_to_work_when_the_procedure_is_unfinished(tmp_path):
    repo = _project(tmp_path, "inc/6-resultats")
    first = _run_stop(repo)
    assert first.returncode == 2
    assert "rex/I6.md" in first.stderr
    # `make check` est déjà mémorisé comme vert : la procédure reste vérifiée.
    assert _run_stop(repo).returncode == 2
    # Une seule relance par arrêt : s'arrêter reste possible, pour poser une question.
    assert _run_stop(repo, active=True).returncode == 0


def test_stop_hook_recognises_the_correction_branch(tmp_path):
    result = _run_stop(_project(tmp_path, "inc/r-audit"))
    assert result.returncode == 2
    assert "rex/R.md" in result.stderr


def test_stop_hook_reads_the_rex_and_the_pull_request(tmp_path):
    """Section et ligne d'audit présentes : seul l'état réel de la PR reste signalé."""
    rex = "# I6 — y\nAudit spec-auditor : abc1234\n"
    repo = _project(tmp_path, "inc/6-resultats", rex=rex)
    result = _run_stop(repo, gh_folder=_fake_gh(tmp_path, "OPEN"))
    assert result.returncode == 2
    assert "fusionn" in result.stderr
    assert "rex/I6.md" not in result.stderr
    assert "L'audit" not in result.stderr


def test_stop_hook_on_main_requires_the_tag_of_the_last_merge(tmp_path):
    repo = _project(tmp_path, "main", merge="Incrément 6 : résultats (#7)")
    result = _run_stop(repo)
    assert result.returncode == 2
    assert "inc-6" in result.stderr
    _git(repo, "tag", "inc-6")
    assert _run_stop(repo).returncode == 0


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


# --- Incrément M : un incrément de méthode porte une lettre, comme R.


def test_stop_hook_recognises_a_method_increment(tmp_path):
    result = _run_stop(_project(tmp_path, "inc/m-methode"))
    assert result.returncode == 2
    assert "rex/M.md" in result.stderr


def test_gaps_on_main_after_a_method_increment():
    assert stop.missing_tag("Incrément M : méthode (#14)", set()) == [
        "Poser et pousser le tag inc-m."
    ]
    assert stop.missing_tag("Incrément M : méthode (#14)", {"inc-m"}) == []


# --- Incrément M : le hook Stop ne lance pas `make check` pendant qu'un pytest tourne.


def _fake_process(proc: Path, pid: int, cmdline: list[str], cwd: Path) -> None:
    folder = proc / str(pid)
    folder.mkdir(parents=True)
    (folder / "cmdline").write_bytes("\0".join(cmdline).encode() + b"\0")
    (folder / "cwd").symlink_to(cwd)


@pytest.mark.parametrize(
    "cmdline",
    [
        ["/home/u/.venv/bin/python3", "/home/u/.venv/bin/pytest", "tests/e2e", "-q"],
        ["uv", "run", "--env-file", ".env.test", "pytest", "tests/unit"],
        ["python", "-m", "pytest", "-x"],
    ],
)
def test_pytest_running_sees_a_pytest_in_the_project(tmp_path, cmdline):
    project = tmp_path / "repo"
    project.mkdir()
    _fake_process(tmp_path / "proc", 4242, cmdline, project)
    assert stop.pytest_running(project, tmp_path / "proc")


def test_pytest_running_sees_a_pytest_in_a_worktree_of_the_project(tmp_path):
    """Les contre-épreuves de spec-auditor tournent dans .claude/worktrees/."""
    project = tmp_path / "repo"
    worktree = project / ".claude" / "worktrees" / "agent-1"
    worktree.mkdir(parents=True)
    _fake_process(tmp_path / "proc", 4242, ["pytest", "tests/e2e"], worktree)
    assert stop.pytest_running(project, tmp_path / "proc")


def test_pytest_running_ignores_other_projects_and_other_programs(tmp_path):
    project = tmp_path / "repo"
    elsewhere = tmp_path / "repo-voisin"  # même préfixe, autre dossier
    project.mkdir()
    elsewhere.mkdir()
    proc = tmp_path / "proc"
    _fake_process(proc, 1, ["pytest", "-q"], elsewhere)
    _fake_process(proc, 2, ["make", "check"], project)
    _fake_process(proc, 3, ["vim", "tests/test_pytest_x.py"], project)
    (proc / "self").mkdir()  # entrées non numériques de /proc
    (proc / "4").mkdir()  # processus disparu entre la liste et la lecture
    assert not stop.pytest_running(project, proc)


def test_pytest_running_without_proc_says_no(tmp_path):
    assert not stop.pytest_running(tmp_path, tmp_path / "absent")


def test_stop_hook_does_not_run_check_while_a_pytest_runs(tmp_path):
    """Les collisions d'I7 et d'I11 : `make check` lancé pendant un pytest du dépôt."""
    repo = _project(tmp_path, "essai")
    (repo / "Makefile").write_text("check:\n\t@false\n")
    fake = tmp_path / "bin" / "pytest"
    fake.parent.mkdir()
    fake.write_text("sleep 60\n")
    runner = subprocess.Popen(["sh", str(fake)], cwd=repo)
    try:
        result = _run_stop(repo)
        assert result.returncode == 2  # renvoyé attendre la fin, sans fin silencieuse
        assert "Un pytest tourne" in result.stderr
        assert "`make check` échoue" not in result.stderr  # rien n'a été lancé
        assert not stop.marker_path(repo).exists()
    finally:
        runner.kill()
        runner.wait()
    result = _run_stop(repo)  # pytest fini : le contrôle reprend
    assert result.returncode == 2
    assert "make check" in result.stderr


# --- Incrément M : la langue de mes messages, surveillée par hook (dérive d'I11).


@pytest.fixture(scope="module")
def lang():
    return load("language")


@pytest.mark.parametrize(
    "text",
    [
        "The branch exists already, empty, at the same commit as main. I'm switching to it.",
        "The sed didn't apply; I'm rewriting the script properly.",
        "Everything is green (86 tests). I commit these fixes.",
        "Next, `phone.js`, rewritten for ETU-10, ETU-11 and FIN-02.",
        "Code written. I'm running the I11 tests.",
    ],
)
def test_english_messages_are_detected(lang, text):
    """Messages réels de la session d'I11."""
    assert lang.looks_english(text)


@pytest.mark.parametrize(
    "text",
    [
        "J'ai lu la spec d'I11 et le code actuel du téléphone.",
        "Vérification rapide verte. Je relance maintenant les tests E2E touchés (I4, I6, I8, I9).",
        "Le garde-fou refuse le `;` après une vérification : j'écris un script.",
        "Je lance `make check` puis `uv run pytest tests/e2e/test_i5_extra_time.py -k end`.",
        "Constat : the board is ready n'apparaît plus dans `board.html`.",
        "```\nThe output is in English, and that is fine for a tool.\n```\nTout passe.",
        "Plan approuvé.",
        "",
    ],
)
def test_french_messages_are_not_flagged(lang, text):
    assert not lang.looks_english(text)


def _transcript(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _prompt(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _said(text: str, sidechain: bool = False) -> dict:
    content = [{"type": "text", "text": text}]
    return {"type": "assistant", "isSidechain": sidechain, "message": {"content": content}}


def _tool_use(tool_id: str) -> dict:
    content = [{"type": "tool_use", "id": tool_id, "name": "Bash", "input": {}}]
    return {"type": "assistant", "message": {"content": content}}


def _tool_result(tool_id: str) -> dict:
    content = [{"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}]
    return {"type": "user", "message": {"content": content}}


ENGLISH = "The tests pass now. I'm committing the fixes and then opening the PR."
FRENCH = "Les tests passent. Je committe les corrections, puis j'ouvre la PR."


def test_before_tool_reads_the_text_just_before_this_call(lang):
    rows = [_prompt("Go"), _said(ENGLISH), _tool_use("t1"), _tool_result("t1")]
    rows += [_said(FRENCH), _tool_use("t2")]
    assert lang.texts_before_tool(rows, "t2") == [FRENCH]
    assert lang.texts_before_tool(rows, "t1") == [ENGLISH]
    assert lang.texts_before_tool(rows, None) == [FRENCH]  # sans identifiant : le dernier appel


def test_before_tool_warns_once_for_parallel_calls(lang):
    rows = [_prompt("Go"), _said(ENGLISH), _tool_use("t1"), _tool_use("t2")]
    assert lang.texts_before_tool(rows, "t1") == [ENGLISH]
    assert lang.texts_before_tool(rows, "t2") == []


def test_before_tool_says_nothing_about_an_unknown_call(lang):
    """Appel d'un sous-agent : son identifiant n'est pas dans le fil principal."""
    rows = [_prompt("Go"), _said(ENGLISH), _tool_use("t1")]
    assert lang.texts_before_tool(rows, "sous-agent") == []
    assert lang.texts_before_tool(rows, None) == [ENGLISH]


def test_english_thresholds(lang):
    """Deux mots-outils anglais sans français suffisent ; un mélange doit pencher nettement."""
    assert lang.looks_english("Tests pass and it works")
    # « j\u2019ai » (apostrophe typographique) compte comme français : 2 contre 1, pas anglais.
    assert not lang.looks_english("J\u2019ai relu the hooks and settings")
    # 4 mots anglais contre 3 français : pas plus du double, donc pas anglais.
    mixed = "Le hook relit the settings and the hooks are fine, et c'est vert"
    assert not lang.looks_english(mixed)


def test_before_tool_stops_at_an_incoming_message(lang):
    rows = [_said(ENGLISH), _prompt("Go"), _tool_use("t1")]
    assert lang.texts_before_tool(rows, "t1") == []


def test_words_ending_a_sentence_count(lang):
    assert lang.looks_english("Done. All green now.")
    assert not lang.looks_english("Fait. Tout est vert.")


def test_a_meta_row_does_not_open_a_turn(lang):
    """Rappel système, message d'une autre session : ils arrivent au milieu du tour."""
    meta = {**_prompt("Another Claude session sent a message"), "isMeta": True}
    feedback = {**_prompt("Stop hook feedback: Procédure inachevée"), "isMeta": True}
    assert lang.turn_texts([_prompt("Go"), _said(ENGLISH), meta]) == [ENGLISH]
    assert lang.turn_texts([_prompt("Go"), _said(ENGLISH), feedback]) == []


def test_turn_texts_since_the_last_prompt_without_subagents(lang):
    rows = [_prompt("Avant"), _said(ENGLISH), _prompt("Feu vert"), _said(FRENCH)]
    rows += [_tool_use("t1"), _said("Sub-agent report, in English.", sidechain=True)]
    rows += [_tool_result("t1"), _said(FRENCH)]
    assert lang.turn_texts(rows) == [FRENCH, FRENCH]


def test_read_tail_skips_a_cut_line_and_bad_json(lang, tmp_path):
    path = tmp_path / "t.jsonl"
    long_row = _said("x" * 5000)
    path.write_text(json.dumps(long_row) + "\n{pas du json\n" + json.dumps(_said(FRENCH)) + "\n")
    assert lang.read_tail(path, size=200) == [_said(FRENCH)]
    assert lang.read_tail(tmp_path / "absent.jsonl") == []


def _run_language(payload: dict) -> subprocess.CompletedProcess[str]:
    return _run_hook("language", payload)


def test_post_tool_hook_warns_at_once_about_english(tmp_path):
    rows = [_prompt("Feu vert"), _said(ENGLISH), _tool_use("t1")]
    transcript = _transcript(tmp_path / "t.jsonl", rows)
    result = _run_language({"transcript_path": str(transcript), "tool_use_id": "t1"})
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "PostToolUse"
    assert "français" in context["additionalContext"]
    assert "The tests pass now" in context["additionalContext"]


def test_post_tool_hook_stays_silent_in_french(tmp_path):
    rows = [_prompt("Feu vert"), _said(FRENCH), _tool_use("t1")]
    transcript = _transcript(tmp_path / "t.jsonl", rows)
    result = _run_language({"transcript_path": str(transcript), "tool_use_id": "t1"})
    assert (result.returncode, result.stdout) == (0, "")


def test_post_tool_hook_never_fails_on_a_bad_payload():
    assert _run_language({}).returncode == 0
    assert _run_hook("language", None).returncode == 0  # entrée vide
    assert _run_hook("language", [1, 2]).returncode == 0  # JSON qui n'est pas un objet


STOP = {"hook_event_name": "Stop", "stop_hook_active": False}


def test_stop_hook_sends_back_an_english_turn(tmp_path):
    rows = [_prompt("Feu vert"), _said(FRENCH), _tool_use("t1"), _tool_result("t1")]
    rows += [_said(ENGLISH)]
    transcript = _transcript(tmp_path / "t.jsonl", rows)
    payload = {**STOP, "transcript_path": str(transcript)}
    result = _run_hook("language", payload)
    assert result.returncode == 2
    assert "français" in result.stderr
    # Une seule relance par arrêt : le retour du hook entre au journal, puis Claude s'arrête.
    feedback = {**_prompt(f"Stop hook feedback: {result.stderr}"), "isMeta": True}
    _transcript(transcript, [*rows, feedback])
    assert _run_hook("language", {**payload, "stop_hook_active": True}).returncode == 0


def test_stop_hook_reads_the_last_message_not_yet_in_the_transcript(tmp_path):
    """Observé dans une vraie session : au moment du hook Stop, le journal n'a pas encore le
    dernier message ; il n'est que dans `last_assistant_message`."""
    transcript = _transcript(tmp_path / "t.jsonl", [_prompt("Feu vert")])
    payload = {
        **STOP,
        "transcript_path": str(transcript),
        "last_assistant_message": ENGLISH,
    }
    result = _run_hook("language", payload)
    assert result.returncode == 2
    assert "The tests pass now" in result.stderr


def test_stop_hook_does_not_count_the_last_message_twice(lang):
    rows = [_prompt("Feu vert"), _said(ENGLISH)]
    problem = lang.turn_problem(rows, ENGLISH)
    assert problem is not None
    assert "1 message(s)" in problem


def test_stop_hook_checks_the_language_after_another_hook_sent_back(tmp_path):
    """Le retour de `stop_check.py` ouvre un nouveau tour : il est contrôlé quand même."""
    rows = [_prompt("Feu vert"), _prompt("Stop hook feedback: Procédure inachevée")]
    transcript = _transcript(tmp_path / "t.jsonl", rows)
    payload = {**STOP, "stop_hook_active": True, "transcript_path": str(transcript)}
    payload["last_assistant_message"] = ENGLISH
    assert _run_hook("language", payload).returncode == 2


def test_stop_hook_sends_back_once_for_the_language(lang, tmp_path):
    rows = [_prompt("Feu vert"), _prompt(f"Stop hook feedback: {lang.RULE} 1 message(s)")]
    transcript = _transcript(tmp_path / "t.jsonl", rows)
    payload = {**STOP, "stop_hook_active": True, "transcript_path": str(transcript)}
    payload["last_assistant_message"] = ENGLISH
    assert _run_hook("language", payload).returncode == 0


def test_stop_hook_lets_a_french_turn_stop(tmp_path):
    transcript = _transcript(tmp_path / "t.jsonl", [_prompt("Feu vert"), _said(FRENCH)])
    payload = {**STOP, "transcript_path": str(transcript)}
    assert _run_hook("language", payload).returncode == 0


def test_settings_ask_for_french_and_run_the_language_hook():
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["language"] == "french"
    commands = [
        hook["command"] for entry in settings["hooks"]["PostToolUse"] for hook in entry["hooks"]
    ]
    assert any("language.py" in command for command in commands)
    matchers = [
        entry.get("matcher")
        for entry in settings["hooks"]["PostToolUse"]
        if any("language.py" in hook["command"] for hook in entry["hooks"])
    ]
    assert matchers == ["*"]  # après tout outil, pas seulement Bash
    stop = [hook["command"] for entry in settings["hooks"]["Stop"] for hook in entry["hooks"]]
    assert any("language.py" in command for command in stop)


def test_stop_check_ignores_the_language(tmp_path):
    """La langue est une entrée Stop à part : le hook de procédure ne la regarde pas."""
    repo = _project(tmp_path, "essai")
    transcript = _transcript(tmp_path / "t.jsonl", [_prompt("Feu vert"), _said(ENGLISH)])
    payload = {**STOP, "transcript_path": str(transcript), "last_assistant_message": ENGLISH}
    assert _run_hook("stop_check", payload, repo).returncode == 0
