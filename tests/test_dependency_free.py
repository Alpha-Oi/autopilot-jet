"""Навык не тянет чужие артефакты: только стандартная библиотека, ни одного менеджера пакетов.

Это техническая проверка того, что README и ADR говорят словами (REQ-COND-03 стандарта DOA:
horizontal transfer запрещён, и запрет проверяется). Область — код самого навыка и репозитория:
скрипты `skills/autopilot-jet/tools/` и `tools/`. Проект, который навык строит для пользователя,
сюда не входит.

Функции проверки проверены на синтетическом коде: без этого тест, который никогда не краснеет,
ничего не доказывает.
"""

import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
PRODUCT_DIRS = (ROOT / "skills" / "autopilot-jet" / "tools", ROOT / "tools")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
MANIFESTS = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "Pipfile", "Pipfile.lock", "poetry.lock", "go.mod", "Cargo.toml", "Gemfile", "pom.xml",
}
PACKAGE_MANAGERS = {"pip", "pip3", "npm", "npx", "yarn", "pnpm", "curl", "wget", "poetry", "pipx", "uv"}


def package_manifests(root):
    """Манифесты зависимостей в дереве репозитория (без .git и кэшей)."""
    found = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIP_DIRS & set(path.relative_to(root).parts) and path.name in MANIFESTS:
            found.append(path.relative_to(root).as_posix())
    return found


def non_stdlib_imports(source):
    """Имена верхнего уровня импортов, которых нет в стандартной библиотеке."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return sorted(name for name in names if name not in sys.stdlib_module_names)


def package_manager_calls(source):
    """Списки-аргументы вида ["pip", "install", ...] и ["npm", ...] в исходнике."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.List) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value.split("/")[-1].split(".")[0] in PACKAGE_MANAGERS:
                    hits.append(first.value)
    return hits


def product_sources():
    for directory in PRODUCT_DIRS:
        for path in sorted(directory.glob("*.py")):
            yield path, path.read_text(encoding="utf-8")


class CheckersCanTurnRed(unittest.TestCase):
    def test_non_stdlib_imports_are_found(self):
        source = "import os\nimport requests\nfrom yaml import safe_load\nfrom . import sibling\nimport json.decoder\n"
        self.assertEqual(non_stdlib_imports(source), ["requests", "yaml"])

    def test_package_manager_calls_are_found(self):
        source = 'subprocess.run(["pip", "install", "x"])\nsubprocess.run(["/usr/bin/curl", "-O", u])\nsubprocess.run(["ps", "-p", "1"])\n'
        self.assertEqual(package_manager_calls(source), ["pip", "/usr/bin/curl"])

    def test_manifests_are_found_and_caches_are_ignored(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "sub" / "package.json").write_text("{}", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "package.json").write_text("{}", encoding="utf-8")
            (root / "README.md").write_text("x", encoding="utf-8")
            self.assertEqual(package_manifests(root), ["sub/package.json"])


class SkillIsDependencyFree(unittest.TestCase):
    def test_product_code_is_found(self):
        names = {path.name for path, _ in product_sources()}
        self.assertTrue({"sync.py", "redact.py", "measure-run.py"} <= names, names)

    def test_repository_has_no_package_manifests(self):
        self.assertEqual(package_manifests(ROOT), [])

    def test_product_code_imports_only_the_standard_library(self):
        for path, source in product_sources():
            with self.subTest(file=path.name):
                self.assertEqual(non_stdlib_imports(source), [])

    def test_product_code_never_invokes_a_package_manager(self):
        for path, source in product_sources():
            with self.subTest(file=path.name):
                self.assertEqual(package_manager_calls(source), [])


if __name__ == "__main__":
    unittest.main()
