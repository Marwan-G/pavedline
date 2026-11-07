# Pavedline v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** an installable Claude Code plugin marketplace whose `pavedline` plugin runs steps 0–3 (start, market + SEO
research, grill, spec) with file-based memory, enforced hooks, `doctor`, and a local Kubernetes cluster (kind +
ArgoCD + CNPG), with its own CI.

**Architecture:** the repo root is a marketplace (`.claude-plugin/marketplace.json`) listing one plugin at
`plugins/pavedline/`. The plugin ships skills (Markdown), one agent, settings hooks (Python 3 stdlib scripts), a
pinned Playwright MCP, and templates that `/pavedline:start` copies into a product repo. Repo-level `scripts/` hold
the factory's own CI tools. Everything is tested with `python3 -m unittest` (stdlib only) plus CI jobs.

**Tech stack:** Python 3.10+ stdlib · Bash · Graphviz · kind v0.33.0 · Helm · Argo CD chart 10.15.0 · CloudNativePG
chart 0.29.1 · kind node `kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5`
· `@playwright/mcp@0.0.84` · Claude Code 2.1.319 (CI) · gitleaks v8.30.1 · GitHub Actions. (All versions verified
2026-11-07.)

**Spec:** `docs/superpowers/specs/2026-11-07-pavedline-design.md` (read §5, §6.1, §6.2, §6.5, §7, §9.3, §10, §11.6,
§12, §13, §16, §17 before starting).

## Global Constraints

- **Nothing is pushed** until the founder says so; commit locally after every task.
- No private identifiers anywhere (no product names other than Pavedline, no employer, no usernames, no local paths,
  no cloud IDs). The deny-list scan (Task 2) must pass on every commit.
- Python scripts and hooks use the **standard library only**; target Python 3.10+.
- Hooks read the JSON object on stdin; `PreToolUse` blocks with **exit 2 and a reason on stderr**; any other failure
  path exits 0 with a stderr note (fail open), except the secret guard (§12.4).
- Bash tool input: `tool_input.command`. Read/Write/Edit: `tool_input.file_path`; Write content `tool_input.content`;
  Edit `tool_input.old_string` / `tool_input.new_string` (verify the Write/Edit field names against a captured hook
  payload in Task 4, step 1, and adjust the fixtures if they differ).
- `STATE.md` ≤ 60 lines; template `CLAUDE.md` ≤ 150 lines.
- Local cluster name `pavedline-<project>`; kube context prefix `kind-pavedline-`.
- Skill names are kebab-case and equal their directory name; each `SKILL.md` ≤ 500 lines with detail in
  `references/`.
- Model policy: `config/models.yaml` holds `role: model` lines; agents' `model:` lines are generated from it.
  Defaults: `orchestrator: opus`, `designer: opus`, every other role `sonnet`. Never `haiku`.
- Exact step-0 compliance wording (§6.1): "Should we design with compliance in mind (privacy laws such as GDPR,
  health or payment rules)? Recommended: yes."
- Privacy line (§2): "Pavedline collects nothing. Every answer stays in your own repository."
- Dependencies for v0.1: `superpowers@claude-plugins-official`, `mattpocock-skills@claude-plugins-official`,
  `product-management@knowledge-work-plugins`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Deferred to v0.3 (CI already enforces both):** the two warning-only hooks of design §12.4 (`.dot` drift warning,
  PR-body gates-line warning).

## Review Focus

1. **Malformed hook input** (empty stdin, non-JSON, missing `tool_input`): the hook must not block the session; it
   exits 0 with a stderr note. Exception: the secret guard blocks when it can still read a `.env*` target path.
   → tests in Task 4 and Task 5.
2. **Cluster-guard bypasses:** `kubectl --context prod delete ns x`, `kubectl get pods && kubectl delete ns x`,
   `helm upgrade …` while the current context is not `kind-pavedline-*` must block; `kubectl get`, `describe`,
   `logs` and `helm list` must pass. → Task 5.
3. **`.env` look-alikes:** `.env.example`, `.env.sample` and `.env.template` are allowed; `.env`, `.env.local`,
   `config/.env.production` and `cat .env` through Bash are blocked. → Task 4.
4. **`start` into a non-empty repo:** existing `CLAUDE.md` or `STATE.md` is never overwritten; the script lists the
   conflicts and exits 1 without writing anything. → Task 8.
5. **Deny-list scan on binary and SVG files:** binary files (contain a NUL byte) are skipped; SVG is text and is
   scanned. → Task 2.

---

### Task 1: Repository skeleton, marketplace and plugin manifest

**Files:**
- Create: `LICENSE` (MIT, "Copyright (c) 2026 Marwan Ghubein"), `VERSION` (`0.1.0`), `CHANGELOG.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `.gitignore`
- Create: `.claude-plugin/marketplace.json`, `plugins/pavedline/.claude-plugin/plugin.json`,
  `plugins/pavedline/.mcp.json`
- Test: `tests/test_manifests.py`

**Interfaces:**
- Produces: marketplace name `pavedline`; plugin name `pavedline`, version `0.1.0`; `.gitignore` includes
  `.sanitize-denylist.local`, `.env.local`, `__pycache__/`.

- [ ] **Step 1: Write the failing test** `tests/test_manifests.py`:
  - `test_marketplace_lists_pavedline`: `marketplace.json` has `"name": "pavedline"`, a plugin entry with
    `"source": "./plugins/pavedline"`, and `allowCrossMarketplaceDependenciesOn` ==
    `["claude-plugins-official", "knowledge-work-plugins"]`.
  - `test_plugin_manifest`: `plugin.json` has `name == "pavedline"`, `version == read("VERSION").strip()`,
    `license == "MIT"`, and `dependencies` equal to the three entries in Global Constraints (as `name@marketplace`
    strings).
  - `test_mcp_pins_playwright`: `.mcp.json` has a `playwright` server whose args contain `@playwright/mcp@0.0.84` and
    `--headless`.
- [ ] **Step 2:** `python3 -m unittest tests.test_manifests -v` → FAIL (files missing).
- [ ] **Step 3:** create the files. `plugin.json` also carries `displayName: "Pavedline"`, a `description` (the
  one-line promise), `author: {"name": "Marwan Ghubein", "url": "https://www.linkedin.com/in/marwan-ghubein/"}`,
  `homepage`/`repository` `https://github.com/Marwan-G/pavedline`, `keywords`.
- [ ] **Step 4:** rerun the test → PASS; then `claude plugin validate . --strict` and
  `claude plugin validate plugins/pavedline --strict` → `Validation passed`.
- [ ] **Step 5: Commit** `feat: marketplace and plugin skeleton`.

### Task 2: Deny-list scan

**Files:**
- Create: `scripts/sanitize_scan.py`, `.sanitize-denylist`
- Test: `tests/test_sanitize_scan.py`

**Interfaces:**
- Produces: `scan(paths: list[pathlib.Path], patterns: list[re.Pattern]) -> list[Finding]` where
  `Finding = NamedTuple(path: str, line: int, pattern: str)`; `load_patterns(repo_root) -> list[re.Pattern]` reads
  `.sanitize-denylist` plus `.sanitize-denylist.local` if present (one regex per line; `#` comments). CLI:
  `python3 scripts/sanitize_scan.py` scans `git ls-files` (excluding both deny-list files), prints `path:line: pattern`
  per finding, exits 1 if any.
- `.sanitize-denylist` (generic only): `ocid1\.`, private IPv4 literals (`\b10\.\d+\.\d+\.\d+\b`,
  `\b192\.168\.\d+\.\d+\b`, `\b172\.(1[6-9]|2\d|3[01])\.\d+\.\d+\b`), `-----BEGIN [A-Z ]*PRIVATE KEY-----`,
  `\bghp_[A-Za-z0-9]{36}\b`, `\bsk-ant-[A-Za-z0-9_-]{20,}`, `\bAKIA[0-9A-Z]{16}\b`.

- [ ] **Step 1: Write the failing tests:**
  - `test_flags_ocid` (a temp file containing `ocid1.tenancy.oc1..aaaa` → one finding, line 1).
  - `test_local_extension_patterns_apply` (a temp `.sanitize-denylist.local` with `secretcorp` → flags it).
  - `test_skips_binary` (a file containing `\x00` plus `ocid1.` → no findings).
  - `test_scans_svg` (an `.svg` containing `ocid1.` → one finding).
  - `test_clean_file_passes` → `[]`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement (NUL byte in the first 8 KB means binary).
- [ ] **Step 4:** run → PASS; then `python3 scripts/sanitize_scan.py` on the repo → exit 0. Create your local
  `.sanitize-denylist.local` with your private identifiers (gitignored) and rerun → exit 0.
- [ ] **Step 5: Commit** `feat: deny-list scan for public safety`.

### Task 3: Diagram tooling and the root architecture diagram

**Files:**
- Create: `scripts/dot_check.py`, `scripts/dot_drift.py`, `ARCHITECTURE.dot`, `ARCHITECTURE.svg`
- Test: `tests/test_dot_tools.py`

**Interfaces:**
- Produces: `validate(dot_file: Path) -> tuple[bool, str]` (runs `dot -Tcanon -o /dev/null`); `render(dot_file) ->
  Path` (writes the sibling `.svg`); CLI `python3 scripts/dot_check.py [--check]` validates every tracked `*.dot`,
  re-renders, and with `--check` exits 1 if any committed SVG differs (`git diff --exit-code -- '*.svg'`).
- `drift(changed: list[str], dot_owners: list[str], pr_body: str) -> list[str]`: for each changed path, the nearest
  ancestor directory containing `ARCHITECTURE.dot` is its owner; returns the owners whose `.dot` is not in `changed`,
  unless `pr_body` contains `diagram unchanged:`. CLI `python3 scripts/dot_drift.py --base <ref> [--pr-body-file f]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_validate_rejects_syntax_error` (`digraph{a->}` → `False`).
  - `test_validate_accepts_flow` (`docs/flow.dot` → `True`).
  - `test_drift_flags_owner_without_dot_change` (changed `["plugins/pavedline/x.py"]`, owners `["."]` → `["."]`).
  - `test_drift_passes_when_dot_changed`.
  - `test_drift_passes_with_reason` (body `diagram unchanged: typo only` → `[]`).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement; write `ARCHITECTURE.dot`: the factory itself (marketplace → plugin → skills, agents,
  hooks, MCP, templates; repo scripts → CI), using the colour style of `docs/flow.dot`.
- [ ] **Step 4:** run → PASS; `python3 scripts/dot_check.py --check` → exit 0.
- [ ] **Step 5: Commit** `feat: diagram validation, rendering and drift check`.

### Task 4: Hook — secret and `.env` guard

**Files:**
- Create: `plugins/pavedline/scripts/hooks/_common.py`, `plugins/pavedline/scripts/hooks/guard_secrets.py`,
  `plugins/pavedline/hooks/hooks.json`
- Test: `tests/hooks/test_guard_secrets.py`, `tests/hooks/fixtures/` (JSON payloads)

**Interfaces:**
- Produces in `_common.py`: `read_event() -> dict | None` (None on empty or invalid stdin);
  `block(reason: str) -> NoReturn` (stderr + exit 2); `allow() -> NoReturn` (exit 0); `is_env_file(path: str) ->
  bool` (basename `.env` or `.env.*`, except suffixes `.example`, `.sample`, `.template`).
- `guard_secrets.py`: on `Read`/`Edit`/`Write` with an env `file_path` → block; on `Write` content or `Edit`
  `new_string` matching a secret pattern (reuse the key/token patterns of `.sanitize-denylist`, packaged in
  `_common.SECRET_PATTERNS`) → block; on `Bash` whose command reads an env file (`cat|less|head|tail|source|grep …
  .env…`) → block.
- `hooks.json` registers it for `PreToolUse` with matcher `Read|Write|Edit|Bash`, command
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/guard_secrets.py"`.

- [ ] **Step 1:** capture one real payload each for Read, Write and Edit (a temporary hook that dumps stdin), confirm
  the field names in Global Constraints, and save sanitised copies as fixtures.
- [ ] **Step 2: Write the failing tests** (run the script as a subprocess with a fixture on stdin; assert the exit
  code):
  - `test_blocks_read_env` (`.env` → 2), `test_blocks_env_local` (`.env.local` → 2),
    `test_blocks_nested_env` (`config/.env.production` → 2).
  - `test_allows_env_example` (`.env.example` → 0), `test_allows_normal_file` (`README.md` → 0).
  - `test_blocks_bash_cat_env` (`cat .env` → 2).
  - `test_blocks_write_with_private_key` (content containing `-----BEGIN RSA PRIVATE KEY-----` → 2).
  - `test_malformed_stdin_fails_open` (empty stdin → 0, stderr non-empty).
- [ ] **Step 3:** run → FAIL. **Step 4:** implement. **Step 5:** run → PASS.
- [ ] **Step 6: Commit** `feat: secret and .env guard hook`.

### Task 5: Hooks — cluster-context guard and git guard

**Files:**
- Create: `plugins/pavedline/scripts/hooks/guard_cluster.py`, `plugins/pavedline/scripts/hooks/guard_git.py`;
  modify `plugins/pavedline/hooks/hooks.json`
- Test: `tests/hooks/test_guard_cluster.py`, `tests/hooks/test_guard_git.py`

**Interfaces:**
- `guard_cluster.py`: splits the Bash command on `&&`, `||`, `;` and `|`; for each `kubectl`, `helm` or `argocd`
  segment with a **mutating verb** (kubectl: `apply create delete edit patch replace scale rollout label annotate
  drain cordon taint set`; helm: `install upgrade uninstall rollback`; argocd: `app sync`, `app delete`, `app set`,
  `app create`), the target context is the `--context`/`--kube-context` flag if present, else
  `current_context()`. Block unless the context starts with `kind-pavedline-`. `current_context()` returns
  `os.environ["PAVEDLINE_TEST_KUBE_CONTEXT"]` when set (tests only), else the output of
  `kubectl config current-context` (empty on error → treated as non-kind → block mutating commands).
- `guard_git.py`: blocks `--no-verify` on any `git` command, and `git push` with `--force`/`-f`/`--force-with-lease`
  targeting `main` or `master`.

- [ ] **Step 1: Write the failing tests** (`PAVEDLINE_TEST_KUBE_CONTEXT` set per test):
  - cluster: `test_blocks_delete_on_cloud_context` (context `prod`, `kubectl delete ns x` → 2);
    `test_blocks_context_flag_override` (context `kind-pavedline-demo`, `kubectl --context prod apply -f x` → 2);
    `test_blocks_chained_mutation` (`kubectl get pods && kubectl delete ns x`, context `prod` → 2);
    `test_blocks_helm_upgrade` (context `prod` → 2); `test_allows_read_only` (`kubectl get pods`, `helm list`,
    `kubectl logs x` with context `prod` → 0); `test_allows_local_mutation` (context `kind-pavedline-demo`,
    `kubectl apply -f x` → 0).
  - git: `test_blocks_no_verify` (`git commit --no-verify -m x` → 2); `test_blocks_force_push_main`
    (`git push --force origin main` → 2); `test_allows_force_push_branch` (`git push --force-with-lease origin
    feat/x` → 0); `test_allows_normal_push` → 0.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement and register both in `hooks.json` (`PreToolUse`, matcher `Bash`).
  **Step 4:** run → PASS.
- [ ] **Step 5: Commit** `feat: cluster-context and git guard hooks`.

### Task 6: Hooks — STATE.md cap, CLAUDE.md size warning, session start

**Files:**
- Create: `plugins/pavedline/scripts/hooks/guard_state_size.py`, `warn_claude_md.py`, `session_start.py`; modify
  `hooks.json`
- Test: `tests/hooks/test_state_and_session.py`

**Interfaces:**
- `guard_state_size.py` (`PreToolUse`, `Write|Edit`): when `file_path` ends with `STATE.md`, compute the resulting
  line count (Write: `content`; Edit: the current file with `old_string` replaced by `new_string`). If over 60 →
  block with: "STATE.md would be N lines (cap 60). Move closed items to docs/archive/state-YYYY-MM.md first."
- `warn_claude_md.py` (`PostToolUse`, `Write|Edit`): when `CLAUDE.md` exceeds 150 lines → exit 1 with a stderr
  warning (non-blocking).
- `session_start.py` (`SessionStart`): if `STATE.md` exists in `cwd`, print plain text: the contents of
  `PRODUCT.md` (first paragraph), `STATE.md`, and the open items of `WAITING.md`, under the heading "Pavedline
  project state". Otherwise print "No Pavedline project here. Run /pavedline:start to begin." Exit 0.

- [ ] **Step 1: Write the failing tests:** `test_blocks_write_over_60` (61-line content → 2);
  `test_allows_write_at_60` → 0; `test_edit_growth_blocked` (an existing 59-line file plus an Edit adding 3 lines →
  2); `test_ignores_other_files` → 0; `test_claude_md_warning` (151 lines → exit 1 with stderr);
  `test_session_start_prints_state` (temp dir with all three files → stdout contains the STATE text and
  "WAITING"); `test_session_start_without_project` → stdout contains "Run /pavedline:start".
- [ ] **Step 2:** run → FAIL. **Step 3:** implement and register. **Step 4:** run → PASS.
- [ ] **Step 5: Commit** `feat: STATE cap, CLAUDE.md warning and session-start hooks`.

### Task 7: Model policy, the researcher agent, and the skill linter

**Files:**
- Create: `plugins/pavedline/config/models.yaml`, `plugins/pavedline/agents/researcher.md`,
  `scripts/gen_agent_models.py`, `scripts/lint_skills.py`
- Test: `tests/test_models_and_lint.py`

**Interfaces:**
- `models.yaml`: one `role: model` per line (`orchestrator`, `designer`, `researcher`, `architect`,
  `design-verifier`, `builder`, `reviewer`, `adversary`, `deployer`, `growth`); `parse_models(text) -> dict[str,str]`
  rejects any value not in `{opus, sonnet}`.
- `gen_agent_models.py [--check]`: sets each `agents/<role>.md` frontmatter `model:` to the mapped value; `--check`
  exits 1 on drift.
- `researcher.md`: frontmatter `name: researcher`, a `description`, `model: sonnet`, `tools: Read, Grep, Glob,
  WebFetch, WebSearch, mcp__playwright__*`; body: the research rules of §6.2 (a URL per claim; definite / inferred /
  unknown; robots.txt and terms respected; review sites only by export or API; login-gated competitors from public
  material only; never fetch credentials).
- `lint_skills.py <skills_dir>`: per skill, frontmatter `name` equals the directory, `description` non-empty and ≤
  1024 characters, `SKILL.md` ≤ 500 lines, every relative link under `references/` exists. Exit 1 with
  `path: problem` lines.

- [ ] **Step 1: Write the failing tests:** `test_parse_rejects_haiku`; `test_generator_check_detects_drift`
  (a temp agent with `model: opus` mapped to `sonnet` → exit 1); `test_lint_name_mismatch`;
  `test_lint_missing_reference`; `test_lint_passes_valid_skill`.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** run → PASS;
  `python3 scripts/gen_agent_models.py --check` → 0.
- [ ] **Step 5: Commit** `feat: model policy generator, researcher agent, skill linter`.

### Task 8: Templates and the copy engine

**Files:**
- Create: `plugins/pavedline/templates/` with `CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, `GLOSSARY.md`,
  `RUN.md`, `SERVICES.md`, `LINKS.md`, `decisions/0000-template.md`, `handoff/README.md`, `docs/rules-index.md`,
  `docs/business/README.md`, `docs/spec/README.md`, `docs/archive/README.md`, `ARCHITECTURE.dot`
- Create: `plugins/pavedline/scripts/start_project.py`
- Test: `tests/test_start_project.py`

**Interfaces:**
- Placeholders: `{{PROJECT_NAME}}`, `{{DATE}}` (from `date`), `{{MODE}}` (`solo` or `team`).
- `start_project.py --target <dir> --name <name> --mode solo|team [--dry-run]`: copies every template that does not
  yet exist; if **any** destination file already exists, writes nothing, prints `conflict: <path>` per file, exits 1.
  Prints `created: <path>` per file on success.
- Template rules: `CLAUDE.md` ≤ 150 lines and contains the "who asks what" rule of §6.5 verbatim in substance,
  the reading order of §7, and the pointer to `docs/rules-index.md`; `STATE.md` has exactly the fields of §7 and is
  ≤ 60 lines; `WAITING.md` has the `Fn · what · where/how · what it unblocks` format.

- [ ] **Step 1: Write the failing tests:** `test_copies_into_empty_dir` (every template exists, placeholders
  replaced, no `{{` left); `test_refuses_when_claude_md_exists` (pre-existing `CLAUDE.md` → exit 1, no other file
  written, stdout lists the conflict); `test_template_sizes` (`CLAUDE.md` ≤ 150, `STATE.md` ≤ 60);
  `test_state_has_required_fields` (`STEP`, `WAVE`, `SLICES IN FLIGHT`, `LAST`, `NEXT`, `LEFT BEHIND`, `STALE`,
  `GROW DUE`, `OWNER`, `MODE`).
- [ ] **Step 2:** run → FAIL. **Step 3:** write the templates and the script. **Step 4:** run → PASS.
- [ ] **Step 5: Commit** `feat: product-repo templates and start copy engine`.

### Task 9: `doctor`

**Files:**
- Create: `plugins/pavedline/scripts/doctor.py`, `plugins/pavedline/skills/doctor/SKILL.md`
- Test: `tests/test_doctor.py`

**Interfaces:**
- `check_tools(which=shutil.which) -> list[Check]` for required `git, gh, python3, node, dot, kubectl, helm, kind`
  and a container runtime (`docker` answering `docker info`); optional `colima, uv, terraform`.
- `check_plugins(listing_json: str) -> list[Check]` against the three v0.1 dependencies and `pavedline` itself,
  reading `claude plugin list --json` ids.
- `Check = NamedTuple(name, ok: bool, required: bool, fix: str)`; `fix` is the exact install command (e.g.
  `/plugin marketplace add anthropics/knowledge-work-plugins` then `/plugin install
  product-management@knowledge-work-plugins`; `brew install kind`).
- CLI prints a table and exits 1 if any required check fails. `SKILL.md`: when to run it (start of step 0, or on
  any "command not found"), and to relay each `fix` exactly.

- [ ] **Step 1: Write the failing tests:** `test_missing_kind_is_required_failure` (a fake `which` returning None for
  `kind` → a failing required check whose fix mentions kind); `test_plugins_detected` (a JSON listing with all four
  ids → all ok); `test_missing_dependency_has_install_fix` (`product-management@knowledge-work-plugins` absent → fix
  contains `/plugin install product-management@knowledge-work-plugins`).
- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** run → PASS; run `doctor.py` on this machine and
  record the output in the task report.
- [ ] **Step 5: Commit** `feat: doctor`.

### Task 10: Step-0 skills — start, architecture-intake, compliance, state

**Files:**
- Create: `plugins/pavedline/skills/{start,architecture-intake,compliance,state}/SKILL.md` (+ `references/` as
  needed)
- Test: `tests/skills/test_contracts.py` (per-skill required content), plus `lint_skills.py` in the test run

**Interfaces:**
- `start` (user-invoked `/pavedline:start`; `disable-model-invocation: true`; `allowed-tools` includes
  `Bash(python3 *)`): runs `doctor`; prints the privacy line; asks §6.1 in order, one question at a time; calls
  `start_project.py` via `${CLAUDE_PLUGIN_ROOT}`; writes an ADR per answer; sets `STATE.md STEP: 1`; ends with "go?".
- `architecture-intake`: questions 2, 4, 5, 6, 7 of §6.1 with their options and defaults; records ADRs.
- `compliance`: the exact wording in Global Constraints; the three follow-ups; the "no" path (ADR "compliance not in
  scope" with the one-line consequence, and a `LAUNCH` re-ask note).
- `state`: how to read and update `STATE.md`/`WAITING.md`/hand-offs (§7), timestamps from `date`, commit after each
  state change, check the remote before redoing work, the opening and closing blocks.

- [ ] **Step 1: Write the failing tests** `test_start_asks_product_first` (in `start/SKILL.md`, "What are you
  building" appears before "multi-tenant"); `test_compliance_exact_wording`; `test_compliance_no_path_recorded`
  ("compliance not in scope" present); `test_privacy_line_present` (exact line in `start`);
  `test_cloud_not_asked_at_step0` (`start` and `architecture-intake` contain no cloud-provider question and do
  contain "chosen at step 12"); and the linter passes on `plugins/pavedline/skills`.
- [ ] **Step 2:** run → FAIL. **Step 3:** write the skills. **Step 4:** run → PASS.
- [ ] **Step 5:** run `/pavedline:start` in an empty temp repo with the plugin loaded via `claude --plugin-dir` and
  confirm the files are created and nothing is overwritten on a second run; record the transcript summary.
- [ ] **Step 6: Commit** `feat: step 0 skills`.

### Task 11: Step-1 skills — competitor-teardown, pricing-model, market-size

**Files:**
- Create: `plugins/pavedline/skills/{competitor-teardown,pricing-model,market-size}/SKILL.md` (+ `references/`)
- Modify: `tests/skills/test_contracts.py`

**Interfaces:**
- `competitor-teardown`: input = the founder's sites; dispatches the `researcher` agent; output files of §6.2
  (`competitors/<name>.md` with features, pricing, public complaints, sources), `landscape.dot`, and
  `SEO-STRATEGY.md` (sitemaps, topics, queries and intent, clusters, pillar pages, a target query per page); the
  scraping rules of §6.2; uses `competitive-brief` / `synthesize-research` when installed.
- `pricing-model`: tiers, what each tier includes, how the product makes money, pricing references from competitors,
  open questions; → `BRIEF.md` pricing section. No per-tenant cost model.
- `market-size`: top-down and bottom-up estimates, each number sourced or marked as an assumption; → `BRIEF.md`.

- [ ] **Step 1: Write the failing tests:** `test_teardown_requires_sources` ("URL" and "definite, inferred or
  unknown" present); `test_review_sites_rule` ("manual export or official APIs" present);
  `test_seo_strategy_output` (`SEO-STRATEGY.md` and "target query" present); `test_market_size_marks_assumptions`.
- [ ] **Step 2:** run → FAIL. **Step 3:** write the skills. **Step 4:** run → PASS.
- [ ] **Step 5: Commit** `feat: step 1 market and SEO research skills`.

### Task 12: Steps 2–3 and cross-cutting skills — spec, diagram, project-registry

**Files:**
- Create: `plugins/pavedline/skills/{spec,diagram,project-registry}/SKILL.md`
- Modify: `tests/skills/test_contracts.py`

**Interfaces:**
- Step 2 uses Matt Pocock's `grilling` / `grill-with-docs` (a dependency); `start`'s closing hand-off names it.
- `spec`: `SPEC.md` sections of §6 step 3 (users, jobs, features **per surface** — website, blog, web app, mobile app
  — non-goals, acceptance tests, non-functional needs, site map and URL plan); updates `BRIEF.md` if pricing changes;
  team mode: `to-tickets`.
- `diagram`: when a `.dot` is required (§10), the shared style, validate and render commands.
- `project-registry`: keep `RUN.md`, `SERVICES.md` (what, dashboard, **where** each key lives, owner, rotation; never
  the value) and `LINKS.md` current.

- [ ] **Step 1: Write the failing tests:** `test_spec_has_four_surfaces`; `test_spec_has_acceptance_tests`;
  `test_registry_never_values` ("never the value" present); `test_diagram_uses_canon` (`-Tcanon` present).
- [ ] **Step 2:** run → FAIL. **Step 3:** write. **Step 4:** run → PASS.
- [ ] **Step 5: Commit** `feat: spec, diagram and project-registry skills`.

### Task 13: Local Kubernetes cluster

**Files:**
- Create: `plugins/pavedline/scripts/local-cluster/{versions.env,kind-config.yaml.tpl,up.sh,verify.sh,down.sh}`,
  `plugins/pavedline/scripts/local-cluster/manifests/cnpg-smoke-cluster.yaml`,
  `plugins/pavedline/skills/local-cluster/SKILL.md`
- Test: `tests/test_local_cluster_static.py` (static checks) + the CI job of Task 14 (real run)

**Interfaces:**
- `versions.env`: `KIND_NODE_IMAGE` (the pinned digest above), `ARGOCD_CHART_VERSION=10.15.0`,
  `CNPG_CHART_VERSION=0.29.1`, `REGISTRY_PORT=5001`, with a `# verified 2026-11-07` comment.
- `up.sh <project>`: refuses unless a container runtime answers; creates a local registry container
  (`kind-registry`, port 5001) per the kind local-registry recipe; creates cluster `pavedline-<project>` from the
  config (extraPortMappings 8080→80 and 8443→443; containerd registry mirror); `helm upgrade --install` Argo CD and
  the CNPG operator at the pinned versions into `argocd` and `cnpg-system`, with `--wait`.
- `verify.sh <project>`: the context is `kind-pavedline-<project>`; `argocd-server` and the CNPG controller
  deployments are Available; applies `cnpg-smoke-cluster.yaml` (1 instance, 1Gi) and waits for
  `Cluster/smoke` to report `Cluster in healthy state`; then deletes it. Exit 0 only if all pass.
- `down.sh <project>`: deletes the cluster and, with `--all`, the registry.
- Every script uses `set -euo pipefail` and passes `--context kind-pavedline-<project>` explicitly.

- [ ] **Step 1: Write the failing static tests:** `test_versions_pinned` (no `latest`, digest present);
  `test_scripts_pin_context` (every `kubectl`/`helm` line in the scripts has `--context` or `--kube-context`);
  `test_strict_mode` (each `.sh` starts with `set -euo pipefail` after the shebang).
- [ ] **Step 2:** run → FAIL. **Step 3:** implement scripts and the skill (Colima 4 CPU / 10 GB guidance; teardown;
  "what local cannot prove" list from §11.6).
- [ ] **Step 4:** run the static tests → PASS; on this Mac: `colima start --cpu 4 --memory 10`, then `up.sh demo`,
  `verify.sh demo` → exit 0, `down.sh demo --all`. Record durations and memory used.
- [ ] **Step 5: Commit** `feat: local Kubernetes cluster (kind + Argo CD + CNPG)`.

### Task 14: The factory's own CI and Renovate

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/renovate.yml`, `renovate.json`,
  `.github/pull_request_template.md`, `scripts/pr_checks.py`
- Test: `tests/test_pr_checks.py`

**Interfaces:**
- `pr_checks.py --body-file f`: exits 1 unless the body has a line matching
  `^Gates: TDD ✓ · review ✓ \(\d+ found, \d+ fixed\) · security ✓ · adversarial (✓|n/a) · verification ✓$`.
- `ci.yml` jobs (all actions pinned by commit SHA, looked up when written): `unit` (`python3 -m unittest discover -v`),
  `lint` (`lint_skills.py`, `gen_agent_models.py --check`, and a `STATE.md` ≤ 60-line check on the template — the
  CI backstop of design §9.3), `sanitize`, `diagrams` (apt `graphviz`; `dot_check.py
  --check`; `dot_drift.py` on PRs), `plugin-validate` (`npm i -g @anthropic-ai/claude-code@2.1.319`; validate root
  and plugin with `--strict`), `gitleaks` (the v8.30.1 release binary, checksum verified), `local-cluster`
  (`ubuntu-24.04-arm`; installs kind v0.33.0 and helm; `up.sh ci` → `verify.sh ci` → `down.sh ci --all`),
  `pr-body` (on `pull_request`: `pr_checks.py`).
- `renovate.yml`: weekly cron, `renovatebot/github-action` pinned by SHA, token from secret `RENOVATE_TOKEN`
  (documented in `SECURITY.md` and `CONTRIBUTING.md`).
- `renovate.json`: weekly schedule; minor and patch grouped; dependency dashboard; `automerge` only for patch updates
  of development tooling; never for `versions.env` (add a regex manager for `versions.env` and a rule disabling
  automerge for it).

- [ ] **Step 1: Write the failing tests:** `test_accepts_valid_gates_line`; `test_rejects_cross_value` (`✗`);
  `test_rejects_missing_line`.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** run → PASS; lint the workflows with `actionlint`
  if it is installed (it is a new local tool, so ask before installing it); otherwise state in the task report that
  the workflows were reviewed by eye and will be proven by their first run.
- [ ] **Step 5: Commit** `ci: factory CI, PR gates check and Renovate`.
- [ ] **Step 6:** the founder adds the `RENOVATE_TOKEN` secret later (add to the founder's waiting list); the CI jobs
  run for the first time only when the founder allows the first push.

### Task 15: README, credits, docs for steps 0–3

**Files:**
- Modify: `README.md` (install section: only the v0.1 dependency marketplace,
  `anthropics/knowledge-work-plugins`, plus `Marwan-G/pavedline`; status; roadmap; requirements)
- Create: `CREDITS.md`, `THIRD_PARTY_NOTICES.md` (header and "no adapted code in v0.1"), `docs/steps/00-start.md`,
  `01-market.md`, `02-grill.md`, `03-spec.md`, `docs/environments.md`, `docs/faq.md`
- Test: `tests/test_docs.py`

**Interfaces:**
- `CREDITS.md`: every row of design §12.2 and §13 credits, with author, link, licence and "installed / adapted /
  ideas only".

- [ ] **Step 1: Write the failing tests:** `test_readme_links_resolve` (every relative link in README and docs
  exists); `test_credits_cover_dependencies` (each `plugin.json` dependency and the MCP package appears in
  `CREDITS.md`); `test_readme_status_line` ("Status: in development").
- [ ] **Step 2:** run → FAIL. **Step 3:** write the docs. **Step 4:** run → PASS; full suite
  `python3 -m unittest discover -v` → all PASS; `sanitize_scan.py` → 0; `dot_check.py --check` → 0.
- [ ] **Step 5: Commit** `docs: README, credits and step 0–3 guides`.

### Task 16: Clean-profile install test and the v0.1 release candidate

**Files:**
- Create: `scripts/install_test.sh`; modify `CHANGELOG.md`

- [ ] **Step 1:** `install_test.sh` runs Claude Code against a throwaway config directory (verify the supported
  mechanism first: `CLAUDE_CONFIG_DIR`, else a temporary `HOME`), adds the local repo as a marketplace by path, adds
  the dependency marketplace(s), installs `pavedline@pavedline`, and checks `claude plugin list --json` for
  `pavedline@pavedline` and the three dependencies. It never touches the real profile.
- [ ] **Step 2:** run it; record exactly which dependencies installed automatically and which needed their
  marketplace added. Update README's install section and design §12.2 to match the observed behaviour.
- [ ] **Step 3:** run the whole verification: unit suite, linter, generator check, deny-list scan, diagram check,
  `claude plugin validate --strict` (root and plugin), local cluster up/verify/down. All green.
- [ ] **Step 4:** `CHANGELOG.md` → `## 0.1.0 — <date>` with what works. Commit `release: v0.1.0 candidate`.
- [ ] **Step 5: STOP.** Report to the founder: the evidence of steps 2–3, and the waiting-on-you items (approve the
  push; add `RENOVATE_TOKEN`; approve making the repo public; then `claude plugin tag --push` for
  `pavedline--v0.1.0`). Nothing is pushed, tagged or made public without the founder's word.
