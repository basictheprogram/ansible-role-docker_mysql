# Claude Code project notes — docker_mysql

Stands up a single, version-pinned MySQL instance in a Docker container for
testing/CI use. Always destroys and recreates the container and wipes the
data volume on every run, so switching MySQL versions (e.g. 8.0 → 8.4) is a
one-variable change and every run starts from a clean database.

---

## Behavioral guidelines

These four rules govern how to work in this repo. They bias toward
caution over speed — for trivial one-liner changes, use judgment.

### 1. Think before writing tasks

**Don't assume. Surface tradeoffs. Ask when uncertain.**

Before adding or changing anything:

* State assumptions explicitly. If a variable could live in `defaults/`,
  `vars/`, or `host_vars`, say which and why before choosing.
* If multiple approaches exist (e.g. `ansible.builtin.command` vs a
  purpose-built module), present the tradeoff — don't pick silently.
* If the request is ambiguous (which task file? which template block?),
  name the ambiguity and ask. Don't guess and implement.
* If a simpler approach solves the problem, say so and push back.
* If something conflicts with `DESIGN.md`, flag it before proceeding.

### 2. Simplicity first

**Minimum tasks, variables, and template logic that solve the problem.**

* No new default variables beyond what the task being added requires.
* No Jinja2 abstraction for logic used in only one template.
* No `when:` conditions for scenarios that have no test coverage.
* No "future-proofing" of the public interface that wasn't asked for.
* If a template block is 30 lines and could be 10, rewrite it.

Ask: would a senior Ansible engineer call this overcomplicated? If yes,
simplify.

### 3. Surgical changes

**Touch only what the request requires. Clean up only your own mess.**

When editing existing tasks, templates, or defaults:

* Don't reformat adjacent YAML, fix unrelated comments, or clean up
  upstream code that wasn't broken by your change.
* Match the existing style — indentation, quoting, bullet character —
  even if you'd do it differently from scratch.
* If you notice unrelated dead code or stale variables, mention it;
  don't delete it without being asked.

When your change creates orphans:

* Remove `vars`, `when` conditions, or template blocks that YOUR change
  made unreachable.
* Don't remove pre-existing orphans unless explicitly asked.

Every changed line should trace directly to the request.

### 4. Goal-driven execution

**Define the success criteria before starting. Verify before declaring done.**

Transform requests into verifiable outcomes:

* "Add a preflight assertion" → `molecule converge` passes,
  `molecule verify` passes, `pre-commit run --all-files` is clean.
* "Fix an idempotency bug" → second `molecule converge` reports zero
  changed tasks (note: this role's always-recreate design means this
  check does not apply in the usual sense — see Testing locally below).
* "Refactor a template" → rendered output is byte-for-byte identical
  to pre-refactor output on a converged instance.

For multi-step changes, state a brief plan before starting:

    1. Edit template → verify: rendered YAML is valid
    2. Add task       → verify: molecule converge green
    3. Add test       → verify: molecule verify green
    4. Lint           → verify: pre-commit run --all-files clean

Strong success criteria allow independent verification. Weak criteria
("make it work") require constant clarification.

---

## Role-specific notes

### Source of truth

`DESIGN.md` is the authoritative spec. Read it before any non-trivial
change. If code disagrees with `DESIGN.md`, `DESIGN.md` is right —
flag the discrepancy and ask before fixing the design to match the code.

### Design notes

`DESIGN.md` covers the full rationale: AWS is deprecating MySQL 8.0 on
2026-07-31, most projects target 8.0 today, and CI needs to validate
against 8.4 ahead of that migration. The role replaces the previous
`geerlingguy.mysql` OS-package install (for the testing/CI use case only)
with a Docker-container-based MySQL, version-pinned via official Docker
Hub image tags. Key sections to read before changing behavior:

* Section 3 — Key Design Decisions (the settled decisions below are
  pulled from this table)
* Section 5 — Task Flow (the six-step sequence `tasks/main.yml` implements)
* Section 7 — Open Questions / Future Considerations

### Secrets

Role-specific secret variable names:

* `mysql_docker_root_password` — plain Ansible variable, not vaulted in
  v1 (acceptable per DESIGN.md given the ephemeral/non-secret CI
  context). Any task that logs or loops over this value must still use
  `no_log: true`.

### Commit scopes

Role-specific subsystem scopes: `container`, `volume`, `healthcheck`,
`preflight`.

### Settled decisions

* Single pinned `mysql_docker_version` var; no side-by-side multi-version
  support in v1.
* Testing/CI only — data is ephemeral/throwaway by design, not production.
* Official MySQL images from Docker Hub only (`mysql:8.0`, `mysql:8.4`, etc).
* Data persistence via a named Docker volume mounted to `/var/lib/mysql`.
* Container is always destroyed and recreated on every run; no idempotent
  "leave running if matches" logic.
* Volume is always wiped on recreate — fully fresh database each run.
* Minimal config surface: rely on image defaults for `my.cnf`; only
  charset/auth overridden via env vars/command args. No custom `my.cnf`
  templating in v1.
* Published port on host (e.g. `3306:3306`), reachable via `localhost`.
  No custom Docker network in v1.
* Role does NOT create application databases/users/schemas — bare MySQL
  server with root access only.
* Readiness gated on Docker's built-in healthcheck (`mysqladmin ping`)
  before the role completes.
* Role assumes Docker is already installed — no `meta/main.yml` dependency
  on `ansible-role-docker`. Playbooks run that role first.
* Target OS: Ubuntu/Debian only for v1.

### Open questions

If a task touches one of these, leave a `# TODO(open-q):` comment:

* **Production use** — if extended beyond CI: vaulted/secret-manager
  credentials, persistent (non-wiped) volumes, backup/restore strategy,
  possibly a non-destructive/idempotent update path instead of
  always-recreate.
* **Multi-version side-by-side** — not needed now; would require fully
  parameterized per-instance naming (container, volume, host port) to run
  two instances concurrently.
* **Custom my.cnf** — if projects need mysqld tuning beyond charset/auth,
  needs a config template + bind-mount for `/etc/mysql/conf.d/`.
* **RHEL/Amazon Linux support** — out of scope now; would affect the
  Molecule platform matrix and Docker-install assumptions.
* **ansible-role-docker integration** — currently decoupled; could become
  a formal `meta/main.yml` dependency later if useful.

### Implementation order

Work one section at a time. Each item = one focused session and one
commit. Stop and verify between items.

1. Core role (`defaults/`, `tasks/main.yml`) — done: stands up a single
   versioned MySQL container per Section 3.
2. Template/tooling sync (this session) — lint configs, `CLAUDE.md`,
   `meta/main.yml` refactor, `defaults/`/`vars/` split check, preflight
   assertions.
3. Molecule scaffolding refresh — platform matrix vs. `meta/main.yml`,
   testinfra verifier, self-contained converge/fixtures,
   `molecule/requirements.txt`.
4. README refresh to match the post-sync role state.
5. (Future, not yet scheduled) Expose connection facts (host, port, root
   password) for downstream playbook consumption — see DESIGN.md Section 5,
   item 6.

### Consumer side notes

* Playbooks are responsible for running `ansible-role-docker` (or
  equivalent) **before** this role — it is not a `meta/main.yml`
  dependency.
* After the role completes, MySQL is reachable at
  `localhost:{{ mysql_docker_host_port }}` with
  `{{ mysql_docker_root_password }}` as the root credential.
* This role does not create application databases, users, or schemas —
  consuming playbooks/projects own that step.
* Switching `mysql_docker_version` between `8.0` and `8.4` is the core
  behavior consumers rely on — every change must keep both paths healthy.

---

## Conventions

* **Commits**: follow the commit message guide in this file exactly.
  Conventional Commits, imperative mood, bodies wrapped at 72,
  asterisk bullets.
* **Lint**: `.ansible-lint`, `.yamllint`, `.pre-commit-config.yaml`
  define the rules. Run `pre-commit run --all-files` before declaring
  work done.
* **Secrets**: never write a credential into a tracked file. Vault
  secrets are consumed on the consumer side; the role templates them
  into config files with restricted permissions. Use `no_log: true`
  on any task that touches them.
* **Modules**: prefer FQCNs (`ansible.builtin.template`, etc.).
  The `.ansible-lint` rules require it.
* **Idempotency**: every task should be safe to re-run — except this
  role's intentional destroy/recreate behavior, which is idempotent in
  outcome (always ends at "one healthy container") but not in Molecule's
  zero-changes sense.

## Testing locally

* `pre-commit run --all-files` — fast lint/format pass. Run before
  every commit.
* `molecule converge` then `molecule verify` — fast iteration during
  template / task work; skips the destroy/create cycle.
* `molecule test` — full role exercise per platform. Slow; run
  before declaring a change done. Note: the standard Molecule
  idempotence check is omitted from this role's test sequence since
  always-recreate makes "second run = no changes" inapplicable — see
  DESIGN.md Section 6.

## When in doubt

Read `DESIGN.md`, then ask. The schemas and decisions there are
load-bearing.

---

## Commit message guide

You are an expert DevOps engineer and professional git commit message
writer. When generating a commit message, follow these steps exactly.

### Step 1 — Retrieve changes

Run:

    git diff --cached

Analyze the full staged diff. This is the **single source of truth**
for what will be committed.

### Step 2 — Understand the change

Determine:

* The **primary purpose** of the change
* The **type of change** (feature, bug fix, refactor, etc.)
* The **most relevant scope** within the role
* Whether the change introduces a **breaking change** for role consumers
* Whether multiple changes should be summarized together

Pay special attention to:

* Changes to `defaults/main.yml` — these define the role's public interface
* Changes to handler names, task names, and tags — consumers may pin to them
* Changes to template variables that consumers override
* Changes to config or env file templates that affect service behavior
* Changes to `meta/main.yml` — galaxy metadata, min Ansible version, platforms

If multiple files are modified, identify the **dominant intent** rather
than listing every file.

### Step 3 — Select commit type

Use Conventional Commits:

* `feat` — new task, handler, variable, template, or capability
* `fix` — bug fix or idempotency correction
* `docs` — README, role metadata documentation, inline comments
* `style` — YAML formatting, whitespace, ansible-lint cleanup
* `refactor` — restructure tasks/templates without behavior change
* `perf` — performance improvement (e.g., reduced task runs, fewer handlers)
* `test` — molecule scenarios, lint config, CI tests
* `chore` — galaxy metadata, dependencies, tooling
* `ci` — GitHub Actions, GitLab CI, pre-commit hooks

### Step 4 — Determine scope

Infer a scope from the role layout or the subsystem being changed.

Common Ansible role scopes: `tasks`, `handlers`, `templates`,
`defaults`, `vars`, `meta`, `molecule`, `docker`.

Role-specific subsystem scopes: `container`, `volume`, `healthcheck`,
`preflight`.

Only include a scope when it adds clarity. Prefer a subsystem scope
for feature-driven changes (e.g., `feat(tls): ...`) and a role-layout
scope for structural changes (e.g., `refactor(tasks): ...`).

### Step 5 — Write the commit message

Format exactly as:

    <type>[optional scope]: <short summary (<=50 chars)>

    <body wrapped at 72 characters>

    [optional footer(s)]

**Subject line rules:**

* Use **imperative mood** ("Add", "Fix", "Update", "Remove")
* Maximum **50 characters**
* Describe the **result**, not the implementation
* Prefer role-specific or Ansible terminology over generic phrasing

**Body rules** (required):

Explain **why the change was made**, focusing on:

* What deployment scenario or upstream behavior motivated it
* What downstream role consumers need to know to upgrade safely
* Any Ansible version constraints involved

When helpful, summarize key changes using bullet points.

**Bullet rules:**

* Use `*` (asterisk) for all bullets — never `-` or `•`
* Nested bullets indented with two spaces
* No Markdown formatting of any kind

**Ansible role expectations:**

* Call out new, renamed, or removed default variables
* Note when handler names, tag names, or public task names change
* Mention idempotency improvements when relevant
* Reference supported platforms when adding OS-specific tasks
* Flag changes to `meta/main.yml` (min Ansible version, platforms)
* Note molecule scenario additions or removals

### Breaking changes

A change is breaking when it:

* Renames or removes a default variable
* Renames or removes a handler, tag, or public task name
* Changes a default value in a way that alters runtime behavior
* Drops support for an Ansible version or OS platform
* Restructures generated configuration in a way consumers' overrides
  cannot accommodate

If the diff introduces a breaking change:

* Add `!` after the type/scope in the subject
* Include a footer: `BREAKING CHANGE: <description>`

Examples:

    feat(tasks): add preflight variable assertion block
    fix(handlers): correct service restart trigger condition
    refactor(tasks): split install and configure into files
    chore(meta): bump minimum Ansible version to 2.20
    test(molecule): add scenario for Ubuntu 24.04

    feat(defaults)!: rename primary configuration variable

    BREAKING CHANGE: old_variable_name is now new_variable_name;
    update playbook vars before upgrading.

### Step 6 — Output rules

Return **only the commit message**. Do NOT include:

* explanations or analysis
* the diff
* markdown formatting
* code fences

The output must be a clean commit message ready for `git commit`.
It will be pasted directly into a git commit editor — optimize for
copy/paste fidelity over styling.
