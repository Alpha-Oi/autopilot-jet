# 07 — Нативная проверка корней Windows/Linux/macOS

**Требования:** R10, R12, R14, R15, R16, R22, R23, R25
**Blocked by:** 05
**Зона:** `.github/workflows/verify.yml`, `tests/test_native_runtime.py`
**Волна:** 5
**Status:** done — independent review clean, root local gate green; commit 7911d30636afbf2987274e7c881b8a9977eebc67 опубликован с exact informed approval; native Actions35257607290 success на Windows/Linux/macOS (по33 tests/no skips), publication-approval-and-native-ci-20260917.json. Whole-project acceptance остаётся T04.

## Что должно заработать

Согласованный CI проверяет фактические path/root/runtime seams на Windows, Linux и macOS, а не выдаёт POSIX mocks за macOS. Реальные короткие cold CLI/helper runs из другого cwd с пробелами/Unicode и isolated home/log fixtures подтверждают корни; process query проверяется только для собственного текущего test PID. Это доказательная доработка действующего R12, не смена цели «любая ОС» на три среды.

## Из брифа, дословно

> «Проект должен корректно определять корневые директории при запуске на любой ОС.»
> «Использовать его логи для контроля качества кода.»
> «Любая ошибка в рантайме или сборке отменяет коммит.»
> «Один шаг = один коммит в development.»
> «Продолжай, как предлагаешь» — дополнение с согласием на адаптированный CI, не отменой других требований.

## Разделы спецификации

§§3, 4.0.2, 5–6, 9, 12. Использовать существующие public seams: helper CLI/main, cmdline(pid), measure CLI. Не вводить новый production resolver/API. Будущие/private изменения T06 не являются dependency этой проверки.

## Критерии приёмки

- [ ] Workflow содержит native Ubuntu/Windows/macOS jobs (matrix допустима), сохраняет name, job validate, push/PR main/master/development, Actions версии, Python3.11/Node20 и exact full-repo flake8 gate. Новые production dependencies/lockfile не создаются; npm не запускается без package.json.
- [ ] Новый native test module запуском скопированного runtime helper с --no-serve из другого cwd доказывает __file__ root, обновление только соседнего dashboard snapshot и сохранность чужих state/dashboard. Fixture root и cwd содержат пробелы/Unicode; реальные процессы сервера не стартуют.
- [ ] Cold measure CLI использует isolated child home/default .claude/projects и synthetic JSONL с ненулевыми metrics, из другого cwd. Проверяются правильный session/log selection и controlled errors; реальные домашние Claude logs/secrets не читаются. Только child env может быть fixture-local, global HOME/config не меняются.
- [ ] Read-only native cmdline(os.getpid()) для собственного test process даёт осмысленный nonempty command line на поддержанном native runner. Не применять os.kill/terminate/process cleanup, не запускать ps на Windows и не выдавать skipped/unknown за native PASS.
- [ ] Meaningful tests не ослабляют существующие regression/performance/ownership gates; production sources, runtime .autopilot и чужие tests не меняются.
- [ ] Focused + full suite + check-only + exact full-repo flake8 green; failures не обходятся blanket skip/platform exclusions. При sandbox process-query restriction использовать обычную процедуру exact approved rerun, не escalation внутри runtime.
- [ ] Выдать compact contract result и фактический verification scope. Сам ticket закрывается только после независимого review/зелёных проверок/одного отдельного development commit оркестратора. External push и native Actions proof остаются оркестратору.

## Выполнение и защищённые зоны

Сначала полностью interfaces.md, затем ticket и указанные spec sections; до первого изменения полностью skillDir/prompts/executor.md. Runtime stdlib/vanilla, без installs. Full suite: python -B -m unittest discover -s tests -v; focused: python -B -m unittest discover -s tests -p test_native_runtime.py -v; measure check-only и exact flake8 команда из AGENTS.md.
Не менять canonical sync/measure/dashboard, tests/test_sync.py и остальные tests, .autopilot/state/spec/interfaces/evidence/memory, Git config/refs, dependencies/locks или global skill/hooks/config. Не читать .env/secrets, не делать commit/push/API mutations, не останавливать реальные серверы. Root владеет metadata; T06 параллельно владеет canonical/runtime sync и tests/test_sync.py.
