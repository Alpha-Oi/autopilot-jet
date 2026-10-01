# DOA conformance assessment

**Assessed:** 2026-10-01
**Subject:** autopilot-jet on `development` at `8c8cb33353df35c2831d977ad5d81922191738d9`
**Standard:** Digital Organism Architecture `DOA-FS-1.0` (release `v1.0.0`), profile Core
**Claim:** [`DOA_CONFORMANCE_CLAIM.yaml`](DOA_CONFORMANCE_CLAIM.yaml): status `PARTIAL`, self-assessed, not independent.

## 1. What was assessed, and how

Autopilot JET is an agent skill. Its behaviour has two layers:

1. **Instructions** (`skills/autopilot-jet/SKILL.md`, `phases/`, `prompts/`): a process the host LLM executes. They define the manifest, gates, subagent roles, caps, repair and shutdown rules.
2. **Deterministic code**: `skills/autopilot-jet/tools/sync.py` (state, snapshot, dashboard server lifecycle), the dashboard template, `tools/measure-run.py`, and the CI in `.github/workflows/verify.yml`.

DOA conformance is evidence-based. Evidence in this repository is strong for layer 2 and is documentation for layer 1. The assessment treats the whole skill as the organism and the host agent, LLM provider, git remotes and installer as external dependencies.

Evidence reproduced during this assessment (Linux, Python 3.11.15, Node 22.22.0, commit `8c8cb33`):

| Check | Result |
|---|---|
| `python -B -m unittest discover -s tests -v` | 40 tests, OK |
| `flake8 . --select=E9,F63,F7,F82` (7.4.1) | 0 findings |
| `python -B tools/measure-run.py --check-only` | OK |
| CI run for the same commit ([run 58](https://github.com/Alpha-Oi/autopilot-jet/actions/runs/36579354199)) | success on ubuntu, windows and macos |
| Repository settings (public API) | secret scanning and push protection enabled; **no branch rules on `development` or `main`** |

An end-to-end run of the skill was not executed. The author's local governance harness (45/45) and release-finalization evidence are not in the repository and were not used.

## 2. Result

| Status | Count |
|---|---|
| PASS | 1 |
| PARTIAL | 24 |
| FAIL | 3 |
| EXCLUDED | 1 |
| Total (Core 26 + Conditional 3) | 29 |

The claim is `PARTIAL`, not `VERIFIED`: one requirement has a full PASS, most have a real mechanism that is documented but not enforced or tested, and three have no mechanism.

**Strongest areas:** truthful uncertainty (unknown process status is never treated as absent or healthy, with tests), desired/observed separation (manifest versus blind acceptance), bounded loops (ticket, repair, handoff and polish caps), role separation (executor, reviewer, blind checker), and honest provenance of decisions (ADRs, one commit per ticket).

## 3. Requirement-by-requirement

| ID | Requirement | Status | What exists | Gap | Suggested action |
|---|---|---|---|---|---|
| REQ-CORE-01 | Identity of every action | PARTIAL | Commits per ticket; ticket/stage records in state.js; measure-run attributes tokens to orchestrator and subagent contexts from host logs. | No record binds each action to a subject (which subagent, which host/model, which skill version). Skill version is not stamped into the run. | Stamp skill version, host and agent role into state.js tickets; low effort. |
| REQ-CORE-02 | Declared organism boundary | PARTIAL | Dashboard server binds only 127.0.0.1 (code and test); user input passes a redaction gate; irreversible/outward actions are questions (rule 4). | No declared boundary or external-dependency register (host agent, LLM provider, git remote, npx installer). Ingress and egress are described in prose only. | Add a short boundary table to AGENTS.md: what is inside the skill, what is the host, what crosses the boundary. |
| REQ-CORE-03 | Desired/observed separation | PARTIAL | Requirements manifest is the desired state; blind acceptance against the brief is the observed state; disagreements are reported as drift. Strong design. | Desired state is not integrity-protected (no hash or signature); the reconcile step is executed by the LLM following prose, with no deterministic check or test. | Record a content hash of brief.md and manifest.md in state.js; verify it in sync.py audit(). |
| REQ-CORE-04 | Genome/epigenome separation | PARTIAL | Run-level overlays (mode/depth/polish) are resolved once, recorded, and cannot remove the manifest and safety gates. | Overlays do not expire, are not signed, and the effective policy of a run is not reconstructable from a record. | Persist resolved dials in state.js (done for some) and document that they may not widen authority. |
| REQ-CORE-05 | Least capability and attenuation | PARTIAL | Executors get a ticket zone and an explicit 'must not touch' list; zones in a wave are disjoint; secrets travel as variable names only. | Capabilities are instructions, not grants: nothing technically stops a subagent from touching files outside its zone; permissions are whatever the host gives. | Add a post-ticket deterministic check that changed files stay inside the ticket zone (git diff --name-only vs zone). |
| REQ-CORE-06 | No unilateral self-modification | PARTIAL | The orchestrator may write only .autopilot/, the memory file and git; the helper updates only its adjacent snapshot (tested); runtime copies of sync.py/dashboard are re-copied from the skill, not edited. | The rule that the orchestrator does not write project code is a prose rule for an LLM; there is no technical guard and no test of the rule itself. | Consider a host-level hook or a post-hoc diff check that orchestrator commits touch only allowed paths. |
| REQ-CORE-07 | Closed-loop homeostasis | PARTIAL | Bounded loops with caps and stop conditions: repairs/retries/handoffs capped at 2, polish capped at 3 rounds with whole-round rollback, executor ceiling about 50 tool calls. | No ControlLoopSpec: no declared variable, sensor freshness, target range, escalation or manual override per loop; bounds are prose numbers for the LLM. | Declare the loops (repair, handoff, polish, idle server) in one table with variable, limit, escalation, override. |
| REQ-CORE-08 | Compartmentalization | PARTIAL | One executor context per ticket, never two tickets in one context; at most three in flight; same-file tickets are serialised. | Isolation and the three-in-flight cap are prose; no test or runtime check; a failing subagent's blast radius is not measured. | Record in state.js how many tickets were in flight at once; assert the cap in a unit test of the planner output if one is added. |
| REQ-CORE-09 | Provenance | PARTIAL | Dated redacted brief, manifest rows with stated basis, one commit per ticket, run record committed, decisions as ADRs. | Source and time exist; integrity (hash) and classification do not. Provenance of agent output (model, version) is not recorded in repo. | Add content hashes for brief and manifest and the host/model metadata to state.js. |
| REQ-CORE-10 | Reversibility | PARTIAL | Commit per ticket gives rollback points; a polish round that breaks the suite is reverted whole; ship.ps1 stops on red checks and never forces or touches main. | Rollback is a documented procedure, not tested; no automated restore drill. | Add a test or fixture for the polish-round revert command sequence. |
| REQ-CORE-11 | Observable lifecycle | PARTIAL | Stage and ticket transitions are recorded; sync.py enforces the 'one active stage' invariant and reports half-written transitions. | No formal state machine with guards, authority and timeouts; close_passed() and audit() have no unit tests (tests cover server lifecycle, dashboard render, measure-run). | Add unit tests for close_passed() and audit(); publish stage/ticket state machines as a table. |
| REQ-CORE-12 | Human authority | PARTIAL | Only the user removes a requirement; irreversible or outward-facing actions (deploy, publish, pay, message, delete, rewrite history) are questions in every mode. | Enforced by instruction to the LLM; no technical approval gate; no time-bounded break-glass concept. | Keep as policy but add an explicit list of actions that require confirmation to a testable config. |
| REQ-CORE-13 | Truthful uncertainty | PASS | Unknown is never reported as healthy or absent: process_status() returns present/absent/unknown; unknown ownership never triggers a duplicate launch or registry rewrite; corrupt state.js is rejected without writes; partial requirements do not inflate coverage. Tests pass locally (40) and in CI on three OSes. | Scope of the PASS: the deterministic helper, dashboard and measure-run. Truthfulness of the orchestrator's own reports rests on blind acceptance (prose, not unit-tested). | Keep; extend the same discipline to reports (a test that 'done' without blind confirmation is not shown as complete). |
| REQ-CORE-14 | Immune response lifecycle | PARTIAL | A leaked secret is a stop condition with a user warning and rotation advice; three-axis review per ticket; GitHub secret scanning and push protection are enabled on the repository. | No incident lifecycle (identify, contain, quarantine, neutralize, learn, update defences) for a run; quarantine of a bad artifact is not defined. | Define a minimal incident path for a leaked secret: stop, scrub history guidance, record in state.js. |
| REQ-CORE-15 | Bounded termination (apoptosis) | PARTIAL | On finish the run is closed (finishedAt), the helper never relaunches a server for a finished run (tested), and only the run's own server is killed after the report. | Termination of subagents and release of all run resources is not a bounded, verified protocol; no terminal record beyond state.js. | Write the terminal checklist as a verification step in sync.py (no live server, finishedAt set). |
| REQ-CORE-16 | Uncontrolled failure containment (necrosis) | PARTIAL | Interrupted runs resume from files; ownership checks refuse to kill foreign processes (tested); a second window on a live run is detected. | No fencing of a lost subagent: a crashed executor's partial edits are handled by the orchestrator by instruction, not by a revocation mechanism. | Document and test the partial-edit recovery path (git status before re-dispatch). |
| REQ-CORE-17 | Growth control | PARTIAL | Tickets capped at 16 per run, 3 in flight, 2 repairs/retries/handoffs per ticket, 3 polish rounds; the orchestrator does not grant itself authority. | Caps are prose numbers; no enforcement and no orphan detection; spawn depth (subagents spawning subagents) is not bounded explicitly. | State a maximum subagent nesting depth and check it in state.js. |
| REQ-CORE-18 | Resource accounting | PARTIAL | Token and time metrics per context (tested); the ceiling is justified with measured numbers. | Measurement is after the fact and Claude-Code-log specific; there is no budget reserved or enforced per run and no scarcity gate. | Add an optional per-run token budget to state.js and a warning in sync.py when exceeded. |
| REQ-CORE-19 | Memory governance | PARTIAL | Project memory is written from the finished code, inside autopilot markers, user text untouched; run record kept in .autopilot; decisions as ADRs. | No retention, decay or erasure policy; memory records carry no confidence or provenance fields; stale memory is possible (AGENTS.md test counts lag the code). | Add a freshness check for AGENTS.md facts that can be verified (test count, commands). |
| REQ-CORE-20 | Recovery taxonomy | PARTIAL | Recovery paths exist and differ: resume from files, repair in the same context, rebuild in a fresh context, whole-round rollback, dashboard regenerated from the template each flight. | Permitted recovery modes are not declared per component; the rule against cloning corrupted state is implicit. | Add a short recovery table (mode, when, verification) to AGENTS.md. |
| REQ-CORE-21 | Aging and senescence | FAIL | The skill notes that an installed global copy may differ from the checkout, and README documents an update command. | No aging or version-skew mechanism: no skill-version stamp in runs, no staleness check of installed vs source skill, no deprecation path for old runs. | Stamp skill version into state.js and warn when the installed skill differs from the repository version. |
| REQ-CORE-22 | Identity continuity and anti-resurrection | FAIL | Closest: finishedAt closes a run and the helper refuses to relaunch a server for it. | No identity continuity record, tombstone or fencing: a finished or abandoned run directory can be resumed without any check that it is still valid. | Mark closed runs with a terminal marker that resume refuses without explicit user action. |
| REQ-CORE-23 | Failure-class coverage | PARTIAL | Failure kinds are named (nedodelka vs otkaz), the audit lists known gaps, ADR 0006 documents the unknown-process case. | No per-class table with detection, containment, recovery and verification for the failure classes of the standard. | Map the existing failure kinds to the DOA failure-class list in one table. |
| REQ-CORE-24 | Audit and secret hygiene | PARTIAL | Secrets are redacted before writing and referred to by name; .env is gitignored first; GitHub secret scanning and push protection are enabled. | The redaction gate is an instruction to the orchestrating agent; the repository contains no deterministic implementation or test of it, although the README describes it as a filter. The audit trail (.autopilot) is not tamper-evident. | Implement the pattern table of 1-manifest.md as a stdlib script with tests and run it over .autopilot/ before commit. |
| REQ-CORE-25 | Microbiome (guest) governance | EXCLUDED | The skill neither loads nor admits third-party plugins, tools or agents: it is dependency-free (CI step 'Confirm dependency-free dashboard' passes; no package.json) and its subagents are instances of the host agent configured by the host. Guest governance belongs to the host. Revisit if the skill ever bundles an external tool. | — | Revisit if the skill ever bundles an external tool. |
| REQ-CORE-26 | Separation of cognition and authority | PARTIAL | Roles are separated: executor writes, an independent reviewer judges, a blind checker verifies against the brief; the orchestrator does not write code. | Policy authority is the same LLM family following prose; there is no deterministic policy enforcement point. | Move the few hard rules (secrets, commit-on-red, zone) into deterministic checks run by the orchestrator. |
| REQ-COND-01 | Reproduction control | PARTIAL | The skill does not create other Autopilot instances; a second run on a live .autopilot is detected and stops for the user. | No explicit declaration that reproduction is forbidden and no enforcement test. | State 'no nested or parallel Autopilot runs' as a rule and test the concurrent-run detection. |
| REQ-COND-02 | Federation and treaties | FAIL | No federation capability exists in the repository. | No declared prohibition (federation: none) and no enforcement; the standard asks for it explicitly. | Add the declaration to AGENTS.md; nothing to build. |
| REQ-COND-03 | Horizontal transfer isolation | PARTIAL | The skill is dependency-free (CI confirms no package.json) and is documented not to install or download anything without the user's knowledge. | Prose only; no technical gate for importing artifacts from other sources into a run. | Keep dependency-free; add a CI assertion that no package manifests exist. |

## 4. Principal findings

1. **Hard rules are instructions, not code.** Secret redaction, 'nothing committed on red', 'the orchestrator does not write project code', ticket zones and the irreversible-action rule are enforced by prose for an LLM. The README describes redaction as a filter; the repository has no implementation or test of it. This is the largest gap against DOA (REQ-CORE-24, 05, 06, 26). *Action:* implement the pattern table from `phases/1-manifest.md` as a stdlib script with tests; add a zone check on `git diff --name-only`.
2. **Process invariants in `sync.py` are untested.** `close_passed()` and `audit()` carry the lifecycle invariants (REQ-CORE-11) but no test exercises them. *Action:* add unit tests.
3. **No server-side branch rules.** `development` and `main` have no rules, so PR-first and green-CI-before-merge (`CONTRIBUTING.md`) are policy, not enforcement. The repository is public, so rulesets are available. *Action:* a ruleset requiring the CI check.
4. **CI workflow has no `permissions:` block** and uses tag-pinned actions (`@v4`, `@v5`). *Action:* `permissions: contents: read` and SHA pinning.
5. **Memory drift.** `AGENTS.md` reports 33 tests; the suite now has 40. *Action:* a freshness check for verifiable facts in the memory file.
6. **No aging or version-skew handling** (REQ-CORE-21) and **no terminal marker for closed runs** (REQ-CORE-22): runs do not record the skill version and a closed run can be resumed without a check.

## 5. Out of scope and limits

- Distributed, Adaptive and Embodied profiles are not claimed.
- The assessment is by an AI assistant from reading the repository and re-running its checks; it is not independent and does not replace review of the evidence.
- Statements about LLM behaviour are statements about instructions, not observed runs.

## 6. Reassessment

Reassess after the actions above or by 2026-12-01. From the DOA repository:

```bash
python scripts/check_conformance_claim.py docs/conformance/DOA_CONFORMANCE_CLAIM.yaml
```
