window.STATE =
{
  "slug": "autopilot-pathing-hardening",
  "dir": "2026-09-10-autopilot-pathing-hardening--wip",
  "title": "Кроссплатформенный Autopilot и быстрый дашборд",
  "mode": "full",
  "depth": "deep",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-10-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "C:\\Users\\Crown-Aliy\\.agents\\skills\\autopilot",
  "startedAt": "2026-09-10T23:25:26.9499987+03:00",
  "updatedAt": "2026-09-11T00:08:35.6028073+03:00",
  "finishedAt": null,
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-09-10T23:25:26.9499987+03:00", "finishedAt": "2026-09-10T23:28:39.9995907+03:00" },
    { "id": "manifest", "status": "done", "startedAt": "2026-09-10T23:28:39.9995907+03:00", "finishedAt": "2026-09-10T23:33:37.8823878+03:00" },
    { "id": "briefing", "status": "skipped", "startedAt": "2026-09-10T23:33:37.8823878+03:00", "finishedAt": "2026-09-10T23:35:40.0710546+03:00", "note": "полный автомат — самобрифинг" },
    { "id": "spec", "status": "done", "startedAt": "2026-09-10T23:35:40.0710546+03:00", "finishedAt": "2026-09-10T23:44:53.1001545+03:00" },
    { "id": "plan", "status": "done", "startedAt": "2026-09-10T23:44:53.1001545+03:00", "finishedAt": "2026-09-10T23:47:33.4484312+03:00", "note": "4 таска, ярус T2; CI и measure-run объединены merge-pass" },
    { "id": "build", "status": "active", "startedAt": "2026-09-10T23:47:33.4484312+03:00", "note": "0 из 4 тасков готовы" },
    { "id": "review", "status": "active", "startedAt": "2026-09-11T00:08:00+03:00", "note": "таск 01: blocking repair — отдельный empty JSONL test" },
    { "id": "final", "status": "pending" }
  ],
  "requirements": {
    "total": 32, "done": 0, "inTicket": 29, "inSpec": 0,
    "placeholder": 0, "deferred": 3, "dropped": 0
  },
  "tickets": [
    {
      "id": "01", "title": "Работающий CI и переносимый measure-run.py",
      "requirements": ["R08", "R09", "R10", "R12", "R14", "R15", "R16", "R18", "R19", "R22", "R23", "R25"],
      "blockedBy": [], "wave": 1,
      "zone": [".github/workflows/verify.yml", "tools/measure-run.py", "tests/test_measure_run.py"],
      "status": "repair", "startedAt": "2026-09-10T23:52:58.3551873+03:00",
      "retries": 0, "repairs": 1, "handoffs": 0
    },
    {
      "id": "02", "title": "Кроссплатформенный sync.py",
      "requirements": ["R11", "R12", "R15", "R16", "R22", "R23"],
      "blockedBy": ["01"], "wave": 2, "zone": ["skills/autopilot/tools/sync.py", "tests/test_sync.py"],
      "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0
    },
    {
      "id": "03", "title": "Единый state path и быстрый tick дашборда",
      "requirements": ["R11", "R12", "R15", "R16", "R19", "R21", "R23", "R24"],
      "blockedBy": ["01"], "wave": 2, "zone": ["skills/autopilot/phases/dashboard-template.html", "tests/test_dashboard.py"],
      "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0
    },
    {
      "id": "04", "title": "Интеграционная приёмка, память и публикация",
      "requirements": ["R02", "R05", "R06", "R07", "R08", "R09", "R13", "R15", "R16", "R17", "R20", "R23", "R24", "R25", "R26", "R27", "R28", "R29", "R30", "R31", "R32i"],
      "blockedBy": ["01", "02", "03"], "wave": 3,
      "zone": ["AGENTS.md", "CLAUDE.md", ".autopilot/", "GitHub release boundary"],
      "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0
    }
  ],
  "singlePass": null,
  "tests": null,
  "debt": {
    "placeholders": [],
    "assumptions": [
      "Минимальная кроссплатформенность: Windows, Linux, macOS; cwd не влияет.",
      "AGENTS.md канонический; CLAUDE.md хранит compact mirror.",
      "Нерабочие repo-specific строки CI-шаблона исправляются минимально.",
      "Repo-local Git identity вместо глобальной конфигурации машины."
    ],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "findings": 9,
    "resolved": 9,
    "result": "G2 passed: missing 0, half-covered 0",
    "actions": [
      "Явно оформлены host-model, Git identity и CI-template ограничения.",
      "Добавлено правило 100% phase contract и полный охват текущих scripts/HTML paths.",
      "Закреплены физическое состояние в обоих memory files и обязательный lease force update development."
    ]
  },
  "concerns": [
    "Исходный CI-шаблон ссылается на отсутствующие package.json и инструменты/measure-run.py.",
    "sync.py падает на Windows из-за безусловного вызова Unix-команды ps.",
    "Ускорение дашборда требует воспроизводимого baseline и бюджета регрессии.",
    "Заданный Git email синтаксически ошибочен; глобальный config выходит за scope репозитория.",
    "AGENTS.md должен быть каноном, а CLAUDE.md — указателем, чтобы память не расходилась.",
    "100% готовность допустима только после фактически зелёного CI и blind acceptance.",
    "Публикация должна сохранить upstream-историю и не менять main до финальной фазы.",
    "craft · tests/test_measure_run.py:29 · mixed malformed JSONL test использует нулевой oracle; финальная triage должна проверить ненулевой наблюдаемый результат.",
    "craft · tests/test_measure_run.py:53 · произвольный cwd проверен исполнителем вручную, но не закреплён subprocess-тестом.",
    "craft · tests/test_measure_run.py:61 · тест выбора сессии связан со скрытыми glob/getsize/analyse вместо публичного main(argv).",
    "craft · tests/test_measure_run.py:24 · default root при root=None не закреплён отдельным тестом смены cwd."
  ],
  "reviewers": { "manifestSpec": "/root/review_manifest_spec", "craft": "/root/review_craft" },
  "blind": null
}
