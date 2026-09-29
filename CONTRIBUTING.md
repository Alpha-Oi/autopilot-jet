# Как предложить правку

Спасибо, что хотите улучшить Autopilot. Коротко о том, как это устроено.

## Перед началом

- Нужны Python 3.11+ и Node.js 20+. Устанавливать пакеты не требуется: проект использует только стандартную библиотеку и HTML/JavaScript без зависимостей.
- Единственный исходник навыка — [`skills/autopilot-jet/`](skills/autopilot-jet). Папки `.agents/skills/autopilot-jet` и `.claude/skills/autopilot-jet` — ссылки на него, править их не нужно.
- Дашборд собирается из шаблона `skills/autopilot-jet/phases/dashboard-template.html`. Правьте шаблон, а не копию в `.autopilot/`.

## Проверка

Перед pull request запустите то же, что запускает CI:

```bash
python -m unittest discover -s tests -v
python tools/measure-run.py --check-only
pip install flake8 && flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

CI повторяет эти команды на Windows, Ubuntu и macOS — pull request сливается, когда все три зелёные.

## Правила

- Один pull request — одна тема. Не смешивайте функцию, форматирование и обновление зависимостей.
- Поведение, которое можно сломать, защищайте тестом в `tests/`.
- Решения, которые нельзя восстановить из кода (почему сделано так, а не иначе), записывайте как ADR в [`docs/adr/`](docs/adr).
- В коммитах и pull request не должно быть ключей, токенов, `.env` и локальных путей вашего компьютера.

## Ветки

Основная ветка — `development`, в `main` попадают только релизы. Открывайте pull request в `development`.
