# Ansible Role: Docker MySQL

[![Ansible Galaxy](https://img.shields.io/badge/ansible--galaxy-realtime.docker__mysql-blue.svg?style=popout-square)](https://galaxy.ansible.com/ui/standalone/roles/realtime/docker_mysql/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ansible-core](https://img.shields.io/badge/ansible--core-%3E%3D2.20-blue.svg)](https://github.com/ansible/ansible)

Stands up a single, version-pinned MySQL instance in a Docker container.
Built for testing/CI use: every role run destroys and recreates the
container and wipes its data volume, so switching MySQL versions (e.g.
8.0 → 8.4) is a one-variable change and every run starts from a clean
database. See `DESIGN.md` for the full design rationale and open questions.

**Not for production use.** Data does not persist between runs by design.

## Requirements

- Ansible core >= 2.20 on the control node (enforced by a preflight
  assertion — see Task Flow below).
- Ubuntu or Debian host (Ubuntu/Debian only in v1).
- Docker already installed and running on the target host. This role does
  **not** install Docker — run `ansible-role-docker` (or equivalent) first.
- The `community.docker` collection (see `requirements.yml`):

  ```bash
  ansible-galaxy collection install -r requirements.yml
  ```

## Supported Platforms

- Ubuntu: jammy (22.04), noble (24.04)
- Debian: bookworm (12), trixie (13)

## Role Variables

All variables live in `defaults/main.yml`, and every one of them can be
overridden the normal Ansible way — most commonly per-host in
`host_vars/<host>.yml` (or `host_vars/<host>/vault.yml` for the
vault-encrypted ones), but also via `group_vars`, play `vars:`, etc. This
role has no OS-specific `vars/*.yml` overrides, since it doesn't branch on
OS family or install OS packages.

**Mandatory** means the role's preflight check (`tasks/preflight.yml`)
fails the run fast if the variable is left at its default/blank value.
Everything else has a working default and only needs overriding if you
want non-default behavior.

| Variable | Default | Mandatory? | Purpose |
|---|---|---|---|
| `mysql_docker_version` | `"8.4"` | No | MySQL version — maps directly to the Docker Hub image tag. |
| `mysql_docker_image` | `"mysql"` | No | Image repository (override for mirrors/private registries). |
| `mysql_docker_container_name` | `"mysql-{{ mysql_docker_version }}"` | No | Container name, e.g. `mysql-8.4`. Override in `host_vars` for a more descriptive/unique name (e.g. per-project). |
| `mysql_docker_host` | `"localhost"` | No | Informational — where downstream consumers should connect. Not passed to the container. |
| `mysql_docker_host_port` | `3306` | No | Host port published to the container. |
| `mysql_docker_container_port` | `3306` | No | Container-side MySQL port. Also set as `MYSQL_TCP_PORT` inside the container, so mysqld actually listens on it. |
| `mysql_docker_root_password` | `""` | **Yes** | Root password. No default — set via vault-encrypted `host_vars`; preflight fails fast if still blank. See Credentials below. |
| `mysql_docker_user` | `""` | Only if you want an extra user | Optional additional MySQL user (`MYSQL_USER`). Blank/opt-in by default. Must be set together with `mysql_docker_password` — preflight fails if only one of the pair is set. |
| `mysql_docker_password` | `""` | Only if `mysql_docker_user` is set | Password for `mysql_docker_user` (`MYSQL_PASSWORD`). Same vaulting guidance as the root password. |
| `mysql_docker_character_set` | `"utf8mb4"` | No | `--character-set-server`. |
| `mysql_docker_collation` | `"utf8mb4_unicode_ci"` | No | `--collation-server`. |
| `mysql_docker_default_authentication_plugin` | `"caching_sha2_password"` | No | Use `mysql_native_password` for legacy app compatibility. Passed as `--authentication-policy=<value>` on MySQL >= 8.4, or `--default-authentication-plugin=<value>` on 8.0 — the flag itself was removed in 8.4 (see Task Flow). |
| `mysql_docker_volume_name` | `"{{ mysql_docker_container_name }}-data"` | No | Named Docker volume mounted to `/var/lib/mysql`. |
| `mysql_docker_restart_policy` | `"unless-stopped"` | No | Container restart policy. |
| `mysql_docker_recreate` | `true` | No | Always destroy/recreate the container on every run. |
| `mysql_docker_wipe_volume` | `true` | No | Always wipe the data volume on every run. |
| `mysql_docker_healthcheck_retries` | `120` | No | Used both as the container's own `HEALTHCHECK retries` and the number of times the role polls for healthy before giving up. Generous by design — see note below. |
| `mysql_docker_healthcheck_interval` | `5` | No | Seconds between checks — used as both the container's `HEALTHCHECK interval` and the role's poll delay. |
| `mysql_docker_startup_timeout` | `"{{ mysql_docker_healthcheck_retries * mysql_docker_healthcheck_interval }}"` (600 by default) | No | Derived total wait. Used as the container's `HEALTHCHECK start_period` (so slow first-time database initialization isn't counted as a failure) and shown in the failure message. Can be overridden independently of the two vars above. |

Because this role always wipes the volume and reinitializes MySQL from
scratch, `--initialize` time varies a lot in practice — two consecutive
runs on the same host were observed taking ~34 seconds and ~239 seconds
respectively (disk I/O contention, not a role bug). The 10-minute default
budget above is intentionally generous to absorb that; a healthy
container still reports healthy as soon as it's ready; the budget only
matters for how long a genuinely stuck container is polled before the
role gives up. Tighten it via `host_vars` only if you've confirmed your
host's init time is reliably fast.

## Credentials

`mysql_docker_root_password` has no default and must be supplied via a
vault-encrypted `host_vars` variable — the preflight check
(`tasks/preflight.yml`) fails fast with a clear message if it's still
blank when the role runs. Encrypt it with `ansible-vault encrypt_string`
and put the result in `host_vars/<host>/vault.yml` (or wherever this
project's vaulted host vars live):

```bash
ansible-vault encrypt_string 'super-secret-value' --name 'mysql_docker_root_password'
```

```yaml
# host_vars/<host>/vault.yml
mysql_docker_root_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  66386439653236336161636... (truncated)
```

`mysql_docker_user` / `mysql_docker_password` are optional and follow the
same pattern — set both together (or leave both blank, the default) to
have the image create one additional MySQL user at container start. This
is opt-in: the role still does not provision application databases or
schemas — see Out of Scope below.

## Task Flow

1. **Preflight** (`tasks/preflight.yml`) — asserts the control node's
   Ansible version is >= 2.20; that `mysql_docker_version`,
   `mysql_docker_image`, `mysql_docker_container_name`,
   `mysql_docker_volume_name`, and `mysql_docker_host` are defined and
   non-empty; that `mysql_docker_root_password` is set (fails fast with
   vault setup guidance if blank); that `mysql_docker_user` and
   `mysql_docker_password` are set together, not just one of the pair;
   and that the host/container ports are valid — all before anything
   touches the host.
2. **Docker availability check** — fails fast with a clear message if
   Docker isn't installed/running (this role doesn't install Docker).
3. **Teardown** — removes any existing container/volume matching the
   configured names (always-recreate/always-wipe by design).
4. **Create volume** — fresh named Docker volume.
5. **Run container** — starts MySQL from the pinned image tag with the
   configured port, volume mount, root password, optional additional
   user, charset/auth flags, and a `HEALTHCHECK` the role defines itself
   (`mysqladmin ping` against `mysql_docker_container_port`) — **the
   official image ships no `HEALTHCHECK` of its own**
   ([docker-library/mysql#196](https://github.com/docker-library/mysql/issues/196)).
   The auth-plugin flag is chosen based on `mysql_docker_version`:
   `--authentication-policy=<plugin>` on MySQL >= 8.4 (which removed
   `--default-authentication-plugin` — passing it there aborts the server
   on startup), or `--default-authentication-plugin=<plugin>` on 8.0.
6. **Wait for healthy** — polls the container's health status (as
   reported by the `HEALTHCHECK` from step 5) every
   `mysql_docker_healthcheck_interval` seconds, up to
   `mysql_docker_healthcheck_retries` times, and fails with a clear
   message (citing `mysql_docker_startup_timeout`) if it never reports
   healthy.

## Example Usage

### MySQL 8.4 (default)

```yaml
- hosts: ci_runners
  roles:
    - role: realtime.docker_mysql
```

### MySQL 8.0

```yaml
- hosts: ci_runners
  roles:
    - role: realtime.docker_mysql
      vars:
        mysql_docker_version: "8.0"
```

### Custom container name via host_vars

The default container name (`mysql-{{ mysql_docker_version }}`, e.g.
`mysql-8.4`) is fine when a host only ever runs one instance of this role.
Give it a more descriptive name in `host_vars/<host>.yml` if you want
`docker ps` to show which project it belongs to:

```yaml
# host_vars/ci-runner-01.yml
mysql_docker_container_name: "myproject-mysql"
```

Every default in `defaults/main.yml` can be overridden the same way —
`host_vars` isn't special-cased for the container name specifically.

### Custom port with a vaulted root password

`mysql_docker_root_password` comes from a vault-encrypted `host_vars`
variable (see Credentials above) — it's not passed as a play `vars:`
value here:

```yaml
- hosts: ci_runners
  roles:
    - role: realtime.docker_mysql
      vars:
        mysql_docker_version: "8.4"
        mysql_docker_host_port: 3307
```

### With an optional application user

```yaml
- hosts: ci_runners
  roles:
    - role: realtime.docker_mysql
      # mysql_docker_user / mysql_docker_password also come from
      # vault-encrypted host_vars
```

After the role completes, MySQL is reachable at
`{{ mysql_docker_host }}:{{ mysql_docker_host_port }}` with the configured
root password (and the optional user, if set).

## Testing

Molecule scaffolding is in `molecule/default/`, using the Docker driver and
a pytest-testinfra verifier, against Ubuntu (jammy, noble) and Debian
(bookworm, trixie) platforms:

```bash
pip install -r molecule/requirements.txt --break-system-packages
ansible-galaxy collection install -r requirements.yml -r molecule/default/requirements.yml
molecule test
```

Note: this role intentionally destroys/recreates the container and wipes the
volume on every run, so the standard Molecule idempotence check doesn't
apply and is omitted from the test sequence in `molecule/default/molecule.yml`.

## Out of Scope (v1)

- Production/persistent use.
- Multiple MySQL versions running simultaneously on one host.
- Application-level database/schema provisioning. (An optional single
  MySQL user can be created via `mysql_docker_user`/`mysql_docker_password`,
  but the role does not create databases, schemas, or grants beyond what
  the image itself does for that user.)
- Backup/restore tooling.
- Non-Debian/Ubuntu hosts.
- Custom `my.cnf` templating beyond charset/auth flags.

See `DESIGN.md` for details and future considerations.

## License

[MIT](LICENSE)

## Author Information

Copyright (c) 2026 Bob Tanner / Real Time Enterprises, Inc.
