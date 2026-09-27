import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "skills" / "autopilot" / "phases" / "dashboard-template.html"


def runtime_source():
    html = TEMPLATE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.DOTALL)
    return max(scripts, key=len)


def run_runtime(
    probe,
    *,
    url="http://127.0.0.1:8765/dashboard.html",
    initial_state=None,
):
    runtime = runtime_source()
    harness = f"""
const vm = require('node:vm');
const sourceNode = {{getAttribute: name => name === 'src' ? 'state.js?channel=live#state' : null}};
const metrics = {{writes: 0, queries: 0}};
const makeElement = dataset => ({{
  dataset, textContent: '', hidden: false,
  classList: {{toggle() {{}}}}, addEventListener() {{}}, setAttribute() {{}}
}});
const liveElements = Array.from({{length: 100}}, (_, i) =>
  makeElement({{from: `2026-09-10T00:${{String(i % 60).padStart(2, '0')}}:00Z`}}));
const idleElements = [makeElement({{}})];
const agoElements = [makeElement({{ago: '2026-09-10T00:00:00Z'}})];
const domNodes = [
  ...liveElements.map(node => ({{node, kind: 'live'}})),
  ...idleElements.map(node => ({{node, kind: 'idle'}})),
  ...agoElements.map(node => ({{node, kind: 'ago'}})),
  ...Array.from({{length: 5000}}, () => ({{node: makeElement({{}}), kind: 'other'}}))
];
const app = {{
  _html: '', addEventListener() {{}},
  set innerHTML(value) {{ this._html = value; metrics.writes += 1; }},
  get innerHTML() {{ return this._html; }}
}};
const document = {{
  baseURI: {json.dumps(url)}, hidden: false,
  documentElement: {{setAttribute() {{}}, removeAttribute() {{}}, lang: ''}},
  head: {{appendChild(node) {{ context.appended = node; }}}},
  getElementById: id => id === 'app' ? app : null,
  querySelector: selector => selector === 'script[data-state-source]' ? sourceNode : null,
  querySelectorAll: selector => {{
    metrics.queries += 1;
    const kind = selector === '[data-live][data-from]' ? 'live'
      : selector === '[data-idle-note]' ? 'idle'
      : selector === '[data-ago]' ? 'ago' : 'missing';
    return domNodes.filter(item => item.kind === kind).map(item => item.node);
  }},
  createElement: () => ({{remove() {{}}}}),
  addEventListener() {{}}
}};
const context = {{
  console, URL, document, location: new URL(document.baseURI),
  performance: require('node:perf_hooks').performance,
  navigator: {{language: 'ru'}}, localStorage: {{getItem() {{ return null; }}, setItem() {{}}}},
  matchMedia: () => ({{matches: false, addEventListener() {{}}}}),
  clearTimeout() {{}}, setInterval() {{}},
  window: {{STATE: {json.dumps(initial_state)}, scrollY: 0, scrollTo() {{}}}}
}};
context.setTimeout = fn => {{ context.scheduled = fn; return 1; }};
context.metrics = metrics;
context.app = app;
context.window.window = context.window;
context.window.document = document;
Object.defineProperty(context, 'STATE', {{
  get() {{ return context.window.STATE; }},
  set(value) {{ context.window.STATE = value; }}
}});
vm.createContext(context);
vm.runInContext({json.dumps(runtime + chr(10) + probe)}, context);
"""
    completed = subprocess.run(
        ["node", "-e", "eval(require('node:fs').readFileSync(0, 'utf8'))"],
        cwd=ROOT,
        encoding="utf-8",
        input=harness,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


class DashboardRuntimeTests(unittest.TestCase):
    def test_state_url_is_resolved_from_the_initial_state_script(self):
        probe = """
pollState();
scheduled();
const polled = new URL(appended.src);
console.log(JSON.stringify({state: stateURL().href, constant: STATE_URL.href,
  path: polled.pathname, channel: polled.searchParams.get('channel'),
  bust: polled.searchParams.get('t'), hash: polled.hash}));
"""
        result = run_runtime(probe)
        self.assertEqual(
            result["state"],
            "http://127.0.0.1:8765/state.js?channel=live#state",
        )
        self.assertEqual(result["constant"], result["state"])
        self.assertEqual(result["path"], "/state.js")
        self.assertEqual(result["channel"], "live")
        self.assertTrue(result["bust"].isdigit())
        self.assertEqual(result["hash"], "#state")

    def test_data_url_stays_snapshot_only(self):
        snapshot = {
            "title": "Embedded snapshot",
            "mode": "semi",
            "depth": "normal",
            "tier": "T1",
            "startedAt": "2026-09-10T00:00:00Z",
            "updatedAt": "2026-09-10T01:00:00Z",
            "requirements": {"total": 1, "done": 1},
            "stages": [],
            "tickets": [],
            "debt": {"placeholders": [], "assumptions": [], "emptyEnv": []},
        }
        probe = """
console.log(JSON.stringify({state: stateURL(), constant: STATE_URL,
  scheduled: typeof scheduled, rendered: app.innerHTML.includes('Embedded snapshot'),
  liveClaim: app.innerHTML.includes('data-auto')}));
"""
        result = run_runtime(
            probe,
            url="data:text/html,dashboard",
            initial_state=snapshot,
        )
        self.assertIsNone(result["state"])
        self.assertIsNone(result["constant"])
        self.assertEqual(result["scheduled"], "undefined")
        self.assertTrue(result["rendered"])
        self.assertFalse(result["liveClaim"])

    def test_file_url_resolves_state_beside_dashboard(self):
        probe = "console.log(JSON.stringify({state: stateURL().href, constant: STATE_URL.href}));"
        result = run_runtime(probe, url="file:///C:/work/project/.autopilot/dashboard.html")
        self.assertEqual(result["state"], "file:///C:/work/project/.autopilot/state.js?channel=live#state")
        self.assertEqual(result["constant"], result["state"])

    def test_ticket_tests_support_escaped_legacy_strings_and_object_counts(self):
        state = {
            "title": "Test formats",
            "mode": "semi",
            "depth": "normal",
            "tier": "T2",
            "startedAt": "2026-09-10T00:00:00Z",
            "updatedAt": "2026-09-10T01:00:00Z",
            "requirements": {"total": 5, "done": 5},
            "stages": [],
            "tickets": [
                {
                    "id": "01",
                    "title": "Legacy",
                    "status": "done",
                    "tests": '7 passed <script>alert("x")</script>',
                },
                {
                    "id": "02",
                    "title": "Escaped passed object",
                    "status": "done",
                    "tests": {
                        "passed": '<img src=x onerror=alert("passed")>',
                        "failed": 0,
                    },
                },
                {
                    "id": "03",
                    "title": "Escaped failed object",
                    "status": "done",
                    "tests": {
                        "passed": 1,
                        "failed": '<svg onload=alert("failed")></svg>',
                    },
                },
                {
                    "id": "04",
                    "title": "Passed object",
                    "status": "done",
                    "tests": {"passed": 3, "failed": 0},
                },
                {
                    "id": "05",
                    "title": "Failed object",
                    "status": "done",
                    "tests": {"passed": 1, "failed": 2},
                },
            ],
            "debt": {"placeholders": [], "assumptions": [], "emptyEnv": []},
        }
        result = run_runtime(
            "console.log(JSON.stringify({html: app.innerHTML}));",
            initial_state=state,
        )

        html = result["html"]
        self.assertIn(
            '7 passed &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;',
            html,
        )
        self.assertNotIn("undefined ✓", html)
        self.assertNotIn("<img src=x onerror=", html)
        self.assertNotIn("<svg onload=", html)
        self.assertIn(
            '&lt;img src=x onerror=alert(&quot;passed&quot;)&gt; ✓',
            html,
        )
        self.assertIn(
            '&lt;svg onload=alert(&quot;failed&quot;)&gt;&lt;/svg&gt; ✗',
            html,
        )
        self.assertIn("3 ✓", html)
        self.assertIn("2 ✗", html)

    def test_tick_uses_cached_dom_and_unchanged_state_does_not_render(self):
        probe = r"""
const ids = ['preflight','manifest','briefing','spec','plan','build','review','final'];
window.STATE = {
  title: 'Representative run', mode: 'semi', depth: 'normal', tier: 'T2',
  startedAt: '2026-09-10T00:00:00Z', updatedAt: '2026-09-10T01:00:00Z',
  requirements: {total: 100, done: 50, dropped: 0, deferred: 0, placeholder: 0},
  stages: ids.map((id, i) => ({id, status: i < 5 ? 'done' : 'pending',
    startedAt: i < 5 ? '2026-09-10T00:00:00Z' : null,
    finishedAt: i < 5 ? '2026-09-10T00:01:00Z' : null})),
  tickets: Array.from({length: 100}, (_, i) => ({
    id: String(i + 1).padStart(2, '0'), title: `Ticket ${i + 1}`,
    status: i < 50 ? 'done' : 'pending', wave: Math.floor(i / 10) + 1,
    requirements: [`R${i + 1}`], startedAt: '2026-09-10T00:00:00Z',
    finishedAt: i < 50 ? '2026-09-10T00:01:00Z' : null
  })),
  debt: {placeholders: [], assumptions: [], emptyEnv: []}
};
render('ru');
lastStamp = stampOf(window.STATE);
metrics.queries = 0;
const writes = metrics.writes;
const baselineTick = () => {
  const stopped = idleNow(window.STATE || {});
  document.querySelectorAll('[data-live][data-from]').forEach(el => {
    el.textContent = fmtClock(activeMs(el.dataset.from, null));
    el.classList.toggle('paused', stopped);
  });
  document.querySelectorAll('[data-idle-note]').forEach(el => { el.hidden = !stopped; });
  document.querySelectorAll('[data-ago]').forEach(el => {
    el.textContent = agoText(el.dataset.ago);
    const S = window.STATE || {};
    const busy = (S.tickets || []).some(t =>
      t.status === 'in-progress' || t.status === 'review' || t.status === 'repair');
    el.classList.toggle('stale', !S.finishedAt
      && spanMs(el.dataset.ago, null) > (busy ? 2700000 : 300000));
  });
};
const measure = fn => {
  const samples = [];
  for (let round = 0; round < 5; round++) {
    const start = performance.now();
    for (let i = 0; i < 1000; i++) fn();
    samples.push(performance.now() - start);
  }
  return samples.sort((a, b) => a - b)[2];
};
for (let i = 0; i < 100; i++) { baselineTick(); tick(); }
metrics.queries = 0;
const baselineMs = measure(baselineTick);
const baselineQueries = metrics.queries;
metrics.queries = 0;
const tickMs = measure(tick);
const tickQueries = metrics.queries;
applyState();
console.log(JSON.stringify({tickQueries, baselineQueries,
  baselineMs, tickMs, renderWrites: metrics.writes - writes}));
"""
        result = run_runtime(probe)
        self.assertGreater(result["baselineQueries"], 0)
        self.assertEqual(result["tickQueries"], 0)
        self.assertLessEqual(result["tickMs"], result["baselineMs"])
        self.assertEqual(result["renderWrites"], 0)
        print(
            "dashboard benchmark: "
            f"tick={result['tickMs']:.2f}ms baseline={result['baselineMs']:.2f}ms, "
            f"DOM queries={result['tickQueries']}/{result['baselineQueries']}"
        )


if __name__ == "__main__":
    unittest.main()
