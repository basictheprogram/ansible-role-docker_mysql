"""Shared test constants for the ansible-role-docker_mysql Molecule scenario.

This role has no per-user fixtures (unlike the shared skeleton this file is
based on) -- it manages a single Docker container, not OS users. These
constants must match molecule/default/molecule.yml's host_vars (or the
role's defaults/main.yml, when host_vars doesn't override them) exactly.
"""

from __future__ import annotations

MYSQL_VERSION: str = "8.4"
MYSQL_IMAGE: str = "mysql"
MYSQL_CONTAINER_NAME: str = f"mysql-{MYSQL_VERSION}"
MYSQL_HOST_PORT: int = 3306
MYSQL_ROOT_PASSWORD: str = "root"  # noqa: S105 -- ephemeral CI test fixture, not a real secret
