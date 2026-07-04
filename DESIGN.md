# Design Document: ansible-role-docker_mysql

**Status:** Draft for review
**Author:** (compiled via Claude session, for handoff to Cowork)
**Date:** 2026-07-04

## 1. Problem Statement

Projects currently provision MySQL via a standalone VM configured with the
`geerlingguy.mysql` Ansible role, which installs MySQL from OS package
repositories. This ties the available MySQL version to whatever the host
OS/distro repos provide, which is no longer sufficient:

- AWS is deprecating MySQL 8.0 on **July 31, 2026**.
- Most current projects target MySQL 8.0.
- Testing/CI needs to validate against **MySQL 8.4** now, ahead of migration.
- OS package repos don't reliably offer a clean way to pin/switch between
  specific MySQL versions on demand.

**Decision:** Replace the OS-package-based MySQL install (for the
testing/CI use case) with MySQL running in a Docker container, version-pinned
via the official MySQL image tags. This decouples MySQL version from host OS,
and makes version switching (8.0 → 8.4) a one-variable change.

## 2. Scope

**In scope:**

- A new, standalone Ansible role — `ansible-role-docker_mysql` — that stands
  up a single MySQL instance in a Docker container on a host.
- Ephemeral/testing/CI use case only (not production, for now).
- Molecule test scaffolding for the role itself.

**Out of scope (for this iteration):**

- Production use / persistent long-lived data (may be revisited later).
- Running multiple MySQL versions simultaneously on one host.
- The role provisioning application-level databases, users, or schemas.
- Backup/restore tooling.
- Non-Debian/Ubuntu host support.
- Installing Docker itself (handled separately by `ansible-role-docker`).

## 3. Key Design Decisions

| Topic | Decision |
|---|---|
| Version selection | Single pinned var, e.g. `mysql_version: "8.4"`. No side-by-side multi-version support in v1. Switching versions is a re-run with a different var value. |
| Primary use case | Testing/CI only. Data is ephemeral/throwaway by design. |
| Image source | Official MySQL images from Docker Hub (`mysql:8.0`, `mysql:8.4`, etc). |
| Data persistence | Named Docker volume, mounted to `/var/lib/mysql` inside the container. |
| Container lifecycle | Always destroy and recreate the container on every role run (matches ephemeral CI use case; no idempotent "leave running if matches" logic needed). |
| Volume lifecycle | Volume is wiped on every recreate — fully fresh database each run. No data survives between runs. |
| Config management | Minimal — rely on image defaults for `my.cnf`; only override charset/auth-related defaults via environment variables/command args. No custom `my.cnf` templating in v1. |
| Networking | Published port on host (e.g. `3306:3306`), reachable via `localhost`. No custom Docker network needed for v1. |
| DB/user provisioning | Role does NOT create application databases or users. It stands up bare MySQL server with root access only. Apps/projects are responsible for their own schema creation. |
| Credential handling | Plain Ansible variable for root password (acceptable given ephemeral/non-secret CI context). Not vaulted in v1. |
| Readiness check | Wait for container to report "healthy" via Docker's built-in healthcheck (the official MySQL image supports `HEALTHCHECK` via `mysqladmin ping`) before the role completes. |
| Docker dependency | Role assumes Docker is already installed/running on the host. Uses `community.docker` collection modules directly — no `meta/main.yml` dependency on `ansible-role-docker`. Playbooks are responsible for running `ansible-role-docker` (or equivalent) beforehand. |
| Restart policy | `unless-stopped` (or `on-failure`) for container resilience during a test run, even though the container itself is destroyed/recreated per role run. |
| Testing | Molecule scaffolding included, using the Docker driver, targeting Ubuntu/Debian. |
| Target OS | Ubuntu/Debian only for v1. |
| Role/repo name | `ansible-role-docker_mysql`. |

## 4. Variables (draft `defaults/main.yml`)

```yaml
# MySQL version — maps directly to Docker Hub tag
mysql_docker_version: "8.4"

# Image repository (allows override for mirrors/private registries later)
mysql_docker_image: "mysql"

# Container naming
mysql_docker_container_name: "mysql-{{ mysql_docker_version }}"

# Networking
mysql_docker_host_port: 3306
mysql_docker_container_port: 3306

# Auth / root credentials (plain var — acceptable for ephemeral CI context)
mysql_docker_root_password: "root"

# Charset/auth defaults (minimal config surface)
mysql_docker_character_set: "utf8mb4"
mysql_docker_collation: "utf8mb4_unicode_ci"
mysql_docker_default_authentication_plugin: "caching_sha2_password"  # or mysql_native_password if needed for legacy app compat

# Volume
mysql_docker_volume_name: "{{ mysql_docker_container_name }}-data"

# Lifecycle
mysql_docker_restart_policy: "unless-stopped"
mysql_docker_recreate: true       # always destroy/recreate container
mysql_docker_wipe_volume: true    # always wipe volume on recreate

# Readiness
mysql_docker_healthcheck_retries: 10
mysql_docker_healthcheck_interval: "5s"
mysql_docker_startup_timeout: 60   # seconds to wait for healthy before failing
```

*Note: variable names are a starting proposal — adjust to match existing
naming conventions used across your other roles (e.g. if you prefix
differently, such as `docker_mysql_*` vs `mysql_docker_*`).*

## 5. Task Flow (draft)

1. **Pre-flight checks**
   - Verify Docker is available on the host (fail fast with a clear message
     if not — since this role does not install Docker itself).
2. **Teardown existing container/volume** (since recreate is always-on)
   - Stop and remove existing container matching `mysql_docker_container_name`, if present.
   - Remove existing named volume `mysql_docker_volume_name`, if present (since wipe is default).
3. **Create volume**
   - `community.docker.docker_volume` — create fresh named volume.
4. **Run container**
   - `community.docker.docker_container`:
     - image: `"{{ mysql_docker_image }}:{{ mysql_docker_version }}"`
     - name, published port, volume mount
     - env vars: `MYSQL_ROOT_PASSWORD`, character set/collation flags via `command:` args (e.g. `--character-set-server`, `--collation-server`, `--default-authentication-plugin`)
     - restart_policy
5. **Wait for healthy**
   - Poll container health status (Docker healthcheck) up to `mysql_docker_startup_timeout`.
   - Fail with clear error if not healthy in time.
6. **(Optional/future) Expose facts**
   - Register connection details (host, port, root password) as Ansible facts for downstream playbook use.

## 6. Molecule Testing Plan

- **Driver:** Docker (molecule-docker)
- **Platform matrix:** Ubuntu (e.g. 22.04, 24.04) — Debian/Ubuntu family only per scope.
- **Scenarios to cover:**
  - Default scenario: role runs cleanly, container reaches healthy state.
  - Version variable override test (e.g. run once with `8.0`, once with `8.4`) — verifying the role is version-agnostic, not that both run simultaneously.
  - Idempotency note: since the role *intentionally* destroys/recreates every run, standard Molecule idempotency checks (second run = no changes) will need to be adapted or explicitly skipped/documented as expected behavior, since "no changes" doesn't apply to an always-recreate role.
  - Verify: container running, correct image tag in use, port reachable, `mysqladmin ping` succeeds, root login works with configured password.
- **Verifier:** likely `ansible` verifier running assertions (docker_container_info, wait_for port, mysql connectivity check).

## 7. Open Questions / Future Considerations

These weren't needed for v1 scope but are worth revisiting later:

- **Production use:** if this role is later extended to production, revisit:
  vaulted/secret-manager-based credentials, persistent (non-wiped) volumes,
  backup/restore strategy, and possibly a non-destructive/idempotent update
  path instead of always-recreate.
- **Multi-version side-by-side:** not needed now, but if cross-version
  compatibility testing in a single CI run becomes valuable, the role would
  need per-instance naming (container name, volume name, host port) fully
  parameterized to run two instances concurrently — the variable structure
  above is already mostly compatible with that if revisited.
- **Custom my.cnf:** if projects need mysqld tuning beyond charset/auth,
  will need a config template + volume/bind-mount for `/etc/mysql/conf.d/`.
- **RHEL/Amazon Linux support:** out of scope now; would mainly affect
  Molecule platform matrix and any Docker-install assumptions.
- **ansible-role-docker integration:** currently decoupled (this role
  assumes Docker exists). If it proves useful, could add it as a formal
  `meta/main.yml` dependency instead of leaving it to playbook ordering.

## 8. Handoff Notes for Cowork

- This document reflects decisions gathered interactively; variable names
  and exact task structure are a starting draft, not final API — feel free
  to refine naming to match conventions in the author's other roles.
- Priority order for implementation: (1) core role that stands up a single
  versioned MySQL container per the decisions in Section 3, (2) Molecule
  scaffolding per Section 6, (3) README with usage examples for both the
  8.0 and 8.4 versions.
- The single most important behavior to get right: the role must cleanly
  support switching `mysql_docker_version` between `8.0` and `8.4` and
  produce a healthy, reachable MySQL instance either way — this is the
  core problem the role exists to solve.
