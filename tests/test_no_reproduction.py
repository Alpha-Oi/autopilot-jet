"""Навык не порождает другие экземпляры Autopilot (REQ-COND-01 стандарта DOA: воспроизводство запрещено).

Проверяется то, что проверяется машиной. Первое: скрипты навыка запускают процессы только двух видов —
чтение списка процессов (`ps`, PowerShell) и сервер дашборда (`python -m http.server`). Любой другой запуск,
в том числе командной строки агента, и любой запуск, который не удалось разобрать, красят тест. Второе:
запрет записан в SKILL.md и в обоих промптах субагентов.

Чего здесь нет: инструмент субагентов хоста лежит вне репозитория, и запрет им пользоваться для второго
прогона остаётся инструкцией. Установщик `tools/ship.ps1` вне области: он ставит навык, а не запускает прогон.

Проверка запусков проверена на синтетическом коде: тест, который не умеет краснеть, ничего не доказывает.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
TOOL_DIRS = (ROOT / "skills" / "autopilot-jet" / "tools", ROOT / "tools")
SKILL = ROOT / "skills" / "autopilot-jet" / "SKILL.md"
PROMPTS = (ROOT / "skills" / "autopilot-jet" / "prompts" / "executor.md",
           ROOT / "skills" / "autopilot-jet" / "prompts" / "craft-review.md")

SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}
OS_LAUNCHERS = {"system", "popen", "execv", "execve", "execl", "execle", "execlp", "execvp", "execvpe",
                "spawnl", "spawnle", "spawnlp", "spawnv", "spawnve", "spawnvp", "startfile"}
READ_ONLY_PROGRAMS = {"ps", "powershell"}
GIT_READ_ONLY = {"rev-parse", "diff-tree"}   # git читает коммит и ничего не пишет (sync.py --zone-check)
SERVER = ("python", "-m", "http.server")


def _attribute_name(node):
    """`subprocess.run` -> ("subprocess", "run"); иное -> None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id, node.attr
    return None


def _program(first):
    """Имя программы из первого элемента списка аргументов, без пути и расширения."""
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value.replace("\\", "/").split("/")[-1].split(".")[0].lower()
    if _attribute_name(first) == ("sys", "executable"):
        return "python"
    return None


def _lists_assigned_to(tree, name):
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.List)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]


def launched_commands(source):
    """Все запуски процессов в исходнике: список кортежей (программа, второй, третий аргумент).

    Запуск, который не удалось разобрать (аргументы не литерал и не переменная со списком-литералом,
    `os.system`, `os.exec*`), возвращается как ("?", ...): допускающий список его не пропустит.
    """
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _attribute_name(node.func)
        if callee is None:
            continue
        module, attr = callee
        if module == "os" and attr in OS_LAUNCHERS:
            found.append(("?", "os." + attr, ""))
            continue
        if module != "subprocess" or attr not in SUBPROCESS_CALLS:
            continue
        argument = node.args[0] if node.args else None
        if isinstance(argument, ast.Name):
            candidates = _lists_assigned_to(tree, argument.id)
        elif isinstance(argument, ast.List):
            candidates = [argument]
        else:
            candidates = []
        if not candidates:
            found.append(("?", "subprocess." + attr, ""))
        for candidate in candidates:
            elts = candidate.elts or [None]
            words = [elt.value if isinstance(elt, ast.Constant) and isinstance(elt.value, str) else "" for elt in elts[1:3]]
            found.append((_program(elts[0]) or "?", *(words + ["", ""])[:2]))
    return found


def disallowed(source):
    """Запуски, которых нет в списке допустимых."""
    return [command for command in launched_commands(source)
            if command[0] not in READ_ONLY_PROGRAMS and command != SERVER
            and not (command[0] == "git" and command[1] in GIT_READ_ONLY)]


def lacks_ban(text, marker):
    return marker not in text


def product_sources():
    for directory in TOOL_DIRS:
        for path in sorted(directory.glob("*.py")):
            yield path, path.read_text(encoding="utf-8")


class CheckerCanTurnRed(unittest.TestCase):
    def test_allowed_launches_pass(self):
        source = (
            "import subprocess, sys\n"
            "argv = ['ps', '-Ao', 'pid=']\n"
            "if nt:\n    argv = ['powershell.exe', '-NoProfile']\n"
            "subprocess.run(argv)\n"
            "subprocess.Popen([sys.executable, '-m', 'http.server', '8000'])\n"
        )
        self.assertEqual(sorted(launched_commands(source)),
                         sorted([("ps", "-Ao", "pid="), ("powershell", "-NoProfile", ""),
                                 ("python", "-m", "http.server")]))
        self.assertEqual(disallowed(source), [])

    def test_an_agent_command_line_is_found(self):
        for program in ("claude", "/usr/local/bin/codex", "gemini.cmd"):
            with self.subTest(program=program):
                found = disallowed("import subprocess\nsubprocess.run(['%s', '-p', 'go'])\n" % program)
                self.assertEqual(len(found), 1)
                self.assertNotIn(found[0][0], READ_ONLY_PROGRAMS)

    def test_git_may_read_a_commit_and_nothing_else(self):
        read = ("import subprocess\nsubprocess.run(['git', 'rev-parse', '--show-prefix'])\n"
                "subprocess.run(['git', 'diff-tree', '--name-only', commit])\n")
        self.assertEqual(disallowed(read), [])
        for verb in ("commit", "push", "reset", "checkout", "add", "clean", "rm", "merge", "rebase", "config", "diff", "-C"):
            with self.subTest(verb=verb):
                found = disallowed("import subprocess\nsubprocess.run(['git', '%s', 'x'])\n" % verb)
                self.assertEqual([command[:2] for command in found], [("git", verb)])

    def test_a_git_launch_without_a_literal_verb_is_found(self):
        self.assertEqual(len(disallowed("import subprocess\nsubprocess.run(['git'])\n")), 1)
        self.assertEqual(len(disallowed("import subprocess\nsubprocess.run(['git', verb])\n")), 1)

    def test_the_skill_itself_is_not_an_allowed_server_argument(self):
        self.assertEqual(len(disallowed("import subprocess, sys\nsubprocess.run([sys.executable, 'autopilot.py'])\n")), 1)
        self.assertEqual(len(disallowed("import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pip'])\n")), 1)

    def test_a_launch_that_cannot_be_read_is_found(self):
        for source in ("import subprocess\nsubprocess.run(cmd)\n",
                       "import subprocess\nsubprocess.Popen(build())\n",
                       "import subprocess\nsubprocess.run('claude -p go', shell=True)\n",
                       "import os\nos.system('claude')\n",
                       "import os\nos.execvp('claude', ['claude'])\n"):
            with self.subTest(source=source):
                self.assertEqual([command[0] for command in disallowed(source)], ["?"])

    def test_code_without_launches_is_silent(self):
        self.assertEqual(launched_commands("import os\nprint(os.getcwd())\n"), [])

    def test_a_missing_ban_is_found(self):
        self.assertTrue(lacks_ban("# Исполнитель\n", "Второй прогон не открывать"))
        self.assertFalse(lacks_ban("## Второй прогон не открывать\n", "Второй прогон не открывать"))


class ToolsLaunchOnlyAllowedProcesses(unittest.TestCase):
    def test_there_are_tools_to_check(self):
        names = [path.name for path, _source in product_sources()]
        self.assertIn("sync.py", names)
        self.assertIn("redact.py", names)

    def test_sync_launches_what_it_is_expected_to(self):
        source = (TOOL_DIRS[0] / "sync.py").read_text(encoding="utf-8")
        programs = {command[0] for command in launched_commands(source)}
        self.assertEqual(programs, {"ps", "powershell", "python", "git"})

    def test_no_tool_launches_anything_else(self):
        for path, source in product_sources():
            with self.subTest(tool=path.name):
                self.assertEqual(disallowed(source), [])


class TheBanIsWritten(unittest.TestCase):
    def test_skill_states_the_ban(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertFalse(lacks_ban(text, "## Autopilot does not start Autopilot"))
        self.assertFalse(lacks_ban(text, "tests/test_no_reproduction.py"))

    def test_both_subagent_prompts_carry_it(self):
        for path in PROMPTS:
            with self.subTest(prompt=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertFalse(lacks_ban(text, "Не запускай `/autopilot-jet`"))


if __name__ == "__main__":
    unittest.main()
