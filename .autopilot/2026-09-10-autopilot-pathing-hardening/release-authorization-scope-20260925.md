# Граница разрешения финального release

Сформировано: `2026-09-25T22:27:38.5117256+03:00`. Разрешение получено и повторно сверено: `2026-09-27T07:39:12.1492244+03:00`.

Статус: **разрешено пользователем 2026-09-27; последовательность выполняется**. Сам документ ничего не публикует, не создаёт `main` или PR и не меняет GitHub.

## Подтверждённая исходная точка

- Локальная ветка и Public `development`: `7911d30636afbf2987274e7c881b8a9977eebc67`.
- Target: Public `Alpha-Oi/autopilot-jet`, id `1372711955`, default `development`.
- Remote `main` отсутствует; PR `development -> main` отсутствует.
- Independent G4 pre-release gate: `GO`.
- Local33/33, exact flake8 `0`, measure-run `OK`, browser smoke и Actions35257607290 Windows/Ubuntu/macOS — зелёные.

## Текущий новый Public payload

На момент разрешения: 12 modified tracked files и 25 new text files, включая предусмотренные финальные status/evidence records ниже. Изменений production source, tests, workflow, symlinks или dependencies нет.

Modified tracked:

- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/2026-09-10-brief.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/host-model-verification.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/interfaces.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/manifest.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/spec.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/tickets/04-release-and-memory.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/tickets/07-native-root-verification.md`
- `.autopilot/README.md`
- `.autopilot/dashboard.html`
- `.autopilot/state.js`
- `AGENTS.md`
- `CLAUDE.md`

New text files:

- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/dashboard-resume-20260925.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/g2-jet-contract-coverage.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/g2-publication-consent-contract.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/g4-current-blind-acceptance.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/g4-max-blind-acceptance.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/goal-resume-revalidation-20260917-2106.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/phase8-post-ci-concern-triage.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/publication-approval-and-native-ci-20260917.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/publication-hold.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/relocation-verification.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/repository-rename-verification.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/release-authorization-approved-20260927.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/release-authorization-blocked-audit-20260925-1.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/release-authorization-blocked-audit-20260925-2.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/release-authorization-scope-20260925.md`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resume-blocked-audit-20260925-1.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resume-blocked-audit-20260925-2.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resume-blocked-audit-20260925-3.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resume-max-verification-20260925.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resume-verification-20260925.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resumed-goal-blocked-audit.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resumed-goal-browser-checkpoint.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resumed-goal-dashboard-proof.json`
- `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/resumed-goal-local-checkpoint.json`
- `docs/adr/0006-preserve-server-registry-on-unknown-process-status.md`

Перед commit добавятся только финальные механические записи в тех же разрешённых зонах: актуальный release status/evidence, snapshot dashboard и снятие `--wip` после фактического завершения. Любое появление другого файла требует нового review.

## Что станет публичным

- Autopilot brief/spec/manifest/tickets, G2/G4 и release evidence.
- Абсолютные локальные пути с именем профиля `Crown-Aliy`, timestamps, session-file path, model/effort aggregates, публичные GitHub repository/run/job identifiers и безопасные excerpts CI.
- Проектная память `AGENTS.md`/`CLAUDE.md` и ADR0006.

Не обнаружены credential values, токены, private keys, `.env`, binary files или файлы крупнее 35 KB. `.pytest_cache` и резервная копия на C: в payload не входят.

## Разрешаемая последовательность после согласия

1. Повторно проверить status, secret scan, local gate и exact remote refs; staged set сверить с этим scope.
2. Подготовить финальный development commit проектной памяти и run evidence; опубликовать только `refs/heads/development` через lease-защищённое обновление.
3. Дождаться terminal-success Actions именно для нового development SHA и прочитать обязательные job logs.
4. Создать отсутствующую `main` строго от сохранённого upstream base `99c7e73678195cac08080bdd442f0e49a7ccb640`.
5. Довести dashboard до честных 100% после зелёных G4/CI, создать PR `development -> main`, дождаться PR-head checks и выполнить merge.
6. После merge отдельно зафиксировать фактическую финальную memory/dashboard в `main`, повторить CI и read-only post-merge verification; не оставлять default `development` со stale memory.
7. Завершить цель только после подтверждения remote main, merge, raw `AGENTS.md`, final dashboard snapshot и отсутствия незавершённых обязательств.

Любая ошибка останавливает последовательность до исправления; merge, force update другого ref, global Git config, dependency install и удаление пользовательских данных не подразумеваются.

## Требуемое согласие

Достаточный явный ответ пользователя:

> Разрешаю описанный в `release-authorization-scope-20260925.md` финальный Public payload и release-последовательность для `Alpha-Oi/autopilot-jet`.

## Полученное согласие

Пользователь 2026-09-27 дал требуемый ответ дословно. Fresh read-only revalidation подтвердила session `Alpha-Oi`, Public repository id1372711955/default `development`, совпадение local/remote `development=7911d30636afbf2987274e7c881b8a9977eebc67`, отсутствие `main` и PR, success Actions35257607290. Машиночитаемая запись — `release-authorization-approved-20260927.json`.
