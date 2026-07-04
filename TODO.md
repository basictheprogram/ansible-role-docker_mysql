# TODO — ansible-role-docker_mysql

Items flagged during the `ansible-sync-role` session on 2026-07-04 that
weren't resolved in this session. Nothing here was silently dropped.

## Fixed: healthcheck never succeeded (official image has none)

After the auth-plugin fix, you reported the role still failed:
`docker ps` showed the container running with no `(healthy)`/
`(unhealthy)` annotation at all, and `docker logs` showed mysqld reach
"ready for connections" well within the timeout — but the role still
reported it never became healthy. Root cause: `DESIGN.md`'s original
readiness-check decision assumed the official `mysql` image defines a
Dockerfile `HEALTHCHECK`. It doesn't — confirmed via
[docker-library/mysql#196](https://github.com/docker-library/mysql/issues/196),
where the maintainers explicitly declined to add one. Without it,
`container.State.Health` is never populated, so the wait task's
`until: ... == "healthy"` condition could never be satisfied, no matter
how long MySQL actually took to start.

Fixed by having the role define its own `HEALTHCHECK` in the
`docker_container` task (`mysqladmin ping`), reusing
`mysql_docker_healthcheck_interval`/`_retries`/`mysql_docker_startup_timeout`
(as `start_period`) rather than adding new variables. `DESIGN.md`,
`README.md`, and this file were all updated with the real root cause.

Not yet done: same sandbox limitation as before — verified the task's
Jinja/YAML structure and ansible-lint/yamllint/ruff cleanliness, but
couldn't run a live container in this session. A real `molecule test`
(or your own environment, which already gave us the evidence for this
fix) is the next real verification step.

## Fixed: MySQL 8.4 crashed on startup (auth-plugin flag removed)

You reported the container's actual error log: mysqld aborted with
`unknown variable 'default-authentication-plugin=caching_sha2_password'`.
Confirmed this is real — MySQL 8.4 removed `--default-authentication-plugin`
(deprecated since 8.0.27, replaced by `--authentication-policy` with
different value syntax). Since `mysql_docker_version` defaults to `"8.4"`,
this broke the role out of the box for anyone who hadn't overridden the
version — not an edge case, a default-path failure.

Fixed in `tasks/main.yml`: the auth-plugin command-line flag is now chosen
based on `mysql_docker_version` (`>= 8.4` → `--authentication-policy`,
`< 8.4` → `--default-authentication-plugin`, unchanged). No variable
rename. Verified the Jinja logic renders correctly for both `"8.4"` and
`"8.0"` inputs. `DESIGN.md` has a "Bug fix (2026-07)" callout with the
original error text preserved for the record.

Not yet done: this was verified via Jinja/logic testing only in this
session (no live container run, same sandbox limitation as before) — a
real `molecule test` will exercise both the 8.0 and 8.4 code paths against
actual running containers and should be run before considering this
fully closed.

## Fixed: mysql_docker_healthcheck_interval was dead

Audit for this session's docs pass found `mysql_docker_healthcheck_interval`
defined in `defaults/main.yml` but never referenced anywhere in `tasks/` —
the wait task's `delay` was instead computed from
`mysql_docker_startup_timeout / mysql_docker_healthcheck_retries`. Per
your call, wired it in directly: `mysql_docker_healthcheck_retries` and
`mysql_docker_healthcheck_interval` are now the real controls, and
`mysql_docker_startup_timeout` is a derived value
(`retries * interval`, still overridable independently) shown only in the
failure message. Verified with a real `ansible-playbook` run that the
computed default is 50 (10 × 5). `DESIGN.md`'s Section 4 draft variable
block was updated to match.

## Not yet run: a real `molecule test`

This session verified the role with static checks only —
`ansible-lint`, `yamllint`, `ruff check`/`format` — all clean. There was
no Docker daemon available in this session's sandbox, so `molecule test`
itself (which actually creates containers, converges the role, and runs
the pytest-testinfra suite) has **not** been executed. Run it for real
before merging:

```bash
pip install -r molecule/requirements.txt --break-system-packages
ansible-galaxy collection install -r requirements.yml -r molecule/default/requirements.yml
molecule test
```

## `.ansible-lint` carries unrelated Windows/mock entries

`mock_roles` (`jborean93.win_openssh`) and part of `mock_modules`
(`chocolatey.chocolatey.*`, `ansible.windows.win_service`,
`ansible.windows.win_file`) came from `_template/.ansible-lint` verbatim
and don't apply to this role at all — it's Linux/Docker-only. They're
harmless (unused mocks don't affect linting), but are dead weight specific
to some other role. Left in place per "don't delete without being asked";
flagging here per that same convention. Safe to remove if you want a
cleaner file.

## No `meta/argument_specs.yml`

Step 4 only required fixing this file if it already existed with
placeholder content. It doesn't exist yet. Not required by any currently
enabled `.ansible-lint` rule, but worth adding later if you want
`ansible-doc`-driven variable documentation/validation.

## Open design questions (from `DESIGN.md`, Section 7)

None of these were needed for v1 and weren't addressed in this sync
(intentionally — they're future considerations, not sync-scope):

- Production use: persistent (non-wiped) volumes, backup/restore,
  non-destructive update path, and secret-manager backends beyond
  Ansible Vault (Ansible Vault credential handling is now done — see
  below).
- Multi-version side-by-side support.
- Custom `my.cnf` templating.
- RHEL/Amazon Linux support.
- Formal `meta/main.yml` dependency on `ansible-role-docker`.

## Vault-encrypted root password + optional user (this session)

Per explicit direction, changed credential handling and reversed two
settled `DESIGN.md` decisions (flagged in the response, not blocked on):

- `mysql_docker_root_password` has no default now (was `"root"`).
  `tasks/preflight.yml` fails fast with vault setup guidance if it's
  blank. Set it via a vault-encrypted `host_vars` variable — see the
  README's Credentials section.
- Added `mysql_docker_user`/`mysql_docker_password` (blank/opt-in) to
  pass `MYSQL_USER`/`MYSQL_PASSWORD` to the container. Preflight asserts
  they're set together, not just one of the two.
- Added `mysql_docker_host` (default `"localhost"`) — informational only,
  documents where to connect; not passed to the container.
- `mysql_docker_container_port` is now also passed as `MYSQL_TCP_PORT`,
  so it actually controls what port mysqld listens on inside the
  container (previously only affected the Docker port *publish* mapping).
- Molecule's `host_vars` now set a plaintext `mysql_docker_root_password:
  "root"` per instance (matches `tests/_data.py`) since the role no
  longer has a working default — flagged clearly as a test fixture, not
  a real credential.
- `DESIGN.md` Section 3 was amended in place (with an explicit
  "Amendment (2026-07)" callout) rather than rewritten silently, so the
  original decision and rationale for reversing it are both visible.
- Not yet done: no real vault-encrypted value exists anywhere in this
  repo (correctly) — you'll need to run `ansible-vault encrypt_string`
  yourself and put the result in the actual `host_vars/<host>/vault.yml`
  this project uses before the role can run for real.

## Debian 13 (trixie) added

Confirmed supported (EOL 2028-08 standard / 2030-06 LTS per
`scripts/platform-data.json`). Added to `meta/main.yml`'s description,
the README's Supported Platforms list, and a third Molecule platform
(`instance-debian13`, `geerlingguy/docker-debian13-ansible:latest`).

## No CI badge added

README badges added: Ansible Galaxy, License, ansible-core version.
Deliberately did **not** add a GitHub Actions CI badge (unlike sibling
roles such as `ansible-role-docker`) because there's no
`.github/workflows/` in this repo yet — a badge pointing at a
nonexistent workflow would be broken. Add one once a CI workflow exists.

## No `roles/realtime.docker_mysql` symlink yet

README examples and the Galaxy badge now reference `realtime.docker_mysql`
(the `namespace.role_name` from `meta/main.yml`), matching how sibling
roles are consumed in this monorepo (e.g. `realtime.docker` symlinks to
`git_repository/ansible-role-docker`). No equivalent
`roles/realtime.docker_mysql -> git_repository/ansible-role-docker_mysql`
symlink exists yet at the `ansible-playbooks/roles/` root, so local
playbooks in this repo can't yet resolve that name — only the Molecule
scenario's own role resolution (via the actual directory name) works
today. Add the symlink if you want local playbooks to use the same name
as the README documents.

## Debian 11 (bullseye) dropped

Confirmed with you during this sync: bullseye's LTS window ends
2026-08-31 and it's flagged EOL in `scripts/platform-data.json`, so it
was dropped from `meta/main.yml`'s description, the README's Supported
Platforms list, and the Molecule platform matrix. Only Debian 12
(bookworm) remains for the Debian family.

## Testinfra suite doesn't follow the shared skeleton shape

The shared `assets/molecule-tests/` skeletons in this skill are built
around a `TEST_USERS`/user-management fixture shape that doesn't apply to
this role (it manages a single Docker container, not OS users). Wrote
role-specific `test_container.py` and `test_connectivity.py` instead of
adapting the skeleton's `test_users.py`/`test_history.py`/
`test_packages.py`. If the shared skeleton gains new shared conventions
later, this role's tests won't auto-inherit them since they don't follow
the same `TEST_USERS` shape — worth a manual check next sync.
