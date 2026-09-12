# 04 — Интеграционная приёмка, память и публикация

**Требования:** R02, R05, R06, R07, R08, R09, R13, R15, R16, R17, R20, R23, R24, R25, R26, R27, R28, R29, R30, R31, R32i
**Blocked by:** 01, 02, 03
**Зона:** `AGENTS.md`, `CLAUDE.md`, `.autopilot/`, GitHub release boundary
**Волна:** 3
**Status:** in-progress — локальная часть готова; внешний release gate ожидает оркестратор

## Что должно заработать

Полный локальный gate и blind acceptance зелёные; memory files отражают завершённый код; Public `Alpha-Oi/skills` получает `development`, успешный Actions run, PR и merge в `main`. Upstream history и target visibility/refs проверены API.

## Из брифа, дословно

> «Убедиться, что дашборд отображает 100% готовность, а тесты GitHub Actions для ветки `development` успешны.»
> «Создать Pull Request, слить ветку `development` в `main`.»
> «Зафиксировать состояние системы в файле памяти AGENTS.md в ветке `main`.»

## Разделы спецификации

§§2–3, 7–13.

## Критерии приёмки

- [ ] Полный локальный gate и независимый blind acceptance зелёные; dashboard ещё не показывает 100% до их завершения.
- [x] `AGENTS.md` и compact mirror в `CLAUDE.md` обновлены реальными командами/состоянием.
- [ ] `Alpha-Oi/skills` существует как Public, `origin` точен, `development` опубликован авторизацией сессии `Alpha-Oi`.
- [ ] GitHub Actions на `development` завершён успешно; PR `development -> main` создан и слит.
- [ ] Remote `main`, история upstream, финальный `AGENTS.md` и 100% dashboard подтверждены после merge.

## Локальная приёмка 2026-09-12

- Рабочие `.autopilot/sync.py` и `.autopilot/dashboard.html` синхронизированы с исправленными source; встроенный snapshot совпадает с `state.js`.
- `python -B -m unittest discover -s tests -v` → 20 passed; `python -B tools/measure-run.py --check-only` → OK; оба `sync.py` прошли `py_compile`.
- System Chrome headless проверил actual dashboard через `file:` и краткоживущий `127.0.0.1` HTTP server: соседний `state.js` загружен, render успешен, console/runtime/load errors — 0, остановлен только собственный server PID.
- `flake8` локально `NOT_RUN`: модуль не установлен; установка зависимостей не выполнялась. Dashboard остаётся pre-release, не 100%.
- State schema repair: top-level `tests` хранит `{passed: 20, failed: 0}`, `flake8` остаётся отдельным `NOT_RUN`, закрытые Windows `ps` и `data:` live-claim findings перенесены в `resolved`.

## Pending orchestrator

- Independent blind acceptance и внешний GitHub gate: target visibility, `origin`, publish `development`, Actions success, PR/merge, remote `main` и post-merge memory/dashboard verification.
