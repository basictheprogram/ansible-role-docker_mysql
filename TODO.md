# TODO — ansible-role-docker_mysql

Items flagged during the `ansible-sync-role` session on 2026-07-04 that
weren't resolved in this session. Nothing here was silently dropped.

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

- Production use: vaulted credentials, persistent (non-wiped) volumes,
  backup/restore, non-destructive update path.
- Multi-version side-by-side support.
- Custom `my.cnf` templating.
- RHEL/Amazon Linux support.
- Formal `meta/main.yml` dependency on `ansible-role-docker`.
- Exposing connection facts (host, port, root password) for downstream
  playbook consumption (DESIGN.md Section 5, item 6) — still marked
  optional/future, not implemented.

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
