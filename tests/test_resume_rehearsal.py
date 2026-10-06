"""Потеря рабочей копии: прогон возобновляется с того, что закоммичено (F-24 катастрофическая потеря, класс отказов DOA).

Фаза 0 (`phases/0-preflight.md`, шаг 6) пишет `.gitignore` и говорит, что `.autopilot/` не игнорируется: запись
прогона лежит в git, и по ней возобновляют, а пока `finishedAt` пуст, это возобновление, а не новый прогон.
Здесь это репетируется на настоящем git: берётся блок `.gitignore` прямо из фазы, строится репозиторий с записью
прогона, коммитится, «машина теряется» (свежий `git clone` без рабочей копии), и `sync.py --run-status` из навыка
называет состояние по тому, что дошло до клона.

Что репетиция говорит, и чего не говорит:
  - дошло до клона только закоммиченное; правка `state.js` после последнего коммита потеряна (так и записано);
  - машинное (`serve.pid`, `serve.log`) не коммитится и в клон не попадает: оно описывает ту машину;
  - потеря самого репозитория (нет ни рабочей копии, ни удалённого) вне границы: тест её не лечит и не изображает.
Контрольный опыт: с `.autopilot/` в `.gitignore` запись до клона не доходит и вердикт `none`. Без него тест не
доказывал бы, что именно запись в git спасает возобновление.

Проверка проверена нарочными поломками: тест, который не умеет краснеть, ничего не доказывает.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "autopilot-jet"
SYNC = SKILL / "tools" / "sync.py"
PREFLIGHT = SKILL / "phases" / "0-preflight.md"
RUN_DIR = "2026-10-05-feature--wip"


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                           *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=check)


def gitignore_block():
    """Блок `.gitignore` из шага 6 фазы 0: первый кодовый блок после слов про `.gitignore`."""
    text = PREFLIGHT.read_text(encoding="utf-8")
    start = text.index("Write `.gitignore`")
    match = re.search(r"```\n(.*?)\n```", text[start:], re.S)
    return match.group(1)


def now():
    return datetime.now(timezone.utc).isoformat()


def run_state(**extra):
    state = {"dir": RUN_DIR, "finishedAt": None, "updatedAt": now(),
             "stages": [{"id": "build", "status": "active", "startedAt": now()}],
             "tickets": [{"id": "01", "status": "done", "startedAt": now(), "finishedAt": now()},
                         {"id": "02", "status": "in-progress", "startedAt": now()}]}
    state.update(extra)
    return state


def write_state(project, state):
    path = project / ".autopilot" / "state.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")


class Rehearsal(unittest.TestCase):
    ignore = None   # None: блок из фазы

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="resume rehearsal ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(os.path.realpath(self.tmp.name))
        self.project = self.base / "project"
        self.project.mkdir()
        git(self.project, "init", "-q")
        (self.project / ".gitignore").write_text((self.ignore or gitignore_block()) + "\n", encoding="utf-8")

    def commit_run(self, state):
        write_state(self.project, state)
        (self.project / ".autopilot" / "serve.pid").write_text("4242\n", encoding="utf-8")
        (self.project / ".autopilot" / "serve.log").write_text("serving\n", encoding="utf-8")
        (self.project / ".autopilot" / RUN_DIR).mkdir(parents=True, exist_ok=True)
        (self.project / ".autopilot" / RUN_DIR / "manifest.md").write_text("# manifest\n", encoding="utf-8")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "ticket 01")

    def lose_the_machine(self):
        clone = self.base / "after the loss"
        git(self.base, "clone", "-q", str(self.project), str(clone))
        return clone

    def verdict(self, clone, mode="--run-status"):
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SYNC), mode, str(clone / ".autopilot")],
                                capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
        return result.returncode, result.stdout.split(" · ")[0].strip()


class CommittedRunSurvivesTests(Rehearsal):
    def test_the_phase_block_keeps_the_record_and_drops_the_machine_marks(self):
        self.commit_run(run_state())
        tracked = git(self.project, "ls-files").stdout.split()
        self.assertIn(".autopilot/state.js", tracked)
        self.assertIn(".autopilot/%s/manifest.md" % RUN_DIR, tracked)
        self.assertNotIn(".autopilot/serve.pid", tracked)
        self.assertNotIn(".autopilot/serve.log", tracked)

    def test_an_open_run_is_resumable_after_the_loss(self):
        self.commit_run(run_state())
        clone = self.lose_the_machine()
        self.assertTrue((clone / ".autopilot" / "state.js").is_file())
        self.assertEqual(self.verdict(clone), (0, "open"))

    def test_the_clone_has_no_machine_marks_and_so_no_other_window(self):
        self.commit_run(run_state())
        clone = self.lose_the_machine()
        self.assertFalse((clone / ".autopilot" / "serve.pid").exists())
        self.assertEqual(self.verdict(clone, "--other-window"), (0, "resume"))

    def test_what_survives_is_the_record_of_the_last_commit(self):
        self.commit_run(run_state())
        later = run_state()
        later["tickets"][1]["status"] = "done"
        write_state(self.project, later)               # правка без коммита
        clone = self.lose_the_machine()
        text = (clone / ".autopilot" / "state.js").read_text(encoding="utf-8")
        recorded = json.loads(text.split("=", 1)[1])
        self.assertEqual([t["status"] for t in recorded["tickets"]], ["done", "in-progress"])

    def test_a_closed_run_is_not_resumed_after_the_loss(self):
        self.commit_run(run_state(dir="2026-10-05-feature", finishedAt=now(), stages=[
            {"id": "final", "status": "done", "startedAt": now(), "finishedAt": now()}],
            tickets=[{"id": "01", "status": "done", "startedAt": now(), "finishedAt": now()}]))
        clone = self.lose_the_machine()
        self.assertEqual(self.verdict(clone), (1, "closed"))

    def test_an_old_open_run_after_the_loss_asks_a_human(self):
        self.commit_run(run_state(updatedAt="2026-01-01T00:00:00+00:00"))
        clone = self.lose_the_machine()
        self.assertEqual(self.verdict(clone), (3, "stale"))


class ControlTests(Rehearsal):
    ignore = ".env\nnode_modules/\n.autopilot/\n"

    def test_with_the_run_dir_ignored_nothing_reaches_the_clone(self):
        self.commit_run(run_state())
        clone = self.lose_the_machine()
        self.assertFalse((clone / ".autopilot" / "state.js").exists())
        self.assertEqual(self.verdict(clone), (0, "none"))


class InstructionTests(unittest.TestCase):
    def setUp(self):
        self.text = PREFLIGHT.read_text(encoding="utf-8")

    def test_the_block_ignores_only_the_machine_marks_of_the_run_dir(self):
        lines = gitignore_block().splitlines()
        self.assertIn(".autopilot/serve.*", lines)
        self.assertFalse([line for line in lines if line.strip().rstrip("/") in (".autopilot", "/.autopilot", ".autopilot/*")])

    def test_the_phase_says_the_run_dir_is_not_ignored(self):
        self.assertIn("`.autopilot/` is **not** ignored", self.text)

    def test_the_phase_resumes_on_an_empty_finishedAt(self):
        self.assertIn("`.autopilot/state.js` exists with `finishedAt` still `null` → this is a resume", self.text)


if __name__ == "__main__":
    unittest.main()
