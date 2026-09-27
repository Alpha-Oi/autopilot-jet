# 04 — Интеграционная приёмка, память и публикация

**Требования:** R01, R02, R03, R04, R05, R06, R07, R08, R09, R12, R13, R14, R15, R16, R17, R20, R22, R23, R24, R25, R26, R27, R28, R29, R30, R31, R32i; G01, G02, G03, G04
**Blocked by:** 01, 02, 03, 05, 06, 07
**Зона:** `AGENTS.md`, `CLAUDE.md`, `.autopilot/`, GitHub release boundary
**Волна:** 6
**Status:** in-progress — independent G4 pre-release gate `GO`: development7911d30, current host `gpt-5.6-sol/max`, local gates, browser smoke, governance45/45 и native CI35257607290 подтверждены. G04 разрешил exact новый Public payload и ordered release sequence; pre-release revalidation выполнена, внешние release actions ещё не начинались.

## Что должно заработать

Полный локальный gate и blind acceptance зелёные; memory files отражают завершённый код; Public `Alpha-Oi/autopilot-jet` (G03) получает `development`, успешный Actions run, PR и merge в `main`. Upstream history и target visibility/refs проверены API.

## Из брифа, дословно

> «Убедиться, что дашборд отображает 100% готовность, а тесты GitHub Actions для ветки `development` успешны.»
> «Создать Pull Request, слить ветку `development` в `main`.»
> «Зафиксировать состояние системы в файле памяти AGENTS.md в ветке `main`.»

## Разделы спецификации

§§2–3, 4.0.2, 7–16.

## Критерии приёмки

- [x] Достоверно проверены фактические host model/effort и не отменённые исторические требования; latest current max подтверждён, mixed history честно оставлена partial. G01/G02/G03 не расширены.
- [x] T06 исправлен и native Windows/Linux/macOS CI текущего опубликованного head завершён success; остальные ОС не объявлены проверенными без evidence.
- [x] Полный локальный gate и независимый blind acceptance зелёные; dashboard не переводится в 100% до release finalization.
- [x] `AGENTS.md` и compact mirror в `CLAUDE.md` обновлены реальными командами/состоянием.
- [x] `Alpha-Oi/autopilot-jet` существует как Public с прежним id1372711955 (G03), `origin` точен; с informed approval опубликован development7911d30 с lease6265e03, незакоммиченные изменения исключены; main/PR/merge не затронуты.
- [ ] Новый development payload ещё не опубликован; после него требуется terminal-success Actions, затем PR `development -> main` и merge в разрешённой G04 последовательности.
- [x] По spec §9 изучены jobs/steps и логи Actions35257607290 именно опубликованного development7911d30: все три ОС по33 tests/no skips, exact flake8/0, measureOK, benchmark tick<baseline/queries0/15000. Безопасные строки результата и run URL/id/SHA сохранены в publication-approval-and-native-ci-20260917.json; это не закрывает future PR head CI.
- [ ] Remote `main`, история upstream, финальный `AGENTS.md` и 100% dashboard подтверждены после merge.

## Локальная приёмка 2026-09-12

- Рабочие `.autopilot/sync.py` и `.autopilot/dashboard.html` синхронизированы с исправленными source; встроенный snapshot совпадает с `state.js`.
- `python -B -m unittest discover -s tests -v` → 20 passed; `python -B tools/measure-run.py --check-only` → OK; оба `sync.py` прошли `py_compile`.
- System Chrome headless проверил actual dashboard через `file:` и краткоживущий `127.0.0.1` HTTP server: соседний `state.js` загружен, render успешен, console/runtime/load errors — 0, остановлен только собственный server PID.
- `flake8` локально `NOT_RUN`: модуль не установлен; установка зависимостей не выполнялась. Dashboard остаётся pre-release, не 100%.
- State schema repair: top-level `tests` хранит `{passed: 20, failed: 0}`, `flake8` остаётся отдельным `NOT_RUN`, закрытые Windows `ps` и `data:` live-claim findings перенесены в `resolved`.

## Pending orchestrator

- Выполнить разрешённую G04 последовательность без перестановки gates: local/staged review, development commit/push с lease, exact-SHA CI logs, dashboard100, main/PR/PR checks/merge, post-merge memory/dashboard/CI verification.
- Exact file scope, metadata exposure and authorized sequence are fixed in `release-authorization-scope-20260925.md`; дополнительные файлы допустимы только как явно предусмотренные финальные механические status/evidence записи в тех же зонах.

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
- Push отправил только development и подтверждён live ref 247535a; main не создан. Ubuntu Actions run 35071567560 завершён success, jobs и quality log lines сохранены в github-actions-result.json. Независимая pre-merge приёмка выполняется; PR/merge остаются следующими шагами.

## Повторный план 2026-09-17

G01 согласован, G02 repair завершён. Revised G2 прошёл independent missing0/half0/extra0. D01 потребовал T06; не подтверждённый native охват R12 потребовал T07. T06/T07 имеют disjoint edit zones и идут одной волной 5; прежняя финальная волна T04 перенесена с 3 на 6 только из-за этих blocking edges, ID и история таска сохранены. Итоговая приёмка/100%/main/PR/merge/post-merge остаются не выполненными.

## Согласованное имя 2026-09-17

G03 явно разрешил rename в Autopilot JET. Current target — `Alpha-Oi/autopilot-jet`; прежние checkpoints выше исторические. API id1372711955/Public/default development/ref6265e03 сохранены, main absent; D: origin обновлён, местный HEAD7911d30 и исходный execution_plan не менялись. Публикация reports/local metadata, fresh native CI, независимая amended G2/full blind acceptance и main/PR/merge остаются pending. Подтверждение — repository-rename-verification.json.

## Возобновлённая приёмка 2026-09-25

- Fresh local gate: 33/33 tests, measure check OK, exact flake8 0, Node VM `489.64ms <= 740.40ms`, queries `0/15000`; sandbox-only `WinError 5` устранён точным повтором вне sandbox без правок кода.
- Read-only GitHub: Public id1372711955, `development=7911d30`, Actions35257607290 success, `main` отсутствует, PR `[]`.
- Memory и ADR независимо перепроверены: дополнительных правок не требуется; ADR0006 закрывает D01 и supersedes только противоречащую часть ADR0002.
- Actual populated dashboard открыт через штатный loopback helper: 81%, 33 tests, 6/7 tickets; fresh checkpoint виден, `undefined` отсутствует, console warn/error `[]`.
- Fresh independent G4: `NO-GO`, 34 строки — 20 реализовано, 8 частично, 6 не выполнено; `g4-current-blind-acceptance.md`.
- Manifest drift не скрыт: R18/R19 помечены done, но G4 может подтвердить их лишь частично при обязательном запрете читать Phase3/run artifacts.
- После ответа пользователя «готово» latest host metadata подтверждает `gpt-5.6-sol/max` (75 contexts; 3 medium / 36 max / 36 xhigh исторически), прежний blocked audit сброшен и начата новая независимая G4. Историческая неоднородность не скрывается.
- Independent G4 завершена `GO` для pre-release gate: local33/33, exact flake80, measureOK, real Edge smoke, live Windows/Ubuntu/macOS CI и governance45/45. Полная матрица и команды — `g4-max-blind-acceptance.md`.
- 100%, `main`, PR/merge и post-merge `AGENTS.md` отсутствовали как упорядоченные post-acceptance шаги; G04 теперь разрешает их последовательное выполнение в exact scope.

## Разрешение финального release 2026-09-27

- G04 получен дословно по формуле из `release-authorization-scope-20260925.md`; evidence — `release-authorization-approved-20260927.json`.
- Fresh read-only start: session `Alpha-Oi`; Public id1372711955/default `development`; local и remote development `7911d30636afbf2987274e7c881b8a9977eebc67`; `main` 404; PR `[]`; Actions35257607290 success.
- Выполнение начато, но commit/push/main/PR/merge на момент этой записи ещё не выполнялись.
