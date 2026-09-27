См. @AGENTS.md

<!-- autopilot:start -->
# Autopilot JET

Канон памяти, контрактов и команд — `AGENTS.md`; здесь только компактное зеркало.
Активный worktree — `D:\Development\skills\worktrees\skills-development`, ветка `development`; резерв на C: не развивать и не синхронизировать обратно.
Целевой Public repository — `Alpha-Oi/autopilot-jet` (id `1372711955`, default `development`); runtime — Python standard library + dependency-free HTML/JavaScript.

- Канонические исходники: `skills/autopilot/SKILL.md`, `skills/autopilot/tools/sync.py`, `skills/autopilot/phases/dashboard-template.html`, `tools/measure-run.py`; `.agents/skills/autopilot` и `.claude/skills/autopilot` — symlink-chain на skill.
- `.autopilot/state.js` → runtime helper → embedded snapshot/loopback server → live dashboard; helper читает соседние файлы относительно собственного пути, не cwd.
- Для существующего dashboard: `python -X utf8 -B .autopilot/sync.py --no-serve`; прямой запуск canonical helper его не обновляет, source/template правки не делать в runtime copy.
- Invalid JSON не обновляет snapshot; unknown recorded PID сохраняется без duplicate launch/registry rewrite; durable decision — `docs/adr/0006-preserve-server-registry-on-unknown-process-status.md`.
- Чужие и незаписанные servers не завершаются; bind только `127.0.0.1`; `data:` snapshot-only, `file:`/`http:` live-poll; stamp `updatedAt|finishedAt|tickets.length` требует двигать `updatedAt` при изменениях.
- Full suite, single-file discovery, measure smoke и exact isolated flake8 команды — в `AGENTS.md`; `.github/workflows/verify.yml` использует Python 3.11/Node 20, локальный toolchain — Python 3.14.3/Node 25.8.0.
- Code HEAD `d9ea88a7d8cc0c8f5aed88f7d092518e0a181f7d` опубликован в remote `development`. Local release gate: 33 tests/`OK`, lint `0`, measure `OK`, benchmark `495.51ms < 888.63ms`, queries `0/15000`.
- Actions `36295270998` для exact SHA успешен на Windows/Ubuntu/macOS: на каждом native runner 33 tests/`OK`, lint `0`, benchmark pass, measure `OK`. Dashboard snapshot + Node VM render: `100%`, `6/7` tickets, runtime matches tested template.
- Real Edge smoke предыдущего среза: live update/controls visible, exit `0`; benchmark `483.02ms < 666.80ms`, queries `0/15000`. Текущая реальная browser tab — `NOT_VERIFIED_CURRENT_CHECKPOINT`: localhost server остановлен, запуск процесса и `file:` navigation заблокированы policy.
- Governance harness `45/45`, `dangerousCommandsExecuted=false`; независимый G4 pre-release gate — `GO`.
- Последние host metadata — `gpt-5.6-sol/max`; история mixed (`3 medium / 36 max / 36 xhigh`), не all-history `max`.
- Пользователь 2026-09-27 разрешил финальный Public payload и согласованную release-последовательность для `Alpha-Oi/autopilot-jet`; повторное разрешение внутри scope не требуется. Payload committed/pushed в `development` с exact lease и проверен exact-SHA CI; на момент checkpoint `main`, PR/merge и post-merge memory/dashboard остаются pending.
- Handoff blocker: два exact `git add` семи подготовленных text files не смогли создать `D:/Development/skills/work/nick-vels-skills/.git/worktrees/skills-development/index.lock` (`Permission denied`), несмотря на выданное разрешение; lock отсутствует, staged set пуст, remote `development` всё ещё `d9ea88a7d8cc0c8f5aed88f7d092518e0a181f7d`, `main`/PR отсутствуют. Открыть активный D: worktree в Codex или дать эффективную запись в Git metadata и продолжить seven-file checkpoint без пересоздания repository.
- `/autopilot`: требования → спецификация → план → разработка → код-ревью → слепая приёмка; «сборка» — весь прогон, единица — «таск», инструкции этапов не читать заранее.
- `.autopilot/` хранит запись прогона, не исходники skill; глобальный skill не обновлялся и может отличаться от checkout.

<!-- autopilot:end -->
