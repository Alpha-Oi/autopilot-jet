См. @AGENTS.md

<!-- autopilot:start -->
# Autopilot JET

Канон памяти, контрактов и команд — `AGENTS.md`; здесь только компактное зеркало.
Активный worktree — ветка `development` (локальная копия автора — отдельный worktree).
Целевой Public repository — `Alpha-Oi/autopilot-jet` (id `1372711955`, default `development`); runtime — Python standard library + dependency-free HTML/JavaScript.

- Канонические исходники: `skills/autopilot-jet/SKILL.md`, `skills/autopilot-jet/tools/sync.py`, `skills/autopilot-jet/phases/dashboard-template.html`, `tools/measure-run.py`; `.agents/skills/autopilot-jet` и `.claude/skills/autopilot-jet` — symlink-chain на skill.
- `.autopilot/state.js` → runtime helper → embedded snapshot/loopback server → live dashboard; helper читает соседние файлы относительно собственного пути, не cwd.
- Для существующего dashboard: `python -X utf8 -B .autopilot/sync.py --no-serve`; прямой запуск canonical helper его не обновляет, source/template правки не делать в runtime copy.
- Invalid JSON не обновляет snapshot; unknown recorded PID сохраняется без duplicate launch/registry rewrite; durable decision — `docs/adr/0006-preserve-server-registry-on-unknown-process-status.md`.
- Чужие и незаписанные servers не завершаются; bind только `127.0.0.1`; `data:` snapshot-only, `file:`/`http:` live-poll; stamp `updatedAt|finishedAt|tickets.length` требует двигать `updatedAt` при изменениях.
- Full suite, single-file discovery, measure smoke и exact isolated flake8 команды — в `AGENTS.md`; `.github/workflows/verify.yml` использует Python 3.11/Node 20, локальный toolchain — Python 3.14.3/Node 25.8.0.
- Финальный release payload `c23de4263454dae03faa5341bceb7d5d24360230` опубликован в `development`; PR #1 смержен в `main` как `ca6743bb0b2453c79325fe30f6b9680b911ef4ed`. Local release gate на момент release: 33 tests/`OK` (сейчас 61 test/`OK`, см. `AGENTS.md`), lint `0`, measure `OK`, benchmark `457.34ms < 712.29ms`, queries `0/15000`.
- Actions `36339995752` для exact development SHA и PR-head Actions `36340188512` успешны на Windows/Ubuntu/macOS. Финальный dashboard: `100%`, `7/7` тасков, frozen snapshot совпадает с state.
- Real Edge smoke предыдущего среза: live update/controls visible, exit `0`; benchmark `483.02ms < 666.80ms`, queries `0/15000`. Текущая реальная browser tab — `NOT_VERIFIED_CURRENT_CHECKPOINT`: localhost server остановлен, запуск процесса и `file:` navigation заблокированы policy.
- Governance harness `45/45`, `dangerousCommandsExecuted=false`; независимый G4 pre-release gate — `GO`.
- Последние host metadata — `gpt-5.6-sol/max`; история mixed (`3 medium / 36 max / 36 xhigh`), не all-history `max`.
- Разрешённая Public release-последовательность завершена: lease-защищённый `development`, exact-SHA CI, `main` от `99c7e736`, PR #1, fresh PR-head CI, merge и post-merge memory/dashboard. Незавершённых release-обязательств нет.
- `/autopilot-jet`: требования → спецификация → план → разработка → код-ревью → слепая приёмка; «сборка» — весь прогон, единица — «таск», инструкции этапов не читать заранее.
- `.autopilot/` хранит запись прогона, не исходники skill; глобальный skill не обновлялся и может отличаться от checkout.

<!-- autopilot:end -->
