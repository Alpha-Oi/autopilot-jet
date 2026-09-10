# 03 — Единый state path и быстрый tick дашборда

**Требования:** R11, R12, R15, R16, R19, R21, R23, R24
**Blocked by:** 01
**Зона:** `skills/autopilot/phases/dashboard-template.html`, `tests/test_dashboard.py`
**Волна:** 2
**Status:** ready

## Что должно заработать

Initial load и poller используют один вычисленный URL соседнего `state.js`; cache busting не ломает query/hash. Ежесекундный tick не повторяет DOM queries для неизменной структуры, а render не запускается без нового stamp. Поведение file/http/data snapshot сохраняется.

## Из брифа, дословно

> «логику подстановки путей статических ресурсов в `dashboard-template.html`»
> «Улучшить скорость рендеринга дашборда»

## Разделы спецификации

§§4, 6, 9, 11–12.

## Критерии приёмки

- [ ] Initial/poll path имеет один источник истины и корректно резолвится рядом с dashboard.
- [ ] Неизменившийся stamp не вызывает render; scroll, RU/EN, theme и snapshot fallback сохранены.
- [ ] 1 000 `tick()` на состоянии со 100 тасками не медленнее baseline и минимум на 20% сокращает DOM-query invocations.
- [ ] Browser smoke подтверждает file/http; data mode показывает snapshot без ложного live claim.
- [ ] Focused и полный локальный gate зелёные.
