# ADR 0003: Single-source dashboard state and incremental rendering

## Context

Дашборд загружал `state.js` разными относительными путями при initial load и polling и каждую секунду повторял DOM-сканирования и полный render. Это ломает соседний ресурс при разных схемах URL и создаёт ненужную нагрузку на больших состояниях.

## Decision

Вычислять один `STATE_URL` из URL исходного `<script data-state-source>` и использовать его для initial load и poller. Для `file:` и `http:` он указывает на соседний `state.js`; для `data:` единственным источником остаётся встроенный snapshot. Cache busting добавлять через `URL.searchParams`. `tick()` использует один snapshot `STATE`, один busy-state и кэшированные коллекции DOM-элементов; кэши обновляются только после `render()`, а полный render выполняется только при изменении stamp из `updatedAt`, `finishedAt` и числа задач.

## Why

Один вычисленный URL устраняет расхождение между первой загрузкой и polling и корректно сохраняет существующие query/hash. Stamp отделяет изменение данных от обновления часов, а DOM-кэши устраняют повторные запросы к неизменившемуся дереву.

## Consequences

Один неизменившийся poll не вызывает render, а 1 000 вызовов `tick()` после render должны быть не медленнее baseline и сокращать DOM-query invocations минимум на 20%. Контракт `state.js` обязан менять `updatedAt` при каждом значимом обновлении; иначе обновление может не попасть в render. Offline snapshot, file/http/data режимы, theme, RU/EN, scroll position и progress math должны сохраняться.
