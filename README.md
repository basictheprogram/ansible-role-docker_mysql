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

Debian 11 (bullseye) is intentionally not supported — its LTS window ends
2026-08-31. Other OS families are out of scope for v1 — see `DESIGN.md`.

## Role Variables

All variables live in `defaults/main.yml`. This role has no OS-specific
`vars/*.yml` overrides — it doesn't branch on OS family or install OS
packages, so every variable is user-overridable via the normal
`defaults/` mechanism.

| Variable | Default | Purpose |
|---|---|---|
| `mysql_docker_version` | `"8.4"` | MySQL version — maps directly to the Docker Hub image tag. |
| `mysql_docker_image` | `"mysql"` | Image repository (override for mirrors/private registries). |
| `mysql_docker_container_name` | `"mysql-{{ mysql_docker_version }}"` | Container name. |
| `mysql_docker_host_port` | `3306` | Host port published to the container. |
| `mysql_docker_container_port` | `3306` | Container-side MySQL port. |
| `mysql_docker_root_password` | `"root"` | Root password. Plain var — acceptable for ephemeral/non-secret CI use, not vaulted. |
| `mysql_docker_character_set` | `"utf8mb4"` | `--character-set-server`. |
| `mysql_docker_collation` | `"utf8mb4_unicode_ci"` | `--collation-server`. |
| `mysql_docker_default_authentication_plugin` | `"caching_sha2_password"` | Use `mysql_native_password` for legacy app compatibility. |
| `mysql_docker_volume_name` | `"{{ mysql_docker_container_name }}-data"` | Named Docker volume mounted to `/var/lib/mysql`. |
| `mysql_docker_restart_policy` | `"unless-stopped"` | Container restart policy. |
| `mysql_docker_recreate` | `true` | Always destroy/recreate the container on every run. |
| `mysql_docker_wipe_volume` | `true` | Always wipe the data volume on every run. |
| `mysql_docker_healthcheck_retries` | `10` | Retries while waiting for the container's healthcheck. |
| `mysql_docker_startup_timeout` | `60` | Seconds to wait for a healthy container before failing the role. |

## Task Flow

1. **Preflight** (`tasks/preflight.yml`) — asserts the control node's
   Ansible version is >= 2.20, that the required container variables are
   defined and non-empty, and that the host/container ports are valid
   before anything touches the host.
2. **Docker availability check** — fails fast with a clear message if
   Docker isn't installed/running (this role doesn't install Docker).
3. **Teardown** — removes any existing container/volume matching the
   configured names (always-recreate/always-wipe by design).
4. **Create volume** — fresh named Docker volume.
5. **Run container** — starts MySQL from the pinned image tag with the
   configured port, volume mount, root password, and charset/auth flags.
6. **Wait for healthy** — polls the container's built-in healthcheck
   (`mysqladmin ping`) and fails with a clear message if it doesn't report
   healthy within `mysql_docker_startup_timeout`.

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

### Custom port and password

```yaml
- hosts: ci_runners
  roles:
    - role: realtime.docker_mysql
      vars:
        mysql_docker_version: "8.4"
        mysql_docker_host_port: 3307
        mysql_docker_root_password: "{{ vault_mysql_root_password }}"
```

After the role completes, MySQL is reachable at
`localhost:{{ mysql_docker_host_port }}` with the configured root password.

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
- Application-level database/user/schema provisioning.
- Backup/restore tooling.
- Non-Debian/Ubuntu hosts.
- Custom `my.cnf` templating beyond charset/auth flags.

See `DESIGN.md` for details and future considerations.

## License

[MIT](LICENSE)

## Author Information

Created in 2026 by Bob Tanner, Real Time Enterprises, Inc.

Copyright (c) 2026 Bob Tanner / Real Time Enterprises, Inc.
