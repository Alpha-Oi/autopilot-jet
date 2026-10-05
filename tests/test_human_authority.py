"""Необратимое и внешнее остаётся вопросом человеку (REQ-CORE-12 стандарта DOA: власть человека).

Правило четыре из пяти правил `SKILL.md`: деплой, публикация, платёж, сообщение третьему лицу, удаление данных,
переписывание истории — вопрос в любом режиме. Правило по-прежнему инструкция для модели, технического шлюза
согласия в навыке нет. Здесь проверяется то, что проверяется машиной:
  - перечень действий записан одинаково там, где он нужен (`SKILL.md`, `phases/0-modes.md`), и оба места говорят, что
    ни один режим его не снимает; обе роли субагентов (`prompts/`) получили то же правило;
  - в инструкциях навыка нет шага, который сам велит выполнить необратимое или внешнее действие: каждая строка с
    такой командой (`git push`, `reset --hard`, `npm publish`, `rm -rf`, `curl -X POST` и подобные) стоит рядом с
    запретом; сканер сам проверен на синтетических строках в обе стороны;
  - скрипты навыка запускают git только для чтения: перечень `GIT_READ_ONLY` из `test_no_reproduction.py` не
    содержит ни одной команды, которая меняет репозиторий.

Чего здесь нет: что модель спрашивает и не действует молча, этот тест не видит. Шлюза согласия, срока действия
разрешения и записи согласия нет; сканер ищет известные команды и не находит перефразированное или собранное из
частей. Установщик `tools/ship.ps1` вне области: он принадлежит владельцу репозитория и запускается им, а не прогоном.

Проверка проверена нарочными поломками: тест, который не умеет краснеть, ничего не доказывает.
"""

import importlib.util
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "autopilot-jet"
SKILL_MD = SKILL / "SKILL.md"
MODES = SKILL / "phases" / "0-modes.md"
PROMPTS = (SKILL / "prompts" / "executor.md", SKILL / "prompts" / "craft-review.md")
INSTRUCTIONS = [SKILL_MD, *sorted((SKILL / "phases").glob("*.md")), *sorted((SKILL / "prompts").glob("*.md"))]

# Перечень из правила четыре: действие -> как оно названо в английских инструкциях.
ACTIONS = {
    "deploy": r"\bdeploy",
    "publish": r"\bpublish",
    "pay": r"\bpay\b",
    "message": r"\bmessage|\bsend messages",
    "delete": r"\bdelete",
    "rewrite": r"\brewrit\w* (?:git )?history",
}

# Команды, которые делают необратимое или внешнее. Не весь мир: то, что чаще всего ловится в агентских сценариях.
RISKY = re.compile(
    r"git\s+push|push\s+--force|push\s+-f\b|--force-with-lease|reset\s+--hard|git\s+clean\s+-\w*f|rm\s+-\w*r\w*f|rm\s+-\w*f\w*r"
    r"|git\s+branch\s+-D|git\s+rebase|npm\s+publish|twine\s+upload|docker\s+push|gh\s+release|gh\s+pr\s+merge"
    r"|netlify\s+deploy|vercel\s+--prod|fly\s+deploy|kubectl\s+(?:apply|delete)|terraform\s+apply"
    r"|curl\b[^\n]*-X\s*(?:POST|PUT|DELETE|PATCH)|force-push|force push",
    re.I)
NEGATION = re.compile(r"\bnever\b|\bdo not\b|\bdon't\b|\bnot\b|\bno\b|\bwithout\b|\bне\b|\bникогда\b|\bнельзя\b|\bбез\b", re.I)

WRITE_VERBS = {"push", "commit", "reset", "clean", "checkout", "switch", "rm", "revert", "merge", "rebase", "tag",
               "branch", "add", "stash", "cherry-pick", "apply", "am", "pull", "fetch", "clone", "init", "remote"}


def unguarded(text):
    """Строки с рискованной командой, рядом с которыми (та же строка) нет запрета. Пусто — всё под запретом."""
    return [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1)
            if RISKY.search(line) and not NEGATION.search(line)]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActionListTests(unittest.TestCase):
    def line(self, path, marker):
        text = path.read_text(encoding="utf-8")
        found = [line for line in text.splitlines() if marker in line]
        self.assertEqual(len(found), 1, "%s: %r" % (path.name, marker))
        return found[0]

    def test_the_rule_names_every_action_in_skill_md(self):
        line = self.line(SKILL_MD, "An irreversible or outward-facing action is a question")
        for action, pattern in ACTIONS.items():
            with self.subTest(action=action):
                self.assertRegex(line, pattern)

    def test_the_modes_file_names_every_action_and_says_all_four_modes(self):
        line = self.line(MODES, "No mode removes the manifest gates or the safety gates")
        for action, pattern in ACTIONS.items():
            with self.subTest(action=action):
                self.assertRegex(line, pattern)
        self.assertIn("**all four** modes", line)
        self.assertIn("including full", line)

    def test_skill_md_says_the_five_rules_hold_in_every_mode(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("**Five rules are not calibration and do not lose.** They hold in every mode, at every depth, at every tier", text)

    def test_only_the_user_removes_a_requirement(self):
        self.assertIn("**A requirement is removed only by the user**", SKILL_MD.read_text(encoding="utf-8"))

    def test_both_subagent_prompts_carry_the_rule(self):
        for path in PROMPTS:
            with self.subTest(prompt=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Необратимое и внешнее — только вопросом", text)
                for word in ("деплой", "публикац", "платёж", "третьему лицу", "удаление", "переписывание истории"):
                    self.assertIn(word, text)

    def test_the_executor_returns_a_question_not_an_action(self):
        text = PROMPTS[0].read_text(encoding="utf-8")
        self.assertIn("верни `BLOCKED` с одним вопросом пользователю", text)

    def test_the_reviewer_changes_nothing_and_flags_the_question(self):
        text = PROMPTS[1].read_text(encoding="utf-8")
        self.assertIn("Ревьюер ничего не меняет в проекте и не делает ничего внешнего", text)
        self.assertIn("одной строкой `ВНИМАНИЕ:` с вопросом пользователю", text)


class ScannerTests(unittest.TestCase):
    def test_a_risky_command_without_a_prohibition_is_found(self):
        for line in ("Then run `git push origin main`.", "Finish with `npm publish`.", "run git reset --hard HEAD~1",
                     "`rm -rf build/`", "curl -X POST https://example.invalid/hook", "git push --force-with-lease",
                     "Close it with gh pr merge 5", "kubectl apply -f deploy.yaml", "force-push the branch"):
            with self.subTest(line=line):
                self.assertEqual(len(unguarded(line)), 1)

    def test_the_same_commands_next_to_a_prohibition_pass(self):
        for line in ("Never `git push` from a ticket.", "do not run git reset --hard", "Не выполняй `git push`.",
                     "без `rm -rf`", "the revert is never `git reset --hard`"):
            with self.subTest(line=line):
                self.assertEqual(unguarded(line), [])

    def test_the_line_number_is_reported(self):
        self.assertEqual(unguarded("ok\nrun git push\nok")[0][0], 2)

    def test_harmless_lines_pass(self):
        self.assertEqual(unguarded("git status and git log are read only\nrun the tests\n"), [])


class InstructionScanTests(unittest.TestCase):
    def test_the_scan_has_files_to_read(self):
        self.assertGreaterEqual(len(INSTRUCTIONS), 17)

    def test_no_instruction_orders_an_irreversible_or_outward_command(self):
        found = {path.name: unguarded(path.read_text(encoding="utf-8")) for path in INSTRUCTIONS}
        self.assertEqual({name: rows for name, rows in found.items() if rows}, {})

    def test_the_one_place_that_names_a_destructive_command_forbids_it(self):
        polish = (SKILL / "phases" / "polish.md").read_text(encoding="utf-8")
        hits = [line for line in polish.splitlines() if RISKY.search(line)]
        self.assertTrue(hits)
        for line in hits:
            self.assertRegex(line, r"never|do not|Do not")


class ToolsAreReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.reproduction = load(ROOT / "tests" / "test_no_reproduction.py", "reproduction_for_authority")

    def test_the_git_allow_list_has_no_verb_that_changes_the_repository(self):
        self.assertTrue(self.reproduction.GIT_READ_ONLY)
        self.assertEqual(set(self.reproduction.GIT_READ_ONLY) & WRITE_VERBS, set())

    def test_every_git_call_in_the_skill_tools_is_on_the_allow_list(self):
        seen = []
        for path in sorted((SKILL / "tools").glob("*.py")):
            for command in self.reproduction.launched_commands(path.read_text(encoding="utf-8")):
                if command[0] == "git":
                    seen.append(command[1])
        self.assertTrue(seen)
        self.assertEqual(set(seen) - set(self.reproduction.GIT_READ_ONLY), set())


if __name__ == "__main__":
    unittest.main()
