# Манифест требований

Источник: `2026-09-10-brief.md`. Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «Ядро: GPT-5.6 Sol (Максимальное аналитическое рассуждение)» | in-ticket | Fresh sanitized host check 2026-09-25T17:00:25+03:00: latest `gpt-5.6-sol/max`, требуемый current effort подтверждён; history3 medium/36 max/36 xhigh, поэтому единообразие прошлого цикла не объявляется доказанным. Evidence: host-model-verification.json, resume-max-verification-20260925.json; финальный статус определяет новая G4 | spec §§3,10 → T04 |
| R02 | «использовать токен и права авторизации текущей активной сессии пользователя Alpha-Oi» | in-ticket | Прямой `gh api GET /user` с разрешённой сетью подтвердил `Alpha-Oi`; создание Public выполнено через эту сессию, секреты не извлекаются | spec §8 → T04 |
| R03 | «git config --global user.name \"Alpha-Oi\"» | in-ticket | Изменение согласовано пользователем 2026-09-17: «Продолжай, как предлагаешь» в ответ на предложение принять repo-local identity; текущий local user.name = Alpha-Oi. Global config не изменяется | spec §§2,10 → T04 |
| R04 | «git config --global user.email \"Alpha-Oi@://github.com\"» | in-ticket | Тем же ответом согласована фактическая repo-local identity: 266576325+Alpha-Oi@users.noreply.github.com вместо исходного ошибочного адреса; окончательное подтверждение включается в приёмку | spec §§2,10 → T04 |
| R05 | «Сразу после миграции создать и переключиться на ветку `development`» | in-ticket | Локальная ветка создана от upstream `99c7e736…` | spec §2 → T04 |
| R06 | «Весь автономный цикл улучшений, коммитов и тестов проводить строго в ветке `development`» | in-ticket | Подтверждено | spec §2 → T04 |
| R07 | «Ветку `main` не трогать до фазы финальной приёмки» | in-ticket | Подтверждено | spec §2 → T04 |
| R08 | «следовать циклу из папки `skills/autopilot/phases/` (от 0-preflight до 9-memory)» | in-ticket | Подтверждено | spec §3 → T01, T04 |
| R09 | «Переходить к следующей фазе только при 100% выполнении контракта текущей» | in-ticket | Подтверждено | spec §3 → T01, T04 |
| R10 | «Исправить относительные пути в `measure-run.py`» | done | Windows/POSIX normalization и cwd-independent logs root проверены 7 тестами; commit `275bb5a` | spec §5 → T01 |
| R11 | «логику подстановки путей статических ресурсов в `dashboard-template.html`» | done | Initial/poll используют один URL; file/http/data behavior покрыт, commit `dc70117` | spec §6 → T02, T03 |
| R12 | «Проект должен корректно определять корневые директории при запуске на любой ОС» | in-ticket | Native CI35257607290 на published7911d30: Windows/Linux/macOS по33 tests/no skips, в том числе native runtime fixtures; общий literal any-OS scope остаётся предметом независимой blind acceptance. Evidence: publication-approval-and-native-ci-20260917.json | spec §4 → T01, T02, T03, T06, T07, T04 |
| R13 | «Каждую итерацию автопилота логировать и сохранять глобальное состояние проекта в файлы `CLAUDE.md` и `AGENTS.md`» | in-ticket | Оба файла физически описывают текущий код и pre-release state; свежие проверки сохранены в `local-verification-result.json`. Финальная память после release ещё требуется | spec §7 → T04 |
| R14 | «На первом этапе создать файл конфигурации автоматических тестов строго по шаблону» | in-ticket | Пользователь 2026-09-17 согласовал адаптированный CI: «Продолжай, как предлагаешь». npm/cache/path адаптация больше не неподтверждённое предположение; историческое время создания и качество текущего head проверяются отдельно | spec §9 → T01, T04 |
| R15 | «Использовать его логи для контроля качества кода» | done | Jobs/steps/logs нового run35257607290 для published7911d30 изучены: Windows/Linux/macOS по33 tests/no skips, exact flake8/0, measureOK, benchmark tick<baseline и queries0/15000. Безопасные quality excerpts, run URL/id/SHA и log hashes — publication-approval-and-native-ci-20260917.json. Historical35071567560 сохранён в github-actions-result.json и не заменяет будущий PR-head CI | spec §9 → T01–T04 |
| R16 | «Любая ошибка в рантайме или сборке отменяет коммит» | in-ticket | ASSUMPTION — commit разрешён только после локального эквивалента CI; внешний CI проверяется после push | spec §9 → T01–T04 |
| R17 | «Склонировать код из nick-vels/skills» | in-ticket | Выполнено локально, upstream сохранён | spec §2 → T04 |
| R18 | «Провести глубокий анализ импортов в скриптах папки `инструменты` и путей к файлам разметки HTML» | done | Source-aware independent recheck COMPLETE: полный runtime import inventory/provenance и HTML anchors; phase3-artifact-recheck.md. Не заменяет failed G2 | spec §4 → T01, T06 |
| R19 | «Сформировать карту путей сборки» | done | Source-aware independent recheck COMPLETE: discovery/copy/anchor/temp/log/state/assets/CI/test consumers; единственный pointer исправлен. phase3-artifact-recheck.md | spec §4 → T01, T03, T06 |
| R20 | «Запустить субагентов для пошагового выполнения бэклога» | in-ticket | Реализация, repair, code review и описание памяти делегированы; финальная слепая перепроверка ожидает внешний release gate | spec §3 → T04 |
| R21 | «Улучшить скорость рендеринга дашборда» | done | Real HTTP DOM 8 stages / 100 tickets: медиана 5 × 1000 tick 570.7ms ≤ 741.5ms upstream baseline; measured DOM queries 0/15000, `browser-benchmark-result.json`; реализация `dc70117`, regression gate `7571f27` | spec §6 → T03 |
| R22 | «стабильность выполнения Python-скриптов автоматизации» | done | D01 устранён T06; independent G4 повторил full33/33 и `measure-run OK`, native Actions35257607290 подтвердил тот же SHA на Windows/Linux/macOS. Unknown-process safety и no-duplicate contract покрыты; g4-max-blind-acceptance.md | spec §§5,14 → T01, T02, T06, T07, T04 |
| R23 | «Один шаг = один коммит в `development`» | in-ticket | Подтверждено | spec §3 → T01–T04 |
| R24 | «дашборд отображает 100% готовность» | in-ticket | Только после всех локальных и внешних проверок | spec §9 → T03, T04 |
| R25 | «тесты GitHub Actions для ветки `development` успешны» | done | Independent G4 live supplement подтвердил run35257607290 на exact published development7911d30: Windows/Ubuntu/macOS success, по33 tests/OK, lint0, benchmark pass и measure-run OK; `--log-failed` пуст/exit0. Evidence: g4-max-blind-acceptance.md | spec §9 → T07, T04 |
| R26 | «Создать Pull Request, слить ветку `development` в `main`» | in-ticket | Внешняя финальная операция после зелёной приёмки | spec §8 → T04 |
| R27 | «Зафиксировать состояние системы в файле памяти AGENTS.md в ветке `main`» | in-ticket | Подтверждено | spec §7 → T04 |
| R28 | «Целевой репозиторий (мой профиль): https://github.com/Alpha-Oi» | in-ticket | GitHub connector подтвердил `Alpha-Oi` | spec §8 → T04 |
| R29 | «Имя целевого репозитория должно быть skills» | in-ticket | G03: пользователь явно согласовал rename в `Alpha-Oi/autopilot-jet`; прежний id1372711955/Public/development сохранены. Исходная цитата историческая; финальная приёмка pending | spec §§8,16 → T04 |
| R30 | «Если репозитория skills еще нет в моем профиле, создай его автоматически через API сессии как публичный (Public)» | done | После прямого API 404 создан через `POST /user/repos`; GET подтвердил `Alpha-Oi/skills`, id `1372711955`, visibility `public`, admin/push true | spec §8 → T04 |
| R31 | «Если он уже существует, сделай в него force push ветки development» | in-ticket | ASSUMPTION — при гонке обновлять только `development` с проверкой remote; `main` не затрагивать | spec §8 → T04 |
| R32i | *(подразумевается)* сохранить историю исходного репозитория при миграции | in-ticket | ASSUMPTION — `upstream` остаётся `nick-vels/skills`, коммиты продолжают его историю | spec §2 → T04 |

## Ограничения, доказанные исполнением

| ID | Родитель | Статус | Наблюдение | Где |
|---|---|---|---|---|
| D01 | R22, R12 | done | T06 1ab3dad097d3653564b8b2bf0e71d40b5baa5a6d; focused14 и root full33 green, independent baseline13 failing subtests/0errors; no duplicate/PID rewrite при unknown на проверенных seams. Real process cleanup не выполнялся | spec §14 → T06 |

## Согласованные изменения

G01 — 2026-09-17, родитель R03/R04/R14: «Продолжай, как предлагаешь» относится к предложению принять адаптированный CI и repo-local Git identity. Полный контекст и цитата находятся в дополнениях исходного брифа. Изменение не снимает R01/R12, исторические требования, G2/G4 или ограничения main/PR/merge.

G02 — 2026-09-17, родитель R09/R22: «Исправляй хук». Точечная коррекция global governance_hook.py отдельно разрешена и завершена; защита проверена 45/45 safe decision tests, не full live Codex E2E. Контракт spec §15, backup/report вне Git; Git/publication этим не разрешены. Подтверждение включается в T04.

G03 — 2026-09-17, родитель R29: «да» на вопрос «Переименовать `Alpha-Oi/skills` в `Alpha-Oi/autopilot-jet`?». Согласованы rename существующего repository и обновление текущего назначения/origin/плана/дашборда. PATCH name и GET сохранили repository id1372711955/Public/default development/remote SHA6265e03; source history и местные folders не переписывались. Дословные прежние требования и dated evidence сохраняются. G03 не разрешает public payload, push/main/PR/merge или снятие acceptance gates; repository-rename-verification.json, spec §16 → T04.

G04 — 2026-09-27, родители R24/R26/R27/R31: «Разрешаю описанный в `release-authorization-scope-20260925.md` финальный Public payload и release-последовательность для `Alpha-Oi/autopilot-jet`». Разрешены exact reviewed payload, lease-защищённое обновление только `development`, создание отсутствующей `main` от upstream base, PR/merge после fresh checks и post-merge memory/dashboard finalization. Другая публикация, force update иных refs, global config, dependencies и удаления не разрешены; release-authorization-approved-20260927.json, spec §17 → T04.
