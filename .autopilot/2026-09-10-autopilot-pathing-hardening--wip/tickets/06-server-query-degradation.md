# 06 — Не дублировать сервер при недоступной проверке процесса

**Requirements:** R12, R16, R22, R23; D01 → R22
**Blocked by:** 02, 05
**Зона:** `skills/autopilot/tools/sync.py`, `tests/test_sync.py`, `.autopilot/sync.py` (только runtime parity copy)
**Волна:** 5
**Status:** done — independent review clean, root local gate green; commit 1ab3dad097d3653564b8b2bf0e71d40b5baa5a6d

## Состояние на 2026-09-16T16:02:20.9101715+03:00

Executor вернул BLOCKED без изменений: baseline focused10/full24/check-only/exact flake8 green. G2 failed6/half4; spec amendment остановлен governance hook до выполнения. Code editing и commit не начаты; D01 не устранён.

2026-09-17: user-authorized hook correction completed; CI/local identity agreed, remaining original contract restored. Independent revised G2 missing0/half0/extra0. Предыдущий отказ и старый status сохранены как история, edit gate теперь открыт после G3 recheck; D01 всё ещё требует реализации.

## Из брифа

> «Улучшить скорость рендеринга дашборда и стабильность выполнения Python-скриптов автоматизации.»
> «Проект должен корректно определять корневые директории при запуске на любой ОС.»
> «Один шаг = один коммит в development.»
> «Любая ошибка в рантайме или сборке отменяет коммит.»

## Наблюдаемая проблема

2026-09-16: recorded port 56521 / PID 5716 жив; approved read-only CIM подтвердил exact own server. Два helper ports 56247 и 56521 одновременно отвечают HTTP 200 и отдают ровно текущий state.js. В sandbox CIM-query недоступен. Текущий `serve()` трактует пустой `cmdline()` как основание выбрать новый порт и запустить новый процесс, переписывая PID record. Это допускает накопление серверов без прекращения уже живого.

## Что должно заработать

Повторный sync обновляет snapshot и не запускает лишний процесс только из-за недоступной проверки command line. Неизвестное состояние процесса не считается положительно доказанным отсутствием. Ownership не подтверждается одним HTTP 200. Обычные подтверждённые own reuse и recovery после действительно отсутствующего/stale server сохраняются.

## Критерии приёмки

- [ ] Recorded responding server + unavailable/empty command query: несколько последовательных `serve()` не вызывают `Popen`, не меняют `serve.pid`, не завершают процессы и возвращают честное предупреждение без утверждения ownership/live readiness.
- [ ] Recorded process unknown + transient HTTP timeout не приводит к слепому дублированию; положительно отсутствующий stale PID допускает обычный controlled recovery.
- [ ] Known exact own live server сохраняет прежний URL; known foreign server не завершается и не объявляется своим; unrecorded same-directory server не обнаруживается для массового cleanup.
- [ ] Nonzero process-query exit со stdout не выдаётся за успешно подтверждённый command line. Process probing не использует `os.kill(pid, 0)` на Windows и не требует новых dependencies или escalation внутри runtime.
- [ ] Tests доказывают regression (могли быть красными на старом коде), platform query/degradation branches и отсутствие destructive process calls. Существующие tests не ослабляются.
- [ ] `.autopilot/sync.py` byte-identical canonical helper; этот файл не изменяет parent state/evidence/memory.
- [ ] Focused + full suite + check-only + exact syntax/error flake8 green; один отдельный commit оркестратора в development после независимого review.

## Спецификация и запуск

`spec.md`: «4.2 Сбой, прерывание, рост и границы», «5.2 sync.py», «14. D01 — недоступность process query и дублирование серверов». Сначала полностью читать `interfaces.md`, затем этот таск. До первого изменения прочитать `skillDir/prompts/executor.md` полностью.

Baseline: 24 full tests, 10 sync-focused tests. Full: `python -B -m unittest discover -s tests -v`; focused: `python -B -m unittest discover -s tests -p "test_sync.py" -v`; smoke: `python -B tools/measure-run.py --check-only`. Exact flake8 из AGENTS.md; без installs.

## Защищённые зоны

Не менять `.github/workflows/verify.yml`, measure/dashboard sources, dependencies/locks, Git config/refs, `.autopilot/state.js`, spec/interfaces/other evidence, AGENTS.md/CLAUDE.md. Не читать secrets/.env. Не делать commit/push/API mutations, не останавливать реальные серверы. Root владеет изменёнными acceptance/memory/state files. Только bounded implementation и тесты.
