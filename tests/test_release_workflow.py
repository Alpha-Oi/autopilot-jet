"""Релиз ставит GitHub Actions: `tools/release.py` и `.github/workflows/release.yml`.

У агента нет права ставить теги и создавать релизы в этой среде, а ручной релиз однажды встал на не тот
коммит. Теперь после слияния в `main` workflow берёт версию и описание из верхнего выпущенного раздела
`CHANGELOG.md` и создаёт тег и релиз, если такого тега ещё нет. Здесь проверяется разбор журнала (в том числе
настоящий `CHANGELOG.md` репозитория: правка журнала не должна молча сломать выпуск) и то, что workflow
остаётся узким: один триггер, права только на запись содержимого, действия закреплены по SHA, ничего из
события не подставляется в команды.

Это проверка текста workflow, а не его запуска: что GitHub выполнит его так, как написано, подтверждает только
первый настоящий релиз. Тесты умеют краснеть: каждая проверка проверена на испорченном тексте.
"""

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tools" / "release.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
SPEC = importlib.util.spec_from_file_location("autopilot_release", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

LOG = """# История изменений

## [Unreleased]

### Добавлено

- ещё не выпущено

## [1.10.2] — 2026-10-02

### Исправлено

- свежее

## [1.9.0] — 2026-09-29

- прежнее
"""


class SectionTests(unittest.TestCase):
    def test_the_first_released_section_wins_and_unreleased_is_skipped(self):
        version, body = release.latest_section(LOG)
        self.assertEqual(version, "1.10.2")
        self.assertEqual(body, "### Исправлено\n\n- свежее")

    def test_a_ten_is_not_smaller_than_a_nine(self):
        # порядок берётся из журнала (сверху вниз), а не сравнением строк
        self.assertEqual(release.latest_section(LOG)[0], "1.10.2")

    def test_the_date_is_optional(self):
        self.assertEqual(release.latest_section("## [2.0.0]\n\n- x\n"), ("2.0.0", "- x"))

    def test_the_body_stops_at_the_next_heading(self):
        body = release.latest_section(LOG)[1]
        self.assertNotIn("прежнее", body)
        self.assertNotIn("1.9.0", body)

    def test_the_last_section_runs_to_the_end_of_the_file(self):
        self.assertEqual(release.latest_section("## [1.0.0] — 2026-01-01\n\n- первый\n- второй\n")[1],
                         "- первый\n- второй")

    def test_windows_line_endings_are_the_same_text(self):
        version, body = release.latest_section(LOG.replace("\n", "\r\n"))
        self.assertEqual((version, body), ("1.10.2", "### Исправлено\n\n- свежее"))

    def test_only_a_strict_heading_is_a_version(self):
        for heading in ("## [1.3.0-rc1]", "## [1.3]", "## [v1.3.0]", "### [1.3.0]", "## 1.3.0", "## [1.3.0] 2026-10-02",
                        "## [1.3.0] — 02.10.2026", " ## [1.3.0]", "## [1.3.0] — 2026-10-02 extra"):
            with self.subTest(heading=heading):
                self.assertIsNone(release.latest_section(heading + "\n\n- x\n")[0])

    def test_a_log_without_a_released_section_is_not_a_release(self):
        for text in ("", "# История\n", "## [Unreleased]\n\n- x\n"):
            with self.subTest(text=text):
                version, why = release.latest_section(text)
                self.assertIsNone(version)
                self.assertIn("нет раздела", why)

    def test_an_empty_section_is_not_released(self):
        version, why = release.latest_section("## [1.0.0] — 2026-01-01\n\n\n## [0.9.0]\n\n- x\n")
        self.assertIsNone(version)
        self.assertIn("пуст", why)

    def test_the_limit_stays_below_what_github_accepts(self):
        self.assertLessEqual(release.LIMIT, 125000)
        self.assertGreaterEqual(release.LIMIT, 100000)

    def test_a_section_too_long_for_a_github_release_is_not_released(self):
        version, why = release.latest_section("## [1.0.0]\n\n" + "x" * (release.LIMIT + 1) + "\n")
        self.assertIsNone(version)
        self.assertIn("длиннее", why)
        self.assertEqual(release.latest_section("## [1.0.0]\n\n" + "x" * release.LIMIT + "\n")[0], "1.0.0")


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)

    def log(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(os.unlink, handle.name)
        handle.write(text)
        handle.close()
        return handle.name

    def test_version_prints_the_number_only(self):
        result = self.run_cli("version", self.log(LOG))
        self.assertEqual((result.returncode, result.stdout), (0, "1.10.2\n"))

    def test_notes_prints_the_body(self):
        result = self.run_cli("notes", self.log(LOG))
        self.assertEqual((result.returncode, result.stdout), (0, "### Исправлено\n\n- свежее\n"))

    def test_a_log_with_nothing_to_release_exits_one_and_prints_nothing_on_stdout(self):
        for mode in ("version", "notes"):
            with self.subTest(mode=mode):
                result = self.run_cli(mode, self.log("## [Unreleased]\n\n- x\n"))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("нет раздела", result.stderr)

    def test_a_missing_log_exits_one(self):
        self.assertEqual(self.run_cli("version", str(ROOT / "нет-такого.md")).returncode, 1)

    def test_a_wrong_call_exits_two(self):
        for args in ((), ("tag",), ("version", "a", "b")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)

    def test_the_default_log_is_the_one_in_the_repository(self):
        result = self.run_cli("version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^\d+\.\d+\.\d+$")


class TheRepositoryLogCanBeReleased(unittest.TestCase):
    """Правка CHANGELOG.md не должна тихо сломать выпуск."""

    def test_the_top_released_section_has_a_version_a_body_and_fits_the_limit(self):
        version, body = release.latest_section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertRegex(version or "", r"^\d+\.\d+\.\d+$")
        self.assertTrue(body)
        self.assertLessEqual(len(body), release.LIMIT)

    def test_the_version_is_the_first_released_heading_of_the_file(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M).group(1)
        self.assertEqual(release.latest_section(text)[0], first)


class TheWorkflowStaysNarrow(unittest.TestCase):
    def text(self):
        return WORKFLOW.read_text(encoding="utf-8")

    def test_it_runs_only_on_a_push_to_main(self):
        text = self.text()
        self.assertRegex(text, r"(?m)^on:\n  push:\n    branches: \[main\]\n")
        for banned in ("pull_request", "pull_request_target", "workflow_run", "workflow_dispatch", "issue_comment",
                       "schedule"):
            with self.subTest(trigger=banned):
                self.assertNotIn(banned, text)

    def test_the_only_permission_is_writing_contents_and_only_in_the_job(self):
        text = self.text()
        self.assertRegex(text, r"(?m)^permissions: \{\}$")
        self.assertEqual(re.findall(r"(?m)^\s+([a-z-]+): (read|write|none)$", text), [("contents", "write")])
        self.assertRegex(text, r"(?m)^    permissions:\n      contents: write$")

    def test_every_action_is_pinned_to_a_full_commit(self):
        uses = re.findall(r"(?m)^\s*uses: (\S+)", self.text())
        self.assertTrue(uses)
        for ref in uses:
            with self.subTest(uses=ref):
                self.assertRegex(ref, r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

    def test_nothing_from_the_event_is_put_into_a_command(self):
        text = self.text()
        expressions = re.findall(r"\$\{\{\s*([^}]*?)\s*\}\}", text)
        self.assertEqual(expressions, ["github.token"])
        self.assertNotIn("github.event", text)
        self.assertNotIn("github.head_ref", text)

    def test_the_description_goes_through_a_file_not_through_the_shell(self):
        text = self.text()
        self.assertIn("--notes-file", text)
        self.assertNotIn("--notes ", text)

    def test_an_existing_tag_stops_it_before_anything_is_created(self):
        text = self.text()
        check = text.index("git/ref/tags/v${VERSION}")
        stop = text.index("exit 0")
        create = text.index("gh release create")
        self.assertLess(check, stop)
        self.assertLess(stop, create)

    def test_the_release_is_made_on_the_pushed_commit(self):
        self.assertIn('--target "${GITHUB_SHA}"', self.text())

    def test_the_version_comes_from_the_script_and_a_failing_script_stops_the_job(self):
        text = self.text()
        self.assertIn('version="$(python3 tools/release.py version)"', text)
        self.assertIn("python3 tools/release.py notes >", text)

    def test_two_releases_do_not_run_at_once_and_none_is_cancelled(self):
        text = self.text()
        self.assertIn("group: release", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_the_trigger_and_the_rule_are_written_in_contributing(self):
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("release.yml", text)
        self.assertIn("CHANGELOG.md", text)


if __name__ == "__main__":
    unittest.main()
