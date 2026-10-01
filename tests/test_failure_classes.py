"""Таблица классов отказов не расходится с кодом и с claim (REQ-CORE-23 стандарта DOA).

docs/conformance/DOA_FAILURE_CLASSES.md называет для каждого из 25 классов F-01…F-25 статус и тесты.
Здесь проверяется то, что проверяется машиной: каждый класс есть ровно один раз; названные тесты
существуют; у PARTIAL есть хотя бы один тест; у EXCLUDED, DESIGNED и FAIL сказано, почему; статусы
совпадают со списком failure_classes в claim.

PyYAML в проекте нет (только стандартная библиотека), поэтому список в claim читается построчно:
нужны только id и status. Разборщики проверены на синтетическом тексте: тест, который не умеет
краснеть, ничего не доказывает.
"""

import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[1]
TABLE = ROOT / "docs" / "conformance" / "DOA_FAILURE_CLASSES.md"
CLAIM = ROOT / "docs" / "conformance" / "DOA_CONFORMANCE_CLAIM.yaml"
CLASS_IDS = ["F-%02d" % number for number in range(1, 26)]
STATUSES = {"PASS", "PARTIAL", "FAIL", "EXCLUDED", "NOT_ASSESSED", "DESIGNED"}
TEST_REF = re.compile(r"`(tests/[\w./]+\.py)::(\w+)::(\w+)`")
ROW = re.compile(r"^\| (F-\d{2}) \|")


def parse_table(text):
    """Строки таблицы: id -> (status, последняя ячейка). Строка с неверным числом ячеек — ошибка."""
    rows = {}
    for line in text.splitlines():
        if ROW.match(line):
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            if len(cells) != 7:
                raise ValueError("строка %s: %d ячеек вместо 7" % (cells[0], len(cells)))
            if cells[0] in rows:
                raise ValueError("класс %s встречается дважды" % cells[0])
            rows[cells[0]] = (cells[2], cells[6])
    return rows


def parse_claim_classes(text):
    """id -> status из блока failure_classes в claim (только простые строки «ключ: значение»)."""
    classes, current, inside = {}, None, False
    for line in text.splitlines():
        if line.startswith("failure_classes:"):
            inside = True
            continue
        if inside and line and not line.startswith((" ", "-")):
            break
        if not inside:
            continue
        item = re.match(r"- id: (\S+)", line)
        if item:
            current = item.group(1)
            classes[current] = None
        elif current and (status := re.match(r"  status: (\S+)", line)):
            classes[current] = status.group(1)
    return classes


def test_exists(path, class_name, test_name):
    file = ROOT / path
    if not file.is_file():
        return False
    for node in ast.parse(file.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(isinstance(item, ast.FunctionDef) and item.name == test_name for item in node.body)
    return False


class ParsersCanTurnRed(unittest.TestCase):
    ROWS = (
        "| ID | Class | Status | D | C | R | Tests |\n|---|---|---|---|---|---|---|\n"
        "| F-01 | A | PARTIAL | d | c | r | `tests/a.py::C::test_x` |\n"
        "| F-02 | B | DESIGNED | d | c | r | Gap: prose. |\n"
    )

    def test_table_rows_are_read(self):
        self.assertEqual(parse_table(self.ROWS),
                         {"F-01": ("PARTIAL", "`tests/a.py::C::test_x`"), "F-02": ("DESIGNED", "Gap: prose.")})

    def test_a_duplicate_or_short_row_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_table(self.ROWS + "| F-01 | A | PARTIAL | d | c | r | t |\n")
        with self.assertRaises(ValueError):
            parse_table("| F-01 | A | PARTIAL | d |\n")

    def test_claim_classes_are_read_and_the_block_ends_at_the_next_key(self):
        text = ("scope: x\nfailure_classes:\n- id: F-01\n  status: PARTIAL\n  component: c\n"
                "  evidence_ref: https://x/a;\n    https://x/b\n- id: F-02\n  status: EXCLUDED\n"
                "  justification: 'no'\nassessor: me\n- id: F-99\n  status: PASS\n")
        self.assertEqual(parse_claim_classes(text), {"F-01": "PARTIAL", "F-02": "EXCLUDED"})

    def test_a_claim_without_the_block_gives_nothing(self):
        self.assertEqual(parse_claim_classes("scope: x\nassessor: me\n"), {})

    def test_test_references_are_checked_against_the_files(self):
        self.assertTrue(test_exists("tests/test_failure_classes.py", "ParsersCanTurnRed",
                                    "test_table_rows_are_read"))
        self.assertFalse(test_exists("tests/test_failure_classes.py", "ParsersCanTurnRed", "test_nope"))
        self.assertFalse(test_exists("tests/test_failure_classes.py", "NoSuchClass", "test_x"))
        self.assertFalse(test_exists("tests/no_such_file.py", "C", "test_x"))


class TableMatchesTheRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = parse_table(TABLE.read_text(encoding="utf-8"))

    def test_every_class_appears_exactly_once(self):
        self.assertEqual(sorted(self.rows), CLASS_IDS)

    def test_statuses_are_known(self):
        for class_id, (status, _last) in self.rows.items():
            with self.subTest(class_id=class_id):
                self.assertIn(status, STATUSES)

    def test_every_named_test_exists(self):
        for class_id, (_status, last) in self.rows.items():
            for path, class_name, test_name in TEST_REF.findall(last):
                with self.subTest(class_id=class_id, test=test_name):
                    self.assertTrue(test_exists(path, class_name, test_name),
                                    "%s: нет теста %s::%s::%s" % (class_id, path, class_name, test_name))

    def test_partial_names_a_test_and_the_others_say_why(self):
        for class_id, (status, last) in self.rows.items():
            with self.subTest(class_id=class_id, status=status):
                if status == "PARTIAL":
                    self.assertTrue(TEST_REF.search(last), "%s: PARTIAL без теста" % class_id)
                elif status == "EXCLUDED":
                    self.assertTrue(last.startswith("Excluded:") and len(last) > 30, class_id)
                elif status in ("DESIGNED", "FAIL"):
                    self.assertTrue(last.startswith("Gap:") and len(last) > 10, class_id)

    def test_the_totals_line_matches_the_rows(self):
        counts = {}
        for status, _last in self.rows.values():
            counts[status] = counts.get(status, 0) + 1
        text = TABLE.read_text(encoding="utf-8")
        for status in ("PARTIAL", "DESIGNED", "EXCLUDED", "FAIL", "PASS"):
            self.assertIn("`%s` %d" % (status, counts.get(status, 0)), text)


class ClaimMatchesTheTable(unittest.TestCase):
    def test_failure_classes_in_the_claim_equal_the_table(self):
        table = {class_id: status for class_id, (status, _last) in
                 parse_table(TABLE.read_text(encoding="utf-8")).items()}
        claim = parse_claim_classes(CLAIM.read_text(encoding="utf-8"))
        self.assertEqual(claim, table)


if __name__ == "__main__":
    unittest.main()
