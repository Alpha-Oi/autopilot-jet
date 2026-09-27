# 02 — Кроссплатформенный `sync.py`

**Требования:** R11, R12, R15, R16, R22, R23
**Blocked by:** 01
**Зона:** `skills/autopilot/tools/sync.py`, `tests/test_sync.py`
**Волна:** 2
**Status:** done

## Что должно заработать

Snapshot и локальный dashboard server работают на Windows без Unix `ps`, сохраняют POSIX-поведение и никогда не завершают чужой процесс. Недоступное перечисление процессов деградирует в безопасный fallback.

## Из брифа, дословно

> «Проект должен корректно определять корневые директории при запуске на любой ОС»
> «стабильность выполнения Python-скриптов автоматизации»

## Разделы спецификации

§§4–5, 9, 11–12.

## Критерии приёмки

- [x] Windows path не вызывает `FileNotFoundError: [WinError 2]` из-за `ps`.
- [x] `cmdline(pid)` и `iter_processes()` имеют переносимую и безопасно деградирующую реализацию.
- [x] Сервер привязан только к `127.0.0.1`, повторный запуск использует свой живой процесс/порт.
- [x] Тесты доказывают, что чужие процессы не завершаются и finished/SSH/CI не поднимают сервер.
- [x] Focused и полный доступный локальный gate зелёные.

## Результат

- Commit: `5a44610`
- Проверки: `python -m unittest discover -s tests -v` → 20 passed; `python -m py_compile skills/autopilot/tools/sync.py` → exit 0; `python tools/measure-run.py --check-only` → exit 0.
- Локальный `flake8`: NOT_RUN — пакет отсутствует; фактический запуск ожидается в GitHub Actions.
