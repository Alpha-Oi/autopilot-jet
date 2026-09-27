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
- Code HEAD `7911d30636afbf2987274e7c881b8a9977eebc67` на `development`; source совпадает с опубликованным `development`. Local: 33 tests/`OK`, lint `0`, measure OK.
- Real Edge smoke: live update/controls visible, exit `0`; benchmark `483.02ms < 666.80ms`, queries `0/15000`. Actions `35257607290` для exact SHA зелёный на Windows/Ubuntu/macOS: 33 tests/`OK`, lint `0`, benchmark pass, measure OK.
- Governance harness `45/45`, `dangerousCommandsExecuted=false`; независимый G4 pre-release gate — `GO`.
- Последние host metadata — `gpt-5.6-sol/max`; история mixed (`3 medium / 36 max / 36 xhigh`), не all-history `max`.
- Пользователь 2026-09-27 разрешил финальный Public payload и согласованную release-последовательность для `Alpha-Oi/autopilot-jet`; повторное разрешение внутри scope не требуется. Последовательность только началась: новый payload не committed/pushed, remote `development` остаётся на `7911d30636afbf2987274e7c881b8a9977eebc67`, remote `main` отсутствует, PR list пуст, merge и post-merge memory/dashboard не выполнены.
- `/autopilot`: требования → спецификация → план → разработка → код-ревью → слепая приёмка; «сборка» — весь прогон, единица — «таск», инструкции этапов не читать заранее.
- `.autopilot/` хранит запись прогона, не исходники skill; глобальный skill не обновлялся и может отличаться от checkout.

<!-- autopilot:end -->
