"""В репозиторий не попадают файлы, которые делает запуск, а не человек (находка при подготовке релиза 1.5.1, 2026-10-06).

В #87 вместе с исправлением ушёл `skills/autopilot-jet/tools/serve.pid` («8123 1»): запись о сервере страницы прогресса,
оставшаяся от запуска рядом с `sync.py`. Он ставится вместе с навыком и сбивает с толку. Откуда он взялся, точно не
установлено: полный набор тестов и каждый модуль по отдельности его теперь не создают. Поэтому защита двойная: `.gitignore`
и этот тест, который смотрит на то, что реально лежит под git (`git ls-files`).

Проверка проверена нарочной поломкой: тест, который не умеет краснеть, ничего не доказывает.
"""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).parents[1]
RUN_ARTIFACTS = ("serve.pid", "serve.log")


def tracked():
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                            check=False)
    if result.returncode != 0:
        raise unittest.SkipTest("не git-копия: нечего проверять")
    return result.stdout.splitlines()


def stray(paths):
    return [path for path in paths if path.rsplit("/", 1)[-1] in RUN_ARTIFACTS or path.endswith((".pyc", ".pid"))]


class RunArtifactsAreNotTracked(unittest.TestCase):
    def test_the_checker_names_what_it_should(self):
        for path in ("skills/autopilot-jet/tools/serve.pid", "serve.log", "a/b/serve.pid", "x/__pycache__/m.cpython-311.pyc",
                     "tools/other.pid"):
            with self.subTest(path=path):
                self.assertEqual(stray([path]), [path])

    def test_the_checker_leaves_ordinary_files_alone(self):
        for path in ("skills/autopilot-jet/tools/sync.py", "docs/serve.md", "tests/test_sync.py", "README.md"):
            with self.subTest(path=path):
                self.assertEqual(stray([path]), [])

    def test_nothing_under_git_is_a_run_artifact(self):
        self.assertEqual(stray(tracked()), [])

    def test_gitignore_keeps_the_pid_file_out(self):
        self.assertIn("serve.pid", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    unittest.main()
