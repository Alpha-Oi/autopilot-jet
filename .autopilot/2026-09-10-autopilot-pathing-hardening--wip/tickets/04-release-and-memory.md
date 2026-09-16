# 04 — Интеграционная приёмка, память и публикация

**Требования:** R02, R05, R06, R07, R08, R09, R13, R15, R16, R17, R20, R23, R24, R25, R26, R27, R28, R29, R30, R31, R32i
**Blocked by:** 01, 02, 03, 05
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

## Локальный checkpoint 2026-09-16

- Текущий code checkpoint — `7571f27`; полный unit gate — 24 tests `OK`, full repo local `flake8` 7.3.0 — exit 0 / 0 violations (`flake8-result.json`).
- Real HTTP browser DOM benchmark — `PASS`: 8 stages, 100 tickets, 94 live clocks; медиана 5 × 1000 calls — 570.7ms против 741.5ms upstream baseline; measured queries 0/15000, console logs пусты. Evidence: `browser-benchmark.html`, `browser-benchmark-result.json` рядом с этим таском в run directory.
- Dashboard получил текущие 24 tests после очередного live poll; transient старый state при initial reload не является отсутствием обновления.
- Финальная повторная blind acceptance и внешний release gate всё ещё не завершены. `Alpha-Oi/skills` возвращает API 404; GitHub CLI OAuth завершился `expired_token` без пользовательского подтверждения.
- Проверочный flake8 установлен отдельно от Git worktree, только в `verification-tools/flake8-7.3.0` внутри Codex workspace. Первый full repo запуск получил sandbox `PermissionError [WinError 5]` в multiprocessing Pipe до checks; exact retry с разрешением дал stdout `0`, exit 0, без exclude/rule changes. Основной Python, global config и production dependencies не изменялись.
- Перед сохранением локального checkpoint повторены полный suite (24 tests in 8.650s, `OK`), точный full repo flake8 (stdout `0`, exit 0) и measure check (`OK`); команды и raw output находятся в `local-verification-result.json`.
- Checkpoint включает фактическую память в обоих файлах и пять ADR. Он не закрывает T04, blind acceptance, внешний CI или merge и не переводит dashboard в 100%.

## Начало публикации 2026-09-16

- Прямой API GET /user с разрешённой сетью подтвердил действующую сессию Alpha-Oi. Sandbox `gh auth status` не был достаточным доказательством недействительности авторизации; новая OAuth попытка не нужна.
- После прямого API 404 создан Public `Alpha-Oi/skills` (id `1372711955`) через POST /user/repos без auto-init. GET подтвердил visibility public и admin/push true; добавлен точный origin без изменения других remotes.
- Live ls-remote до первой публикации подтвердил отсутствие development/main. Публикация development должна использовать explicit ref и lease с ожидаемым отсутствием; main до зелёного CI и pre-merge acceptance не создаётся.
