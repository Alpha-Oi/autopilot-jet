# 01 — Работающий CI и переносимый `measure-run.py`

**Требования:** R08, R09, R10, R12, R14, R15, R16, R18, R19, R22, R23, R25
**Blocked by:** —
**Зона:** `.github/workflows/verify.yml`, `tools/measure-run.py`, `tests/test_measure_run.py`
**Волна:** 1
**Status:** ready

## Что должно заработать

Появляется `.github/workflows/verify.yml`, выполняющий реальные команды repository, а `measure-run.py` одинаково разрешает Claude logs на Windows/POSIX, запускается из любого cwd, поддерживает `--check-only` и контролируемо обрабатывает плохие данные. Таск завершает полный вертикальный quality path, поэтому его commit может быть зелёным.

## Из брифа, дословно

> «На первом этапе создать файл конфигурации автоматических тестов строго по шаблону»
> «Любая ошибка в рантайме или сборке отменяет коммит»
> «Исправить относительные пути в `measure-run.py`»

## Разделы спецификации

§§3–5, 9–10, 12.

## Критерии приёмки

- [ ] Workflow реагирует на `main`, `master`, `development` и соответствующие PR.
- [ ] Нет npm cache/install ошибки в repository без `package.json`.
- [ ] Python 3.11, flake8 error selection, unittest и `tools/measure-run.py --check-only` присутствуют.
- [ ] YAML корректно разбирается; локальные эквиваленты команд перечислены и выполняются либо явно помечены как ожидающие следующих тасков.
- [ ] Windows/POSIX path encoding, явный logs root, UTF-8 и malformed JSONL покрыты тестами.
- [ ] `python tools/measure-run.py --check-only` возвращает `0` из любого cwd.
- [ ] Изменения ограничены зоной и проходят проверку отсутствия секретов.
