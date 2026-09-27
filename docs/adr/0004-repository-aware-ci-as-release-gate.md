# ADR 0004: Repository-aware CI as the release gate

## Context

Предложенный workflow ссылается на отсутствующие `package.json`, npm lockfile и `инструменты/measure-run.py`. Его дословное применение гарантированно создаёт красный CI и не может служить доказательством качества.

## Decision

Сохранить имя workflow, triggers, версии Actions, Python 3.11, Node 20 и flake8-команду, но минимально адаптировать repo-specific шаги к фактическому дереву. npm install выполняется только при наличии `package.json`; без него workflow явно отмечает dependency-free dashboard. Измеритель запускается как `python tools/measure-run.py --check-only`. Gate также включает `python -m unittest discover -s tests -v`; внутри этого suite `test_dashboard.py` выполняет Node VM runtime/performance-проверки. Реальный browser smoke не запускается в CI и остаётся отдельным локальным/final acceptance evidence.

## Why

Quality gate имеет смысл только тогда, когда его команды соответствуют реальным entry points и зависимостям репозитория. Минимальная коррекция сохраняет намерение исходного шаблона, одновременно делая результат локально воспроизводимым и пригодным для блокировки ошибочного изменения.

## Consequences

Любой ненулевой код локального эквивалента CI блокирует commit. Финальная внешняя приёмка требует фактически успешного GitHub Actions run на опубликованной ветке `development`; локальный зелёный прогон его не заменяет. Отклонения от дословного шаблона должны быть перечислены в итоговом отчёте, а новые production dependencies ради CI не добавляются.
