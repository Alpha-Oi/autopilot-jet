# Интерфейсы прогона

## Границы, решённые в спецификации

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `tools/measure-run.py` | нормализация project/log paths и анализ JSONL | `encode_project_path(path)`, `logs_dir_for(path, root=None)`, `analyse(path, label)`, CLI `main(argv=None)` | globbing, weights, формат таблицы |
| `skills/autopilot/tools/sync.py` | атомарный snapshot и жизненный цикл локального сервера | `read_state()`, `write_snapshot(state)`, `cmdline(pid)`, `iter_processes()`, `serve(state)`, `main()` | платформенные process queries и detached flags |
| dashboard inline runtime | URL состояния, render и clock updates | `stateURL()`, `applyState()`, `pollState()`, `render(lang)`, `tick()` | DOM caches, presentation HTML, theme/lang storage |
| `.github/workflows/verify.yml` | воспроизводимый quality gate | команды CI из spec §9 | GitHub runner setup |
| Git release boundary | target visibility, refs, PR, merge | GitHub API metadata и remote refs | credential values |

## Правила проекта

- Runtime: Python 3.11+ и dependency-free HTML/JavaScript; Node 20 используется для CI/browser checks, production npm dependencies отсутствуют.
- Ветка реализации: только `development`; `main` до финальной приёмки не изменять.
- Upstream base: `99c7e73678195cac08080bdd442f0e49a7ccb640` из `nick-vels/skills`.
- Не устанавливать и не обновлять production dependencies. Недостающая зависимость возвращается как `BLOCKED`, а не устанавливается самостоятельно.
- Не изменять credential values и не читать `.env`.
- Локальный gate: `flake8` syntax/error selection, `python -m unittest discover -s tests -v`, `python tools/measure-run.py --check-only`, browser smoke/performance.
- Каждый таск должен завершаться полным зелёным локальным gate и одним отдельным commit.

## Тестовые швы

1. Чистая path normalization и CLI `main(argv)` для `measure-run.py`.
2. Замоканные process/HTTP/port seams для `sync.py`.
3. Реально загруженная `dashboard-template.html` для browser smoke/performance.

## Журнал реализованных интерфейсов

### Из таска 01 — CI и переносимый `measure-run.py`

- `encode_project_path(path) -> str` — кодирует абсолютный Windows/POSIX-путь в имя каталога Claude projects.
- `logs_dir_for(path, root=None) -> Path` — вычисляет каталог логов независимо от текущего `cwd`.
- `analyse(path, label) -> dict` — анализирует JSONL-сессию, пропуская повреждённые строки.
- `main(argv=None) -> int` — CLI `<project> [session-id] | --check-only`.
- Workflow `Verify` запускается для `main`, `master`, `development` и pull request; Python gate не зависит от наличия Node-проекта.

### Из таска 02 — кроссплатформенный `sync.py`

- `cmdline(pid) -> str` — получает командную строку процесса через платформенный адаптер.
- `iter_processes() -> list[tuple[int, str]]` — выдаёт снимок процессов без Unix-only зависимости.
- `serve(state) -> str` — переиспользует только принадлежащий Autopilot сервер либо запускает платформенно-безопасный detached process.

### Из таска 03 — state path и быстрый dashboard runtime

- `stateURL() -> URL|null` — разрешает соседний `state.js` из исходного script source для `file:`/`http:`; только `data:` остаётся snapshot-only.
- `applyState() -> void` и `pollState() -> void` — обновляют состояние; неизменившийся stamp не вызывает `render`.
- `render(lang) -> void` — полный render только при изменившемся state/language.
- `tick() -> void` — обновляет clock/progress через кэшированные DOM references без повторных selector queries.

### Из таска 04 — состояние приёмки

- `state.tests = {passed, failed}` — renderer-compatible агрегат локального test gate.
- `state.checks.flake8.status` — отдельный `NOT_RUN`/итоговый статус lint gate без подмены числа тестов.
- `state.resolved[] = {status, finding, evidence}` — закрытые findings отделены от активных `concerns`.
