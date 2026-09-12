# 03 — Единый state path и быстрый tick дашборда

**Требования:** R11, R12, R15, R16, R19, R21, R23, R24
**Blocked by:** 01
**Зона:** `skills/autopilot/phases/dashboard-template.html`, `tests/test_dashboard.py`
**Волна:** 2
**Status:** done-with-concerns

## Что должно заработать

Initial load и poller используют один вычисленный URL соседнего `state.js`; cache busting не ломает query/hash. Ежесекундный tick не повторяет DOM queries для неизменной структуры, а render не запускается без нового stamp. Поведение file/http/data snapshot сохраняется.

## Из брифа, дословно

> «логику подстановки путей статических ресурсов в `dashboard-template.html`»
> «Улучшить скорость рендеринга дашборда»

## Разделы спецификации

§§4, 6, 9, 11–12.

## Критерии приёмки

- [x] Initial/poll path имеет один источник истины и корректно резолвится рядом с dashboard.
- [x] Неизменившийся stamp не вызывает render; scroll, RU/EN, theme и snapshot fallback сохранены.
- [x] 1 000 `tick()` на состоянии со 100 тасками не медленнее baseline и минимум на 20% сокращает DOM-query invocations.
- [ ] Browser smoke: HTTP подтверждён реальным браузером исполнителя; file path и data snapshot покрыты harness, повторный file smoke перенесён в T04 из-за ошибки CUA kernel assets.
- [x] Focused и полный доступный локальный gate зелёные.

## Результат

- Commit: `dc70117`
- Проверки: `python -m unittest tests.test_dashboard -v` → 4 passed; full suite → 20 passed; `measure-run --check-only` → exit 0.
- Benchmark: 1 000 `tick()` → 462.19ms против baseline 708.37ms; DOM queries 0/3000.
- Локальный `flake8`: NOT_RUN; CUA file smoke: NOT_RUN из-за `failed to write kernel assets`; оба входят в финальную T04-приёмку.
